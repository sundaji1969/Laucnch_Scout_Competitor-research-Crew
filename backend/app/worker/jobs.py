"""arq worker: executes crew runs in subprocesses with a hard timeout.

Start with:  arq app.worker.jobs.WorkerSettings
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import redis.asyncio as aioredis
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crew.progress import make_event
from app.db.models import Run, RunStatus, Source
from app.db.session import get_sessionmaker
from app.logging_setup import configure_logging
from app.services.events import publish_async
from app.services.report_validator import split_sections

log = logging.getLogger("launchscout.worker")

CHILD_CMD = [sys.executable, "-m", "app.worker.child"]


def _parse_source_line(text: str) -> tuple[str, str]:
    import re

    m = re.search(r"https?://[^\s)>\]]+", text)
    url = m.group(0) if m else ""
    title = text.replace(url, "").strip(" -–—:()[]<>") if url else text
    return title, url


def apply_result(run: Run, result: dict[str, Any]) -> None:
    structured = result.get("structured") or {}
    run.competitors = structured.get("competitors")
    run.reviews = structured.get("reviews")
    run.strategy = structured.get("strategy")
    run.report_markdown = result.get("report_markdown")
    run.duration_seconds = result.get("duration_seconds")
    run.search_calls = result.get("search_calls")
    run.llm_model = result.get("llm_model") or run.llm_model
    usage = result.get("token_usage") or {}
    run.prompt_tokens = usage.get("prompt_tokens")
    run.completion_tokens = usage.get("completion_tokens")
    run.total_tokens = usage.get("total_tokens")
    run.sources.clear()
    for n, text in sorted(((int(k), v) for k, v in (result.get("sources") or {}).items())):
        title, url = _parse_source_line(text)
        run.sources.append(Source(number=n, title=title[:500], url=url or text))


async def _finish(
    session: AsyncSession, r: aioredis.Redis, run: Run, status: RunStatus, message: str, **extra: Any
) -> None:
    run.status = status
    run.finished_at = datetime.now(UTC)
    if status is RunStatus.failed:
        run.error = message[:4000]
    await session.commit()
    etype = "run_completed" if status is RunStatus.completed else "run_failed"
    await publish_async(r, run.id, make_event(etype, run.id, message=message, **extra))


async def execute_run(ctx: dict[str, Any], run_id: str) -> str:
    settings = get_settings()
    r: aioredis.Redis = ctx["redis_events"]
    out_dir: Path = settings.outputs_path / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    async with get_sessionmaker()() as session:
        run = (await session.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
        if run is None:
            log.error("run_not_found", extra={"run_id": run_id})
            return "missing"
        run.status = RunStatus.running
        run.started_at = datetime.now(UTC)
        run.llm_model = settings.llm_model
        await session.commit()

        inputs = {
            "business_idea": run.business_idea,
            "city": run.city,
            "target_customer": run.target_customer,
            "known_competitors": run.known_competitors or [],
        }
        (out_dir / "inputs.json").write_text(json.dumps(inputs), encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(*CHILD_CMD, run_id, cwd=str(Path.cwd()))
        try:
            rc = await asyncio.wait_for(proc.wait(), timeout=settings.run_timeout_seconds)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            await _finish(
                session,
                r,
                run,
                RunStatus.failed,
                f"The research took longer than {settings.run_timeout_seconds // 60} minutes "
                "and was stopped.",
            )
            return "timeout"

        result_file = out_dir / "result.json"
        if result_file.exists():
            apply_result(run, json.loads(result_file.read_text("utf-8")))
        error_file = out_dir / "error.txt"
        error = error_file.read_text("utf-8") if error_file.exists() else ""

        if rc == 0 and run.report_markdown:
            n_comp = len((run.competitors or {}).get("competitors", []))
            await _finish(
                session,
                r,
                run,
                RunStatus.completed,
                f"Report ready · {n_comp} competitors · {len(run.sources)} sources",
                duration_seconds=run.duration_seconds,
                sections=list(split_sections(run.report_markdown)),
            )
            return "completed"

        friendly = error or f"The crew stopped unexpectedly (exit code {rc})."
        await _finish(session, r, run, RunStatus.failed, friendly)
        return "failed"


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    ctx["redis_events"] = aioredis.Redis.from_url(get_settings().redis_url)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["redis_events"].aclose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [execute_run]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = get_settings().max_concurrent_runs
    job_timeout = get_settings().run_timeout_seconds + 120
    max_tries = 1
    keep_result = 3600
