"""Hierarchical mode: the strategy must come from the Strategy Analyst, not the director."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from app.crew import delegation
from app.crew.guardrails import strategy_from_specialist_guardrail
from app.crew.schemas import StrategyMatrix


def _strategy(gap: str, price: str) -> str:
    return StrategyMatrix.model_validate(
        {
            "matrix": [],
            "market_gap": gap,
            "recommended_price": price,
            "recommended_offer": "Fresh millet lunches, on time",
            "positioning_rationale": "r",
        }
    ).model_dump_json()


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    delegation.reset()
    yield
    delegation.reset()


def test_rejects_until_the_analyst_has_worked_on_it() -> None:
    director_answer = SimpleNamespace(raw=_strategy("Director's own gap", "₹199"))
    ok, msg = strategy_from_specialist_guardrail(director_answer)
    assert not ok
    assert "Go-to-Market Strategy Analyst" in msg and "Do not write the strategy yourself" in msg
    delegation.record("market_researcher", "{}")  # other specialists don't count
    assert strategy_from_specialist_guardrail(director_answer)[0] is False


def test_uses_the_analysts_own_answer_not_the_directors_rewording() -> None:
    delegation.record("strategy_analyst", "Thought: done\n" + _strategy("First draft gap", "₹149"))
    delegation.record("strategy_analyst", "```json\n" + _strategy("Analyst's gap", "₹169") + "\n```")
    ok, result = strategy_from_specialist_guardrail(SimpleNamespace(raw=_strategy("Reworded gap", "₹199")))
    assert ok
    out = StrategyMatrix.model_validate_json(result)
    assert (out.market_gap, out.recommended_price) == ("Analyst's gap", "₹169")  # latest answer wins


def test_accepts_the_directors_structuring_of_a_prose_answer() -> None:
    delegation.record("strategy_analyst", "The clearest gap is reliable on-time millet lunches at ₹169.")
    director_answer = SimpleNamespace(raw=_strategy("Reliable on-time millet lunches", "₹169"))
    ok, result = strategy_from_specialist_guardrail(director_answer)
    assert ok and result is director_answer
