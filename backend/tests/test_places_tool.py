"""Google Maps price lookup (Serper Places): output format, provenance, failure handling."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.crew import provenance
from app.crew.progress import describe_tool_call, summarise_tool_result
from app.crew.tools.safe_tools import format_places, places_tool

PLACES = [
    {
        "title": "Millet Life",
        "priceLevel": "₹200–400",
        "rating": 4.3,
        "ratingCount": 118,
        "category": "Health Food",
        "address": "RS Puram, Coimbatore",
        "cid": "1234567890",
        "website": "https://milletlife.example",
    },
    {
        "title": "Annam Iyarkai Unavakam",
        "rating": 4.6,
        "ratingCount": 52,
        "category": "South Indian",
        "cid": "42",
    },
]


class _Resp:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self._payload, self.status_code = payload, status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=httpx.Request("POST", "x"), response=None)  # type: ignore[arg-type]

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.fixture
def tracking() -> Iterator[None]:
    provenance.start()
    yield
    provenance.stop()


def test_format_keeps_name_and_price_on_one_line() -> None:
    text = format_places("millet Coimbatore", PLACES)
    first, second = text.splitlines()[1:3]
    assert first.startswith("1. Millet Life | price ₹200–400 per person (Google Maps)")
    assert "rating 4.3 (118 reviews)" in first
    assert "maps: https://www.google.com/maps?cid=1234567890" in first
    assert "price not shown on Google Maps" in second
    assert "No Google Maps listing" in format_places("nothing", [])


def test_lookup_records_evidence_for_the_right_business(
    monkeypatch: pytest.MonkeyPatch, tracking: None
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, **kw: Any) -> _Resp:
        calls.append({"url": url, **kw})
        return _Resp({"places": PLACES})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = places_tool(api_key="k", country="in")._run(query="Millet Life Coimbatore")
    assert "₹200–400" in out
    assert calls[0]["json"] == {"q": "Millet Life Coimbatore", "gl": "in", "hl": "en"}
    assert calls[0]["headers"]["X-API-KEY"] == "k"
    assert provenance.search_calls() == 1
    maps = "https://www.google.com/maps?cid=1234567890"
    assert provenance.was_seen(maps)
    # The range verifies for the business it was listed next to, not for an unrelated name.
    assert provenance.unverified_price("Millet Life", "₹200–400 per person (Google Maps)", [maps]) == []
    assert provenance.unverified_price("Some Other Kitchen", "₹200–400 per person", []) == ["200", "400"]


def test_failure_returns_a_message_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch, tracking: None
) -> None:
    def boom(url: str, **kw: Any) -> _Resp:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    out = places_tool(api_key="k")._run(query="Millet Life Coimbatore")
    assert out.startswith("PLACES LOOKUP FAILED")
    assert summarise_tool_result("local_price_lookup", out) == "PLACES LOOKUP FAILED"


def test_progress_feed_lines() -> None:
    assert describe_tool_call("local_price_lookup", {"query": "Millet Life Coimbatore"}) == (
        "Checking Google Maps: Millet Life Coimbatore"
    )
    text = format_places("q", PLACES)
    assert (
        summarise_tool_result("local_price_lookup", text) == "2 Google Maps listings · 1 with a price range"
    )


# ---------------------------------------------------------------- guardrail fill-in

from types import SimpleNamespace  # noqa: E402

from app.crew.guardrails import competitor_list_guardrail, fill_prices_from_maps, set_price_lookup  # noqa: E402
from app.crew.schemas import NOT_LISTED, CompetitorList  # noqa: E402
from app.crew.tools.price_band import price_band  # noqa: E402

MAPS_PLACES = {
    "MBF Millet Mothers Coimbatore": [
        {"title": "Millet Mothers", "priceLevel": "₹1–200", "cid": "111", "rating": 4.5, "ratingCount": 40}
    ],
    "Mealzy Coimbatore": [
        # A different business with a price, then Mealzy without one: neither may be used.
        {"title": "Meals on Wheels", "priceLevel": "₹200–400", "cid": "222"},
        {"title": "Mealzy", "cid": "333"},
    ],
}


def _fake_places(url: str, **kw: Any) -> _Resp:
    return _Resp({"places": MAPS_PLACES.get(kw["json"]["q"], [])})


THREE = (("MBF Millet Mothers", NOT_LISTED), ("Mealzy", NOT_LISTED), ("Millet Express", "₹120 per meal"))


def _competitors(*names_prices: tuple[str, str]) -> CompetitorList:
    return CompetitorList.model_validate(
        {
            "business_idea": "millet meals",
            "city": "Coimbatore",
            "competitors": [
                {"name": n, "price_per_unit": p, "source_urls": [f"https://{n.split()[0].lower()}.example/"]}
                for n, p in names_prices
            ],
        }
    )


def test_price_band_wording() -> None:
    assert price_band("₹1–200") == "under ₹200"
    assert price_band("₹200–400") == "₹200–400"
    assert price_band("₹1,000+") == "₹1,000+"
    assert price_band(None) is None


def test_fill_in_uses_only_matching_priced_listings(monkeypatch: pytest.MonkeyPatch, tracking: None) -> None:
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Resp({"places": MAPS_PLACES.get(kw["json"]["q"], [])})
    )
    set_price_lookup(places_tool(api_key="k").lookup)
    parsed = _competitors(
        ("MBF Millet Mothers", NOT_LISTED), ("Mealzy", NOT_LISTED), ("Millet Express", "₹120 per meal")
    )
    filled, count = fill_prices_from_maps(parsed)
    mothers, mealzy, express = filled.competitors
    assert count == 1
    assert mothers.price_per_unit == "under ₹200 per person (Google Maps)"
    assert mothers.price_value is None
    assert [str(u) for u in mothers.source_urls][-1] == "https://www.google.com/maps?cid=111"
    assert "Google Maps' typical spend" in mothers.notes
    assert mealzy.price_per_unit == NOT_LISTED  # Meals on Wheels is another business; Mealzy has no band
    assert express.price_per_unit == "₹120 per meal"  # already priced: not looked up
    assert provenance.search_calls() == 2
    # The filled price passes the same provenance check the report validator uses, even though
    # the Maps listing is named "Millet Mothers": its exact Maps link is cited on the same line.
    urls = [str(u) for u in mothers.source_urls]
    assert provenance.unverified_price(mothers.name, mothers.price_per_unit, urls) == []
    # ...but citing a different listing's link does not verify it.
    assert provenance.unverified_price(
        "Someone Else", "under ₹200", ["https://www.google.com/maps?cid=999"]
    ) == ["200"]


def test_guardrail_returns_filled_json(monkeypatch: pytest.MonkeyPatch, tracking: None) -> None:
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: _Resp({"places": MAPS_PLACES.get(kw["json"]["q"], [])})
    )
    for _ in range(3):
        provenance.record_search()  # the guardrail requires real searching first
    for u in ("https://mbf.example/", "https://mealzy.example/", "https://millet.example/"):
        provenance.record_url(u)
    provenance.record_text("Millet Express ₹120 per meal", ref="q")
    set_price_lookup(places_tool(api_key="k").lookup)
    parsed = _competitors(
        ("MBF Millet Mothers", NOT_LISTED), ("Mealzy", NOT_LISTED), ("Millet Express", "₹120 per meal")
    )
    ok, result = competitor_list_guardrail(SimpleNamespace(pydantic=parsed))
    assert ok and isinstance(result, str)
    out = CompetitorList.model_validate_json(result)
    assert out.competitors[0].price_per_unit == "under ₹200 per person (Google Maps)"


def test_no_fill_in_when_disabled() -> None:
    parsed = _competitors(
        ("MBF Millet Mothers", NOT_LISTED), ("a b c d e", NOT_LISTED), ("f g h i j", NOT_LISTED)
    )
    assert fill_prices_from_maps(parsed) == (parsed, 0)
