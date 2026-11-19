"""CrewAI task guardrails.

``competitor_list_guardrail`` is attached to task 1 (market research). It rejects
output with fewer than 3 competitors, or any competitor that lacks a price field
or at least one source URL. CrewAI then re-prompts the agent with the error
message (up to ``guardrail_max_retries`` times).
"""

import json
from typing import Any

from pydantic import ValidationError

from app.crew.schemas import CompetitorList

MIN_COMPETITORS = 3


def _coerce(output: Any) -> CompetitorList:
    """Accept a CrewAI TaskOutput, a CompetitorList, a dict or a JSON string."""
    pyd = getattr(output, "pydantic", None)
    if isinstance(pyd, CompetitorList):
        return pyd
    if isinstance(output, CompetitorList):
        return output
    data: Any = getattr(output, "json_dict", None)
    if not data:
        raw = getattr(output, "raw", output)
        if isinstance(raw, dict):
            data = raw
        else:
            text = str(raw).strip()
            if text.startswith("```"):
                text = text.strip("`")
                text = text[text.find("{") :]
            data = json.loads(text[text.find("{") : text.rfind("}") + 1])
    return CompetitorList.model_validate(data)


def check_competitor_list(output: Any) -> list[str]:
    """Return a list of problems (empty == valid)."""
    try:
        parsed = _coerce(output)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return [f"Output is not a valid CompetitorList JSON object: {exc}"]

    problems: list[str] = []
    if len(parsed.competitors) < MIN_COMPETITORS:
        problems.append(
            f"Only {len(parsed.competitors)} competitors found; at least {MIN_COMPETITORS} real competitors "
            "operating in the city are required. Search again with different queries (aggregators, "
            "Swiggy/Zomato, Justdial, Instagram, Google Maps)."
        )
    names = [c.name.strip().lower() for c in parsed.competitors]
    if len(set(names)) != len(names):
        problems.append("Duplicate competitors listed; each competitor must be a distinct business.")
    for c in parsed.competitors:
        if not c.price_per_unit.strip():
            problems.append(
                f"Competitor '{c.name}' has no price. Give the price per unit, or 'Not publicly listed' "
                "and cite the page you checked."
            )
        if not c.source_urls:
            problems.append(f"Competitor '{c.name}' has no source URL.")
    return problems


def competitor_list_guardrail(output: Any) -> tuple[bool, Any]:
    """CrewAI guardrail signature: (TaskOutput) -> (success, result_or_error_message)."""
    problems = check_competitor_list(output)
    if problems:
        return False, "Rejected by guardrail: " + " ".join(problems)
    return True, output
