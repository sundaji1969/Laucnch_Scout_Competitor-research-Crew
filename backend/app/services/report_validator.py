"""Post-run validation of the final markdown report.

Rules (from the product spec):
* All 6 required sections exist.
* Every ``[n]`` citation in the body maps to an entry in the numbered Sources list,
  and every source entry contains a real http(s) URL.
* The Key Competitors table has at least 3 competitor rows, each with a price
  cell and at least one citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

REQUIRED_SECTIONS: list[tuple[str, str]] = [
    ("key_competitors", "Key Competitors"),
    ("complaints", "What Customers Complain About"),
    ("market_gap", "Market Gap"),
    ("positioning", "Recommended Positioning"),
    ("launch_plan", "30-Day Launch Plan"),
    ("sources", "Sources"),
]

_HEADING_RE = re.compile(r"^(#{1,3})\s+(?:\d+[.)]\s*)?(.+?)\s*#*\s*$", re.MULTILINE)
_CITATION_RE = re.compile(r"\[(\d{1,3})\](?!\()")
_SOURCE_LINE_RE = re.compile(r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[.)])\s+(.*)$")
_URL_RE = re.compile(r"https?://[^\s)>\]]+")


class ReportValidationError(Exception):
    """Raised when a report fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Report failed validation: " + "; ".join(errors))


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    sources: dict[int, str] = field(default_factory=dict)
    citations: set[int] = field(default_factory=set)
    competitor_rows: int = 0


def _normalise(title: str) -> str:
    title = re.sub(r"[*_`]", "", title).strip().lower()
    title = title.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", title)


def split_sections(markdown: str) -> dict[str, str]:
    """Map each required section key to its body text (text until the next heading of same/higher level)."""
    headings = list(_HEADING_RE.finditer(markdown))
    found: dict[str, str] = {}
    for i, h in enumerate(headings):
        title = _normalise(h.group(2))
        for key, wanted in REQUIRED_SECTIONS:
            if key in found:
                continue
            w = _normalise(wanted)
            if (
                title == w
                or title.startswith(w)
                or (key == "launch_plan" and "30" in title and "plan" in title)
            ):
                level = len(h.group(1))
                end = len(markdown)
                for nxt in headings[i + 1 :]:
                    if len(nxt.group(1)) <= level:
                        end = nxt.start()
                        break
                found[key] = markdown[h.end() : end].strip()
                break
    return found


def parse_sources(sources_body: str) -> dict[int, str]:
    sources: dict[int, str] = {}
    for line in sources_body.splitlines():
        m = _SOURCE_LINE_RE.match(line)
        if not m:
            continue
        n = int(m.group(1) or m.group(2))
        sources[n] = m.group(3).strip()
    return sources


def _table_rows(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue  # separator row
        rows.append(cells)
    return rows


def validate_report(markdown: str, min_competitors: int = 3) -> ValidationResult:
    errors: list[str] = []
    sections = split_sections(markdown)

    for key, title in REQUIRED_SECTIONS:
        if key not in sections:
            errors.append(f"Missing section: '{title}'")

    sources = parse_sources(sections.get("sources", ""))
    if "sources" in sections and not sources:
        errors.append("Sources section has no numbered entries")
    for n, text in sources.items():
        if not _URL_RE.search(text):
            errors.append(f"Source [{n}] has no http(s) URL")

    body_without_sources = markdown
    if "sources" in sections:
        idx = markdown.rfind(sections["sources"])
        if idx > 0:
            body_without_sources = markdown[:idx]
    citations = {int(c) for c in _CITATION_RE.findall(body_without_sources)}
    if not citations:
        errors.append("Report body contains no [n] citations")
    missing = sorted(c for c in citations if c not in sources)
    if missing:
        errors.append("Citations without a matching source: " + ", ".join(f"[{c}]" for c in missing))

    competitor_rows = 0
    rows = _table_rows(sections.get("key_competitors", ""))
    if rows:
        header = [c.lower() for c in rows[0]]
        price_idx = next((i for i, c in enumerate(header) if "price" in c), None)
        for r in rows[1:]:
            competitor_rows += 1
            name = r[0] if r else "?"
            if price_idx is None or price_idx >= len(r) or not r[price_idx]:
                errors.append(f"Competitor '{name}' has no price cell")
            if not _CITATION_RE.search(" ".join(r)):
                errors.append(f"Competitor '{name}' row has no [n] citation")
        if price_idx is None:
            errors.append("Key Competitors table has no Price column")
    elif "key_competitors" in sections:
        errors.append("Key Competitors section has no table")
    if "key_competitors" in sections and competitor_rows < min_competitors:
        errors.append(f"Only {competitor_rows} competitors in table (need at least {min_competitors})")

    return ValidationResult(
        ok=not errors,
        errors=errors,
        sections=sections,
        sources=sources,
        citations=citations,
        competitor_rows=competitor_rows,
    )


def assert_valid_report(markdown: str) -> ValidationResult:
    result = validate_report(markdown)
    if not result.ok:
        raise ReportValidationError(result.errors)
    return result
