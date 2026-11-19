"""Run the crew end to end: kickoff, collect structured outputs, save and validate the report."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from app.config import Settings, get_settings
from app.crew.inputs import RunInputs
from app.crew.progress import AGENT_KEYS, Emit, crew_progress, make_event
from app.services.report_validator import ReportValidationError, validate_report

log = logging.getLogger("launchscout.runner")

_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", re.DOTALL)


@dataclass
class RunResult:
    run_id: str
    report_markdown: str
    report_path: str
    structured: dict[str, Any]
    sources: dict[int, str]
    duration_seconds: float
    token_usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = {str(k): v for k, v in self.sources.items()}
        return d


def clean_markdown(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    return text + "\n"


def _noop(_: dict[str, Any]) -> None:
    return None


def _structured_outputs(tasks_output: list[Any]) -> dict[str, Any]:
    keys = ["competitors", "reviews", "strategy"]
    out: dict[str, Any] = {}
    for key, t in zip(keys, tasks_output, strict=False):
        pyd = getattr(t, "pydantic", None)
        out[key] = pyd.model_dump(mode="json") if pyd is not None else None
    return out


def run_crew(
    inputs: RunInputs,
    run_id: str | None = None,
    emit: Emit | None = None,
    settings: Settings | None = None,
    crew_factory: Callable[[Settings], Any] | None = None,
) -> RunResult:
    """Execute a full run. Raises ``ReportValidationError`` if the final report fails validation."""
    settings = settings or get_settings()
    run_id = run_id or uuid.uuid4().hex[:12]
    emit = emit or _noop
    out_dir = settings.outputs_path / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    if crew_factory is None:
        from app.crew.crew import LaunchScoutCrew

        def crew_factory(s: Settings) -> Any:
            return LaunchScoutCrew(settings=s).crew()

    crew = crew_factory(settings)
    role_to_key = {a.role.strip(): k for a, k in zip(crew.agents, AGENT_KEYS, strict=False)}
    id_to_key = {str(a.id): k for a, k in zip(crew.agents, AGENT_KEYS, strict=False)}
    crew_inputs = inputs.as_crew_inputs(run_id, out_dir.as_posix(), date.today().isoformat())

    try:
        with crew_progress(run_id, emit, role_to_key, id_to_key):
            output = crew.kickoff(inputs=crew_inputs)
    except Exception as exc:
        emit(make_event("run_failed", run_id, message=f"Crew failed: {type(exc).__name__}: {exc}"[:500]))
        raise

    tasks_output = list(getattr(output, "tasks_output", []) or [])
    final_raw = str(getattr(tasks_output[-1], "raw", "") if tasks_output else getattr(output, "raw", ""))
    markdown = clean_markdown(final_raw)

    # Authoritative copy: always (over)write report.md from the final task output, so the
    # saved file matches what is validated even if the agent's FileWriterTool call varied.
    report_path = out_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")

    structured = _structured_outputs(tasks_output)
    usage_obj = getattr(output, "token_usage", None)
    token_usage: dict[str, Any] = {}
    if usage_obj is not None and hasattr(usage_obj, "model_dump"):
        token_usage = usage_obj.model_dump()

    validation = validate_report(markdown)
    duration = time.monotonic() - started
    result = RunResult(
        run_id=run_id,
        report_markdown=markdown,
        report_path=str(report_path),
        structured=structured,
        sources=validation.sources,
        duration_seconds=round(duration, 1),
        token_usage=token_usage,
    )
    (out_dir / "result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

    if not validation.ok:
        msg = "Report failed validation: " + "; ".join(validation.errors)
        emit(make_event("run_failed", run_id, message=msg, errors=validation.errors))
        raise ReportValidationError(validation.errors)

    emit(
        make_event(
            "run_completed",
            run_id,
            message=f"Report ready · {validation.competitor_rows} competitors · "
            f"{len(validation.sources)} sources · {duration:.0f}s",
            duration_seconds=round(duration, 1),
        )
    )
    return result
