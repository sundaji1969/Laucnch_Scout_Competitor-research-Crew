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

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.crew import provenance
from app.crew.inputs import RunInputs
from app.crew.progress import AGENT_KEYS, MANAGER_KEY, Emit, crew_progress, make_event
from app.crew.schemas import CompetitorList, ReviewInsights, StrategyMatrix
from app.services.report_validator import (
    ReportValidationError,
    split_sections,
    validate_report,
)

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
    search_calls: int = 0
    llm_model: str = ""
    errors: list[str] = field(default_factory=list)

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


def _prefer_complete_report(markdown: str, saved_path: Any) -> str:
    """Use the Report Writer's saved report.md when the final answer is missing sections.

    In PROCESS_MODE=hierarchical the last task's output is the manager's answer, which can
    come back as "the report has been saved" instead of the report itself. The writer saved
    the full report with its file tool, so prefer whichever has more required sections.
    """
    try:
        saved = clean_markdown(saved_path.read_text(encoding="utf-8")) if saved_path.exists() else ""
    except OSError:
        return markdown
    if not saved:
        return markdown
    final_n, saved_n = len(split_sections(markdown)), len(split_sections(saved))
    if saved_n > final_n:
        log.warning(
            "final_answer_incomplete_using_saved_report",
            extra={"sections_final": final_n, "sections_saved": saved_n},
        )
        return saved
    return markdown


def _noop(_: dict[str, Any]) -> None:
    return None


def _structured_outputs(tasks_output: list[Any]) -> dict[str, Any]:
    models: list[tuple[str, type[BaseModel]]] = [
        ("competitors", CompetitorList),
        ("reviews", ReviewInsights),
        ("strategy", StrategyMatrix),
    ]
    out: dict[str, Any] = {}
    for (key, model), t in zip(models, tasks_output, strict=False):
        pyd = getattr(t, "pydantic", None)
        if pyd is None:  # fall back to parsing the raw JSON answer
            raw = str(getattr(t, "raw", "") or "")
            try:
                pyd = model.model_validate_json(raw[raw.find("{") : raw.rfind("}") + 1])
            except ValueError:
                log.warning("structured_output_unparsed", extra={"task": key})
        out[key] = pyd.model_dump(mode="json") if pyd is not None else None
    return out


def run_crew(
    inputs: RunInputs,
    run_id: str | None = None,
    emit: Emit | None = None,
    settings: Settings | None = None,
    crew_factory: Callable[[Settings], Any] | None = None,
    track_provenance: bool = True,
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
    manager = getattr(crew, "manager_agent", None)
    if manager is not None:  # PROCESS_MODE=hierarchical
        role_to_key[str(manager.role).strip()] = MANAGER_KEY
        id_to_key[str(manager.id)] = MANAGER_KEY
    # Each task's specialist, fixed before kickoff (the manager executes tasks in hierarchical mode).
    task_to_key = {
        str(t.id): id_to_key[str(t.agent.id)]
        for t in getattr(crew, "tasks", []) or []
        if getattr(t, "agent", None) is not None and str(t.agent.id) in id_to_key
    }
    crew_inputs = inputs.as_crew_inputs(run_id, out_dir.as_posix(), date.today().isoformat())

    if track_provenance:
        provenance.start()
    try:
        with crew_progress(run_id, emit, role_to_key, id_to_key, task_to_key):
            output = crew.kickoff(inputs=crew_inputs)
    except Exception as exc:
        provenance.stop()
        emit(make_event("run_failed", run_id, message=f"Crew failed: {type(exc).__name__}: {exc}"[:500]))
        raise

    tasks_output = list(getattr(output, "tasks_output", []) or [])
    final_raw = str(getattr(tasks_output[-1], "raw", "") if tasks_output else getattr(output, "raw", ""))
    markdown = clean_markdown(final_raw)

    # Authoritative copy: always (over)write report.md from the final task output, so the
    # saved file matches what is validated even if the agent's FileWriterTool call varied.
    report_path = out_dir / "report.md"
    markdown = _prefer_complete_report(markdown, report_path)
    report_path.write_text(markdown, encoding="utf-8")

    structured = _structured_outputs(tasks_output)
    usage_obj = getattr(output, "token_usage", None)
    token_usage: dict[str, Any] = {}
    if usage_obj is not None and hasattr(usage_obj, "model_dump"):
        token_usage = usage_obj.model_dump()

    tracking = provenance.is_active()
    validation = validate_report(
        markdown,
        is_known_url=provenance.was_seen if tracking else None,
        unverified_price=provenance.unverified_price if tracking else None,
    )
    if tracking:
        (out_dir / "evidence.json").write_text(
            json.dumps(provenance.evidence(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
    provenance.stop()
    duration = time.monotonic() - started
    result = RunResult(
        run_id=run_id,
        report_markdown=markdown,
        report_path=str(report_path),
        structured=structured,
        sources=validation.sources,
        duration_seconds=round(duration, 1),
        token_usage=token_usage,
        search_calls=provenance.search_calls(),
        llm_model=settings.llm_model,
        errors=validation.errors,
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
