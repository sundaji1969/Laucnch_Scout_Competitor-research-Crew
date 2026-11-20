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
    assert summarise_tool_result("local_price_lookup", out) == "PLACES LOOKUP FAILED (ConnectError)"


def test_progress_feed_lines() -> None:
    assert describe_tool_call("local_price_lookup", {"query": "Millet Life Coimbatore"}) == (
        "Checking Google Maps: Millet Life Coimbatore"
    )
    text = format_places("q", PLACES)
    assert (
        summarise_tool_result("local_price_lookup", text) == "2 Google Maps listings · 1 with a price range"
    )
