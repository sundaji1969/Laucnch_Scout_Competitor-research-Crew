"""Anti-hallucination: sources must have appeared in a tool result during the run."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.crew import provenance
from app.crew.guardrails import check_competitor_list, check_review_insights
from app.services.report_validator import validate_report
from tests.fakes import COMPETITORS, REVIEWS

GOOD = (Path(__file__).parent / "fixtures" / "good_report.md").read_text(encoding="utf-8")


@pytest.fixture
def tracking() -> Iterator[None]:
    provenance.start()
    yield
    provenance.stop()


def _search_n(n: int) -> None:
    for _ in range(n):
        provenance.record_search()


def test_normalise_url() -> None:
    a = provenance.normalise_url("https://www.Zomato.com/coimbatore/greenbowl/")
    assert a == provenance.normalise_url("http://zomato.com/coimbatore/greenbowl")


def test_unseen_urls_rejected(tracking: None) -> None:
    _search_n(3)
    problems = check_competitor_list(COMPETITORS)
    assert len([p for p in problems if "appeared in your search" in p]) == 3


def test_answering_without_searching_rejected(tracking: None) -> None:
    for c in COMPETITORS["competitors"]:
        provenance.record_url(c["source_urls"][0])
    problems = check_competitor_list(COMPETITORS)
    assert problems == [p for p in problems if "web searches" in p]
    assert problems


def test_seen_urls_accepted(tracking: None) -> None:
    _search_n(3)
    provenance.record_text(" ".join(f'"{c["source_urls"][0]}"' for c in COMPETITORS["competitors"]))
    assert check_competitor_list(COMPETITORS) == []


def test_review_guardrail_checks_urls(tracking: None) -> None:
    assert check_review_insights(REVIEWS)
    provenance.record_url("https://www.swiggy.com/restaurants/millet-kitchen")
    assert check_review_insights(REVIEWS) == []


def test_validator_rejects_unseen_sources(tracking: None) -> None:
    r = validate_report(GOOD, is_known_url=provenance.was_seen)
    assert sum("never appeared" in e for e in r.errors) == 4
    provenance.record_text(GOOD)
    assert validate_report(GOOD, is_known_url=provenance.was_seen).ok


def test_tracking_off_is_permissive() -> None:
    provenance.stop()
    assert provenance.was_seen("https://anything.example")


def test_number_matching_ignores_separators(tracking: None) -> None:
    provenance.record_text("Plans from Rs. 1,299 per month. Cost for two ₹250")
    assert provenance.number_seen("1299")
    assert provenance.number_seen("1,299")
    assert provenance.number_seen("250.00")
    assert not provenance.number_seen("129")
    assert not provenance.number_seen("12999")
    assert provenance.unverified_numbers("₹180 per meal, ₹250 for two") == ["180"]


def test_invented_price_rejected_once_then_downgraded(tracking: None) -> None:
    import json as _json
    from types import SimpleNamespace

    from app.crew.guardrails import competitor_list_guardrail

    _search_n(3)
    urls = " ".join(c["source_urls"][0] for c in COMPETITORS["competitors"])
    # 180 appears, but far from "Millet Kitchen": a coincidental number must not count
    provenance.record_text(urls + " GreenBowl CBE salads ₹220 per bowl. " + "x" * 900 + " 180 calories")
    out = SimpleNamespace(pydantic=None, json_dict=COMPETITORS, raw="")
    ok, msg = competitor_list_guardrail(out)
    assert not ok
    assert "Millet Kitchen: 180" in msg
    ok, result = competitor_list_guardrail(out)
    assert ok
    data = _json.loads(result)
    mk = next(c for c in data["competitors"] if c["name"] == "Millet Kitchen")
    assert mk["price_per_unit"] == "Not publicly listed"
    assert "could not be verified" in mk["notes"]
    gb = next(c for c in data["competitors"] if c["name"] == "GreenBowl CBE")
    assert gb["price_per_unit"] == "₹220 per bowl"


def test_validator_rejects_unverified_table_price(tracking: None) -> None:
    provenance.record_text(GOOD.replace("₹180", "₹999"))
    r = validate_report(GOOD, unverified_price=provenance.unverified_price)
    assert any("Millet Kitchen" in e and "180" in e for e in r.errors)


def test_price_on_cited_page_counts(tracking: None) -> None:
    provenance.record_url("https://example.com/menu", "Daily thali 180. Weekly plan 1,050")
    assert provenance.unverified_price("Anything", "₹180 per meal", ["https://example.com/menu"]) == []
    assert provenance.unverified_price("Anything", "₹180 per meal", ["https://other.com"]) == ["180"]


def test_price_near_name_counts(tracking: None) -> None:
    provenance.record_text('{"title": "Mummy\'s Cloud Kitchen menu", "snippet": "Meals from ₹149"}')
    assert provenance.unverified_price("Mummy's Cloud Kitchen", "₹149 per meal") == []
    assert provenance.unverified_price("Other Kitchen Co", "₹149 per meal") == ["149"]
