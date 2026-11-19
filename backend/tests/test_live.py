"""Opt-in live integration test (real LLM + Serper). Run with: pytest -m live"""

import os
from pathlib import Path
from typing import Any

import pytest

from app.crew.inputs import RunInputs
from app.crew.runner import run_crew

pytestmark = pytest.mark.live


@pytest.mark.skipif(
    not os.environ.get("SERPER_API_KEY") or os.environ.get("SERPER_API_KEY") == "test-key",
    reason="needs a real SERPER_API_KEY in .env",
)
def test_live_sample_input(tmp_path: Path) -> None:
    from app.config import Settings

    settings = Settings(outputs_dir=tmp_path)
    events: list[dict[str, Any]] = []
    result = run_crew(
        RunInputs(
            business_idea="Healthy millet meal boxes delivered for lunch",
            city="Coimbatore",
            target_customer="Office workers, age 25 to 40",
        ),
        emit=events.append,
        settings=settings,
    )
    comps = result.structured["competitors"]["competitors"]
    assert len(comps) >= 3
    assert all(c["price_per_unit"] and c["source_urls"] for c in comps)
    assert Path(result.report_path).exists()
    assert {e["agent"] for e in events if e["type"] == "agent_started"} >= {
        "market_researcher",
        "report_writer",
    }
