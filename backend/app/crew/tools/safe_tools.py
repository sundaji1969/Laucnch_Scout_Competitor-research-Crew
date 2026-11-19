"""Fault-tolerant wrappers around the crewai-tools used by the crew.

If Serper rate-limits us or a site blocks scraping, the wrapped tool returns a
short error string instead of raising. The agent sees the error and moves on to
other queries or sources, so one bad page never crashes the run.
"""

from __future__ import annotations

import logging
from typing import Any

from crewai_tools import ScrapeWebsiteTool, SerperDevTool

log = logging.getLogger("launchscout.tools")

MAX_SCRAPE_CHARS = 12_000


class SafeSerperDevTool(SerperDevTool):  # type: ignore[misc]
    """SerperDevTool that never raises."""

    def _run(self, **kwargs: Any) -> Any:
        try:
            return super()._run(**kwargs)
        except Exception as exc:  # noqa: BLE001 - deliberate: tools must not crash the crew
            log.warning("serper_failed", extra={"error": str(exc)[:300], "query": str(kwargs)[:200]})
            return (
                f"SEARCH FAILED ({type(exc).__name__}: {str(exc)[:200]}). "
                "Try a different query or continue with the sources you already have."
            )


class SafeScrapeWebsiteTool(ScrapeWebsiteTool):  # type: ignore[misc]
    """ScrapeWebsiteTool that never raises and truncates very long pages."""

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
        text = str(text)
        if len(text) > MAX_SCRAPE_CHARS:
            text = text[:MAX_SCRAPE_CHARS] + "\n...[truncated]"
        return text


def search_tool(country: str = "in", locale: str = "en", n_results: int = 10) -> SafeSerperDevTool:
    return SafeSerperDevTool(country=country, locale=locale, n_results=n_results)


def scrape_tool() -> SafeScrapeWebsiteTool:
    return SafeScrapeWebsiteTool()
