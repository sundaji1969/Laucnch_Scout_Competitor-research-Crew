"""Scripted fake LLM + canned outputs for offline crew tests (no API keys, no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crewai.llms.base_llm import BaseLLM

FIXTURES = Path(__file__).parent / "fixtures"

COMPETITORS: dict[str, Any] = {
    "business_idea": "Healthy millet meal boxes",
    "city": "Coimbatore",
    "competitors": [
        {
            "name": "Millet Kitchen",
            "price_per_unit": "₹180 per meal",
            "price_value": 180,
            "sales_channels": ["Swiggy"],
            "source_urls": ["https://example.com/millet-kitchen"],
        },
        {
            "name": "GreenBowl CBE",
            "price_per_unit": "₹220 per bowl",
            "price_value": 220,
            "sales_channels": ["Zomato"],
            "source_urls": ["https://www.zomato.com/coimbatore/greenbowl"],
        },
        {
            "name": "Amma Tiffin",
            "price_per_unit": "Not publicly listed",
            "sales_channels": ["WhatsApp"],
            "source_urls": ["https://www.instagram.com/ammastiffin"],
        },
    ],
    "search_queries_used": ["millet meals coimbatore"],
}
TOO_FEW: dict[str, Any] = {**COMPETITORS, "competitors": COMPETITORS["competitors"][:2]}

REVIEWS: dict[str, Any] = {
    "reviews": [
        {
            "competitor": "Millet Kitchen",
            "likes": [],
            "complaints": [
                {
                    "text": "Late delivery",
                    "source_urls": ["https://www.swiggy.com/restaurants/millet-kitchen"],
                }
            ],
        }
    ],
    "common_pain_points": [
        {
            "pain_point": "Late lunch delivery",
            "competitors": ["Millet Kitchen"],
            "source_urls": ["https://www.swiggy.com/restaurants/millet-kitchen"],
        }
    ],
}

STRATEGY: dict[str, Any] = {
    "matrix": [
        {
            "competitor": "Millet Kitchen",
            "price_per_unit": "₹180 per meal",
            "price_value": 180,
            "channel": "Swiggy",
            "strength": "Menu",
            "weakness": "Late",
            "differentiation_score": 6,
            "source_urls": ["https://example.com/millet-kitchen"],
        }
    ],
    "market_gap": "On-time millet lunch subscriptions for offices",
    "recommended_offer": "On-time millet lunch boxes for offices",
    "recommended_price": "₹169 per meal",
    "positioning_rationale": "Undercuts GreenBowl",
}


def _final(payload: Any) -> str:
    body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return f"Thought: I now know the final answer\nFinal Answer: {body}"


class ScriptedLLM(BaseLLM):
    """Answers each task with canned output, chosen from keywords in the prompt.

    ``research_outputs`` is consumed in order for task 1 so tests can make the guardrail
    reject the first attempt and accept a retry.
    """

    research_outputs: list[Any] = []  # noqa: RUF012 - pydantic field, copied per instance
    report: str = ""
    calls: int = 0

    def __init__(self, research_outputs: list[Any] | None = None, report: str | None = None) -> None:
        super().__init__(model="fake/scripted")
        self.research_outputs = list(research_outputs or [COMPETITORS])
        self.report = report if report is not None else (FIXTURES / "good_report.md").read_text("utf-8")
        self.calls = 0

    def call(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        if isinstance(messages, str):
            text = messages
        else:
            text = "\n".join(str(m.get("content", "")) for m in messages)
        response_model = kwargs.get("response_model")
        if "save it with the file writer tool" in text:
            return _final(self.report)
        if "build the strategy for launching" in text:
            payload: Any = STRATEGY
        elif "find what customers like and complain" in text:
            payload = REVIEWS
        elif len(self.research_outputs) > 1:
            payload = self.research_outputs.pop(0)
        else:
            payload = self.research_outputs[0]
        if response_model is not None:
            return response_model.model_validate(payload)
        return _final(payload)

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return True

    def get_context_window_size(self) -> int:
        return 200_000
