"""Worker job: subprocess orchestration, DB updates, terminal events, timeout."""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import fakeredis
import pytest

from app.config import get_settings
from app.db import session as db_session
from app.db.models import Base, Run, RunStatus
from app.services.events import history
from app.worker import jobs

GOOD = (Path(__file__).parent / "fixtures" / "good_report.md").read_text(encoding="utf-8")

FAKE_CHILD_OK = """
import json, sys, pathlib
run_id = sys.argv[1]
out = pathlib.Path(sys.argv[2]) / run_id
report = pathlib.Path(sys.argv[3]).read_text(encoding="utf-8")
(out / "result.json").write_text(json.dumps({
  "report_markdown": report, "duration_seconds": 12.5, "search_calls": 7, "llm_model": "openai/gpt-4.1",
  "structured": {"competitors": {"competitors": [{"name": "A"}, {"name": "B"}, {"name": "C"}]},
                 "reviews": None, "strategy": {"market_gap": "gap"}},
  "sources": {"1": "Millet Kitchen menu - https://example.com/millet-kitchen"},
  "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}), encoding="utf-8")
"""
FAKE_CHILD_FAIL = """
import sys, pathlib
out = pathlib.Path(sys.argv[2]) / sys.argv[1]
(out / "error.txt").write_text("Report failed validation: Missing section: 'Market Gap'", encoding="utf-8")
sys.exit(2)
"""
FAKE_CHILD_SLOW = "import time; time.sleep(30)"


@pytest.fixture
async def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[dict[str, Any]]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'w.db').as_posix()}")
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    for fn in (get_settings, db_session.get_engine, db_session.get_sessionmaker):
        fn.cache_clear()
    async with db_session.get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with db_session.get_sessionmaker()() as s:
        s.add(
            Run(
                id="r1",
                business_idea="Millet boxes",
                city="Coimbatore",
                target_customer="Office workers",
                known_competitors=[],
            )
        )
        await s.commit()
    yield {"redis_events": fakeredis.FakeAsyncRedis(), "tmp": tmp_path}
    await db_session.get_engine().dispose()
    for fn in (get_settings, db_session.get_engine, db_session.get_sessionmaker):
        fn.cache_clear()


def _use_child(monkeypatch: pytest.MonkeyPatch, tmp: Path, code: str) -> None:
    script = tmp / "fake_child.py"
    script.write_text(code, encoding="utf-8")
    report = tmp / "report.md"
    report.write_text(GOOD, encoding="utf-8")
    outputs = str(get_settings().outputs_path)

    real_exec = jobs.asyncio.create_subprocess_exec

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        run_id = args[-1]
        return await real_exec(sys.executable, str(script), run_id, outputs, str(report))

    monkeypatch.setattr(jobs.asyncio, "create_subprocess_exec", fake_exec)


async def _run(run_id: str = "r1") -> Run:
    async with db_session.get_sessionmaker()() as s:
        run = await s.get(Run, run_id)
        assert run is not None
        return run


async def test_successful_run_updates_db_then_publishes(
    ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_child(monkeypatch, ctx["tmp"], FAKE_CHILD_OK)
    assert await jobs.execute_run(ctx, "r1") == "completed"
    run = await _run()
    assert run.status is RunStatus.completed
    assert run.report_markdown and "## 6. Sources" in run.report_markdown
    assert run.total_tokens == 15
    assert run.search_calls == 7
    assert [(s.number, s.url) for s in run.sources] == [(1, "https://example.com/millet-kitchen")]
    inputs = json.loads((get_settings().outputs_path / "r1" / "inputs.json").read_text())
    assert inputs["city"] == "Coimbatore"
    events = await history(ctx["redis_events"], "r1")
    assert events[-1]["type"] == "run_completed"
    assert "3 competitors" in events[-1]["message"]


async def test_validation_failure_marks_failed(ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _use_child(monkeypatch, ctx["tmp"], FAKE_CHILD_FAIL)
    assert await jobs.execute_run(ctx, "r1") == "failed"
    run = await _run()
    assert run.status is RunStatus.failed
    assert run.error and "Missing section" in run.error
    events = await history(ctx["redis_events"], "r1")
    assert events[-1]["type"] == "run_failed"


async def test_timeout_kills_child(ctx: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    _use_child(monkeypatch, ctx["tmp"], FAKE_CHILD_SLOW)
    assert await jobs.execute_run(ctx, "r1") == "timeout"
    run = await _run()
    assert run.status is RunStatus.failed
    assert run.error and "longer than" in run.error
