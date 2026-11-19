"""Validated, sanitised user inputs for a crew run."""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field, field_validator

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TAGS = re.compile(r"<[^>]{0,200}>")
_BRACES = re.compile(r"[{}]")  # CrewAI uses {var} interpolation; never let users inject placeholders

MAX_COMPETITORS = 8


def clean_text(value: str, max_len: int | None = None) -> str:
    """Normalise and strip markup/placeholders. Length is enforced by the field, not truncated."""
    value = unicodedata.normalize("NFKC", value)
    value = _CONTROL.sub(" ", value)
    value = _TAGS.sub(" ", value)
    value = _BRACES.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len] if max_len is not None else value


class RunInputs(BaseModel):
    business_idea: str = Field(..., min_length=3, max_length=300)
    city: str = Field(..., min_length=2, max_length=80)
    target_customer: str = Field(..., min_length=2, max_length=300)
    known_competitors: list[str] = Field(default_factory=list, max_length=MAX_COMPETITORS)

    @field_validator("business_idea", "target_customer", "city", mode="before")
    @classmethod
    def _clean(cls, v: object) -> object:
        # Non-strings (e.g. null) fall through to pydantic's own type error.
        return clean_text(v) if isinstance(v, str) else v

    @field_validator("known_competitors", mode="before")
    @classmethod
    def _clean_competitors(cls, v: object) -> list[str]:
        items: list[str] = v.split(",") if isinstance(v, str) else list(v or [])  # type: ignore[call-overload]
        out: list[str] = []
        for item in items:
            c = clean_text(str(item), 80)
            if c and c.lower() not in {o.lower() for o in out}:
                out.append(c)
        return out[:MAX_COMPETITORS]

    def as_crew_inputs(self, run_id: str, output_dir: str, today: str) -> dict[str, str]:
        return {
            "business_idea": self.business_idea,
            "city": self.city,
            "target_customer": self.target_customer,
            "known_competitors": ", ".join(self.known_competitors) or "none given",
            "run_id": run_id,
            "output_dir": output_dir,
            "today": today,
        }
