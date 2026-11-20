"""URL provenance: which URLs did the crew actually see in tool results during this run?

LLMs can answer "from memory" and skip the tools entirely. Every URL that appears in a
Serper result or that was scraped is recorded here; guardrails and the final validator
reject sources that never appeared in a tool result. That turns "no invented
competitors / sources" from a prompt instruction into an enforced check.

One crew runs per process (see docs/DECISIONS.md), so a module-level registry is safe.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from urllib.parse import unquote, urlsplit

_URL_RE = re.compile(r"https?://[^\s\"'<>)\]},]+")
_lock = threading.Lock()
_seen: set[str] = set()
_active = False
_search_calls = 0
_corpus: list[tuple[str, str, str]] = []  # (kind, ref, text)
_corpus_chars = 0
_evidence: list[dict[str, str]] = []
_price_rejections = 0
MAX_CORPUS_CHARS = 4_000_000
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalise_url(url: str) -> str:
    url = unquote(str(url).strip().rstrip(".,;"))
    try:
        parts = urlsplit(url)
    except ValueError:
        return url.lower()
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parts.path.rstrip("/")
    return f"{host}{path}".lower()


def start(seed: Iterable[str] = ()) -> None:
    """Begin tracking for a new run (clears previous state)."""
    global _active, _search_calls, _corpus_chars, _price_rejections
    with _lock:
        _seen.clear()
        _corpus.clear()
        _evidence.clear()
        _corpus_chars = 0
        _price_rejections = 0
        _active = True
        _search_calls = 0
        _seen.update(normalise_url(u) for u in seed)


def stop() -> None:
    global _active
    with _lock:
        _active = False


def is_active() -> bool:
    return _active


def _add_corpus(kind: str, ref: str, text: str) -> None:
    global _corpus_chars
    if _corpus_chars >= MAX_CORPUS_CHARS:
        return
    _corpus.append((kind, ref, text))
    _corpus_chars += len(text)
    _evidence.append({"tool": kind, "input": ref[:500], "output": text})


def record_text(text: str, kind: str = "search", ref: str = "") -> None:
    if not _active:
        return
    urls = _URL_RE.findall(text)
    with _lock:
        _seen.update(normalise_url(u) for u in urls)
        _add_corpus(kind, ref, text)


def record_url(url: str, text: str = "") -> None:
    if _active and url:
        with _lock:
            _seen.add(normalise_url(url))
            if text:
                _add_corpus("scrape", url, text)


def evidence() -> list[dict[str, str]]:
    return list(_evidence)


def _digits(num: str) -> str:
    return num.replace(",", "").rstrip(".")


NAME_WINDOW = 400  # chars around a number in which the competitor's name must appear


def _number_pattern(num: str) -> re.Pattern[str]:
    target = _digits(num)
    if "." in target:
        target = target.rstrip("0").rstrip(".")
    body = r",?".join(re.escape(ch) for ch in target)
    return re.compile(r"(?<![\d.,])" + body + r"(?:\.0+)?(?![\d,]*\d)")


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def name_key(name: str) -> str:
    """'Mummy's Cloud Kitchen (Aggregator)' -> 'mummyscloudkitchen' (also matches its domain)."""
    return _alnum(re.sub(r"\(.*?\)", "", name))


def number_seen(num: str) -> bool:
    """True if the number (ignoring thousands separators) appears in any tool output."""
    if not _active:
        return True
    pat = _number_pattern(num)
    return any(pat.search(text) for _, _, text in _corpus)


def number_seen_for(num: str, name: str, urls: Iterable[str] = ()) -> bool:
    """True if ``num`` appears on a page cited for this competitor, or near its name in any tool output.

    A bare "the number occurs somewhere" check is too weak: common numbers like 180 or 200
    turn up by coincidence. Requiring the competitor's name nearby (or the competitor's own
    cited page) ties the price to the business it is attributed to.
    """
    if not _active:
        return True
    pat = _number_pattern(num)
    key = name_key(name)
    raw_cited = [str(u).strip() for u in urls if str(u).strip()]
    cited = {normalise_url(u) for u in raw_cited}
    for kind, ref, text in _corpus:
        matches = list(pat.finditer(text))
        if not matches:
            continue
        if kind == "scrape" and normalise_url(ref) in cited:
            return True
        if kind == "places" and raw_cited:
            # A Google Maps line holds one listing: its price and its exact Maps link. Citing
            # that link ties the price to the listing even if the names differ slightly.
            for m in matches:
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start : line_end if line_end >= 0 else len(text)]
                if any(u in line for u in raw_cited):
                    return True
        if len(key) < 4:
            continue
        for m in matches:
            window = text[max(0, m.start() - NAME_WINDOW) : m.end() + NAME_WINDOW]
            if key in _alnum(window):
                return True
    return False


def _price_numbers(text: str, min_value: float) -> list[str]:
    out: list[str] = []
    for n in _NUM_RE.findall(text):
        try:
            value = float(_digits(n))
        except ValueError:
            continue
        if value >= min_value:
            out.append(n)
    return out


def unverified_numbers(text: str, min_value: float = 10) -> list[str]:
    """Numbers (>= min_value) in ``text`` that never appeared in any tool result."""
    return [n for n in _price_numbers(text, min_value) if not number_seen(n)]


def unverified_price(
    name: str, price_text: str, urls: Iterable[str] = (), min_value: float = 10
) -> list[str]:
    """Numbers in a competitor's price that cannot be tied to that competitor in the evidence."""
    url_list = [str(u) for u in urls]
    return [n for n in _price_numbers(price_text, min_value) if not number_seen_for(n, name, url_list)]


def note_price_rejection() -> int:
    global _price_rejections
    with _lock:
        _price_rejections += 1
        return _price_rejections


def record_search() -> None:
    global _search_calls
    with _lock:
        _search_calls += 1


def search_calls() -> int:
    return _search_calls


def was_seen(url: str) -> bool:
    """True when tracking is off (e.g. unit tests) or the URL appeared in a tool result."""
    if not _active:
        return True
    return normalise_url(url) in _seen


def unseen(urls: Iterable[str]) -> list[str]:
    return [str(u) for u in urls if not was_seen(str(u))]
