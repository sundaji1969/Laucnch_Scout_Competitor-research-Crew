"""CLI entry point.

    python -m app.crew.run --idea "Healthy millet meal boxes delivered for lunch" \
        --city Coimbatore --customer "Office workers, age 25 to 40" --competitors "A, B"

Writes outputs/<run_id>/report.md (and result.json) and prints live progress.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

from app.crew.inputs import RunInputs
from app.services.report_validator import ReportValidationError

SAMPLE = {
    "idea": "Healthy millet meal boxes delivered for lunch",
    "city": "Coimbatore",
    "customer": "Office workers, age 25 to 40",
}


def _print_event(event: dict[str, Any]) -> None:
    stamp = time.strftime("%H:%M:%S", time.localtime(event.get("ts", time.time())))
    agent = event.get("agent", "")
    print(f"[{stamp}] {event['type']:<20} {agent:<18} {event.get('message', '')}", flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.crew.run", description="Run the LaunchScout crew")
    p.add_argument("--idea", default=SAMPLE["idea"])
    p.add_argument("--city", default=SAMPLE["city"])
    p.add_argument("--customer", default=SAMPLE["customer"])
    p.add_argument("--competitors", default="", help="comma-separated known competitors")
    p.add_argument("--run-id", default=None)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from app.crew.runner import run_crew  # heavy import after arg parsing

    inputs = RunInputs(
        business_idea=args.idea,
        city=args.city,
        target_customer=args.customer,
        known_competitors=args.competitors,
    )
    try:
        result = run_crew(inputs, run_id=args.run_id, emit=_print_event)
    except ReportValidationError as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 2
    print(f"\nReport saved to {result.report_path} ({result.duration_seconds}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
