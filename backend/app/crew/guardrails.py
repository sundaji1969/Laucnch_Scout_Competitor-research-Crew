"""CrewAI task guardrails.

``competitor_list_guardrail`` is attached to task 1 (market research). It rejects
output with fewer than 3 competitors, or any competitor that lacks a price field
or at least one source URL. CrewAI then re-prompts the agent with the error
message (up to ``guardrail_max_retries`` times).
"""

import json
from typing import Any

from pydantic import ValidationError

from app.crew import provenance
from app.crew.schemas import NOT_LISTED, CompetitorList, ReviewInsights

MIN_COMPETITORS = 3
MIN_SEARCHES = 3


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
        else:
            bad = provenance.unseen(str(u) for u in c.source_urls)
            if bad and len(bad) == len(c.source_urls):
                problems.append(
                    f"Competitor '{c.name}': none of its source URLs ({', '.join(bad[:3])}) appeared in your "
                    "search or scrape results. Use the search tool to find this business and copy the URLs "
                    "exactly as returned, or drop it if you cannot find evidence that it exists."
                )
    if provenance.is_active() and provenance.search_calls() < MIN_SEARCHES:
        problems.append(
            f"You ran {provenance.search_calls()} web searches. Run at least {MIN_SEARCHES} searches with "
            "the search tool before answering; do not answer from memory."
        )
    return problems


def unverified_prices(parsed: CompetitorList) -> dict[str, list[str]]:
    """Competitor name -> numbers in its price that never appeared in a tool result."""
    bad: dict[str, list[str]] = {}
    for c in parsed.competitors:
        if c.price_per_unit.strip().lower() == NOT_LISTED.lower():
            continue
        nums = provenance.unverified_price(c.name, c.price_per_unit, (str(u) for u in c.source_urls))
        if nums:
            bad[c.name] = nums
    return bad


def downgrade_unverified_prices(parsed: CompetitorList, bad: dict[str, list[str]]) -> CompetitorList:
    """Replace prices that cannot be traced to a tool result with 'Not publicly listed'."""
    comps = []
    for c in parsed.competitors:
        if c.name in bad:
            note = f"Price claim '{c.price_per_unit}' could not be verified in the sources checked."
            c = c.model_copy(
                update={
                    "price_per_unit": NOT_LISTED,
                    "price_value": None,
                    "notes": f"{c.notes} {note}".strip(),
                }
            )
        comps.append(c)
    return parsed.model_copy(update={"competitors": comps})


def competitor_list_guardrail(output: Any) -> tuple[bool, Any]:
    """CrewAI guardrail signature: (TaskOutput) -> (success, result_or_error_message).

    Structural problems (too few competitors, missing price/source, unseen URLs) are always
    rejected so the agent researches again. Prices whose numbers never appeared in a tool
    result are rejected once with specific feedback; if the agent still cannot back them up,
    they are downgraded to "Not publicly listed" instead of failing the whole run.
    """
    problems = check_competitor_list(output)
    if problems:
        return False, "Rejected by guardrail: " + " ".join(problems)
    parsed = _coerce(output)
    bad = unverified_prices(parsed)
    if bad:
        if provenance.note_price_rejection() <= 1:
            detail = "; ".join(f"{name}: {', '.join(nums)}" for name, nums in bad.items())
            return False, (
                "Rejected by guardrail: these prices could not be found next to the competitor's name in "
                f"any search result, nor on a page cited for it ({detail}). Find the page that states the "
                "competitor's own price, add it to source_urls and copy the price exactly, or set the price "
                f"to '{NOT_LISTED}' and cite the page you checked. Never estimate a price."
            )
        return True, downgrade_unverified_prices(parsed, bad).model_dump_json()
    _attach(output, parsed)
    return True, output


def _coerce_reviews(output: Any) -> ReviewInsights:
    pyd = getattr(output, "pydantic", None)
    if isinstance(pyd, ReviewInsights):
        return pyd
    if isinstance(output, ReviewInsights):
        return output
    data: Any = getattr(output, "json_dict", None)
    if not data:
        raw = getattr(output, "raw", output)
        text = raw if isinstance(raw, str) else json.dumps(raw)
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
    return ReviewInsights.model_validate(data)


def check_review_insights(output: Any) -> list[str]:
    try:
        parsed = _coerce_reviews(output)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return [f"Output is not a valid ReviewInsights JSON object: {exc}"]
    urls: list[str] = []
    for r in parsed.reviews:
        for like in r.likes:
            urls.extend(str(u) for u in like.source_urls)
        for complaint in r.complaints:
            urls.extend(str(u) for u in complaint.source_urls)
    for p in parsed.common_pain_points:
        urls.extend(str(u) for u in p.source_urls)
    bad = sorted(set(provenance.unseen(urls)))
    if bad:
        return [
            "These source URLs never appeared in your search or scrape results, so the reviews they "
            "support cannot be verified: " + ", ".join(bad[:6]) + ". Search for the reviews and cite "
            "the URLs exactly as returned, or remove the unsupported items."
        ]
    if not parsed.common_pain_points:
        return ["No common pain points found; list the recurring complaints with their sources."]
    return []


def review_insights_guardrail(output: Any) -> tuple[bool, Any]:
    problems = check_review_insights(output)
    if problems:
        return False, "Rejected by guardrail: " + " ".join(problems)
    _attach(output, _coerce_reviews(output))
    return True, output


def _attach(output: Any, parsed: Any) -> None:
    """CrewAI keeps a TaskOutput returned by a guardrail as-is; make sure .pydantic is populated."""
    if hasattr(output, "pydantic") and getattr(output, "pydantic", None) is None:
        try:
            output.pydantic = parsed
            output.json_dict = parsed.model_dump(mode="json")
        except (AttributeError, ValueError, TypeError):
            pass
