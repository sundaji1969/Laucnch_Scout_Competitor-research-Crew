"""Fault-tolerant, cost-aware wrappers around the crewai-tools used by the crew.

* Never raise: if Serper rate-limits us or a site blocks scraping, the tool returns a short
  error string and the agent moves on to other sources.
* Keep context small: everything a tool returns is re-sent to the LLM on every later step of
  the agent's loop, so scraped pages are whitespace-collapsed and capped (SCRAPE_MAX_CHARS).
* Cache identical searches in Redis for SEARCH_CACHE_TTL_SECONDS (saves Serper calls and makes
  repeated research of the same market consistent). Cache failures are ignored.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
from typing import Any

import httpx
from crewai.tools import BaseTool
from crewai_tools import ScrapeWebsiteTool, SerperDevTool
from pydantic import BaseModel, Field

from app.crew import provenance

log = logging.getLogger("launchscout.tools")

DEFAULT_SCRAPE_CHARS = 5_000
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def compact(text: str) -> str:
    """Collapse runs of spaces and blank lines (scraped pages are mostly whitespace)."""
    return _BLANK_LINES.sub("\n", _WS.sub(" ", text)).strip()


class SafeSerperDevTool(SerperDevTool):  # type: ignore[misc]
    """SerperDevTool that never raises and caches identical queries in Redis."""

    cache_ttl: int = 0
    redis_url: str = ""

    def _cache_key(self, kwargs: dict[str, Any]) -> str:
        ident = json.dumps(
            {"q": kwargs, "country": self.country, "locale": self.locale, "n": self.n_results},
            sort_keys=True,
            default=str,
        )
        return "launchscout:serper:" + hashlib.sha256(ident.encode()).hexdigest()

    def _cache(self) -> Any | None:
        if not (self.cache_ttl and self.redis_url):
            return None
        try:
            import redis

            return redis.Redis.from_url(self.redis_url, socket_timeout=2, socket_connect_timeout=2)
        except Exception:  # noqa: BLE001 - cache is optional
            return None

    def _run(self, **kwargs: Any) -> Any:
        provenance.record_search()
        query = str(kwargs.get("search_query", ""))
        cache = self._cache()
        key = self._cache_key(kwargs)
        if cache is not None:
            try:
                hit = cache.get(key)
                if hit:
                    text = hit.decode() if isinstance(hit, bytes) else str(hit)
                    provenance.record_text(text, kind="search", ref=query)
                    return json.loads(text)
            except Exception:  # noqa: BLE001
                log.info("search_cache_unavailable")
        try:
            result = super()._run(**kwargs)
        except Exception as exc:  # noqa: BLE001 - deliberate: tools must not crash the crew
            log.warning("serper_failed", extra={"error": str(exc)[:300], "query": query[:200]})
            return (
                f"SEARCH FAILED ({type(exc).__name__}: {str(exc)[:200]}). "
                "Try a different query or continue with the sources you already have."
            )
        text = _as_text(result)
        provenance.record_text(text, kind="search", ref=query)
        if cache is not None:
            with contextlib.suppress(Exception):  # cache is optional
                cache.setex(key, self.cache_ttl, text)
        return result


class SafeScrapeWebsiteTool(ScrapeWebsiteTool):  # type: ignore[misc]
    """ScrapeWebsiteTool that never raises and returns compact, capped page text."""

    max_chars: int = DEFAULT_SCRAPE_CHARS

    def _run(self, **kwargs: Any) -> Any:
        url = kwargs.get("website_url") or getattr(self, "website_url", None)
        try:
            text = super()._run(**kwargs)
        except Exception as exc:  # noqa: BLE001
            log.warning("scrape_failed", extra={"error": str(exc)[:300], "url": str(url)[:300]})
            return (
                f"SCRAPE FAILED for {url} ({type(exc).__name__}). The site may block bots. "
                "Use the search result snippet for this page or try another source."
            )
        text = compact(str(text))
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + "\n...[truncated]"
        # Record exactly what the agent saw: provenance must not credit text it never read.
        provenance.record_url(str(url or ""), text)
        return text


class PlacesQuery(BaseModel):
    query: str = Field(..., description='Business name and city, e.g. "Millet Life Coimbatore"')


class LocalPriceTool(BaseTool):  # type: ignore[misc]
    """Google Maps facts for a local business, via Serper's Places endpoint (no scraping).

    Many food businesses sell only through Swiggy/Zomato, whose menus can't be read without
    a browser (and whose terms forbid scraping). Google Maps publishes a typical price per
    person for most of them ("₹200–400"), plus rating and review count. Each result line
    keeps the business name next to its price, so provenance can tie the price to the
    business, and a Google Maps link the report can cite.
    """

    name: str = "local_price_lookup"
    description: str = (
        "Look up a local business on Google Maps. Returns up to 5 matches, each with its "
        "typical price per person (Google's price range, mainly for food places), rating, "
        "review count, category, address, website and a Google Maps link you can cite. "
        'Input: the business name and city, e.g. "Millet Life Coimbatore".'
    )
    args_schema: type[BaseModel] = PlacesQuery
    api_key: str = ""
    country: str = "in"
    locale: str = "en"
    cache_ttl: int = 0
    redis_url: str = ""
    endpoint: str = "https://google.serper.dev/places"

    def _cache(self) -> Any | None:
        if not (self.cache_ttl and self.redis_url):
            return None
        try:
            import redis

            return redis.Redis.from_url(self.redis_url, socket_timeout=2, socket_connect_timeout=2)
        except Exception:  # noqa: BLE001 - cache is optional
            return None

    def _run(self, query: str = "", **_: Any) -> str:
        query = str(query).strip()[:200]
        if not query:
            return "Give a business name and city, e.g. 'Millet Life Coimbatore'."
        provenance.record_search()
        key = (
            "launchscout:places:"
            + hashlib.sha256(json.dumps([query, self.country, self.locale]).encode()).hexdigest()
        )
        cache = self._cache()
        if cache is not None:
            with contextlib.suppress(Exception):
                hit = cache.get(key)
                if hit:
                    text = hit.decode() if isinstance(hit, bytes) else str(hit)
                    provenance.record_text(text, kind="places", ref=query)
                    return text
        api_key = self.api_key or os.environ.get("SERPER_API_KEY", "")
        try:
            resp = httpx.post(
                self.endpoint,
                json={"q": query, "gl": self.country, "hl": self.locale},
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                timeout=20,
            )
            resp.raise_for_status()
            places = resp.json().get("places") or []
        except Exception as exc:  # noqa: BLE001 - tools must not crash the crew
            log.warning("places_failed", extra={"error": str(exc)[:300], "query": query})
            return (
                f"PLACES LOOKUP FAILED ({type(exc).__name__}). "
                "Use web search results for this business instead."
            )
        text = format_places(query, places)
        provenance.record_text(text, kind="places", ref=query)
        if cache is not None:
            with contextlib.suppress(Exception):
                cache.setex(key, self.cache_ttl, text)
        return text


def format_places(query: str, places: list[dict[str, Any]], limit: int = 5) -> str:
    """One line per place, name first, so a price always sits next to its business."""
    if not places:
        return f"No Google Maps listing found for '{query}'. Try a shorter name or web search."
    lines = [f"Google Maps results for '{query}':"]
    for i, p in enumerate(places[:limit], 1):
        title = str(p.get("title") or "Unknown")
        price = p.get("priceLevel")
        parts = [f"{i}. {title}"]
        parts.append(f"price {price} per person (Google Maps)" if price else "price not shown on Google Maps")
        if p.get("rating") is not None:
            parts.append(f"rating {p['rating']} ({p.get('ratingCount', 0)} reviews)")
        for field in ("category", "address"):
            if p.get(field):
                parts.append(str(p[field]))
        if p.get("cid"):
            parts.append(f"maps: https://www.google.com/maps?cid={p['cid']}")
        if p.get("website"):
            parts.append(f"website: {p['website']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _as_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        result = result.model_dump()
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


def search_tool(
    country: str = "in",
    locale: str = "en",
    n_results: int = 6,
    cache_ttl: int = 0,
    redis_url: str = "",
) -> SafeSerperDevTool:
    return SafeSerperDevTool(
        country=country, locale=locale, n_results=n_results, cache_ttl=cache_ttl, redis_url=redis_url
    )


def scrape_tool(max_chars: int = DEFAULT_SCRAPE_CHARS) -> SafeScrapeWebsiteTool:
    return SafeScrapeWebsiteTool(max_chars=max_chars)


def places_tool(
    api_key: str = "",
    country: str = "in",
    locale: str = "en",
    cache_ttl: int = 0,
    redis_url: str = "",
) -> LocalPriceTool:
    return LocalPriceTool(
        api_key=api_key, country=country, locale=locale, cache_ttl=cache_ttl, redis_url=redis_url
    )
