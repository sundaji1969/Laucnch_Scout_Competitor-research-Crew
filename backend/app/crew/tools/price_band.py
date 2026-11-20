"""Google Maps price levels as report text (kept free of heavy imports for the guardrails)."""

from __future__ import annotations

import re
from typing import Any


def price_band(level: Any) -> str | None:
    """Google's price level as words: its lowest band "₹1–200" really means "under ₹200"."""
    if not level:
        return None
    text = str(level).strip()
    m = re.fullmatch(r"(\D*)1\s*[–-]\s*(\d[\d,]*)", text)
    return f"under {m.group(1)}{m.group(2)}" if m else text
