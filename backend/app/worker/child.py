"""Crew subprocess: ``python -m app.worker.child <run_id>``.

Runs exactly one crew in an isolated process (CrewAI's event bus is process-global),
streaming progress to Redis. Terminal events (run_completed / run_failed) are NOT
published here: the parent job publishes them after the database is updated, so a
browser that reacts to "completed" always finds the finished report.

Exit codes: 0 = report valid, 2 = report failed validation, 1 = crew error.
Inputs are read from outputs/<run_id>/inputs.json; results go to result.json / error.txt.
"""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from app.config import get_settings
from app.crew.inputs import RunInputs
from app.services.events import TERMINAL, SyncEventPublisher
from app.services.report_validator import ReportValidationError


def main(argv: list[str]) -> int:
    run_id = argv[0]
    settings = get_settings()
    out_dir = settings.outputs_path / run_id
    logging.basicConfig(level=logging.WARNING)
    publisher = SyncEventPublisher(settings.redis_url, run_id)

    def emit(event: dict[str, Any]) -> None:
        if event.get("type") in TERMINAL:
            return
        publisher.publish(event)

    try:
        inputs = RunInputs.model_validate_json((out_dir / "inputs.json").read_text("utf-8"))
        from app.crew.runner import run_crew

        run_crew(inputs, run_id=run_id, emit=emit, settings=settings)
        return 0
    except ReportValidationError as exc:
        (out_dir / "error.txt").write_text(str(exc), encoding="utf-8")
        return 2
    except Exception as exc:  # noqa: BLE001 - report every failure to the parent
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "error.txt").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        (out_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    finally:
        publisher.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
