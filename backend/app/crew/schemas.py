"""Structured outputs for the LaunchScout crew (tasks 1-3).

Every competitor-level fact carries ``source_urls`` so the final report can cite
real pages. "Not publicly listed" is an explicitly allowed price value, as long
as the page that was checked is cited.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, WithJsonSchema, field_validator
from pydantic import HttpUrl as _HttpUrl

NOT_LISTED = "Not publicly listed"

# Validated as a real http(s) URL at runtime, but advertised to the LLM as a plain string:
# OpenAI structured outputs reject JSON-schema `format: uri`.
HttpUrl = Annotated[
    _HttpUrl, WithJsonSchema({"type": "string", "description": "Full http(s) URL copied from a tool result"})
]


class Competitor(BaseModel):
    """A real competitor found by the Market Researcher."""

    name: str = Field(..., min_length=1, description="Business / brand name exactly as it appears online")
    website: HttpUrl | None = Field(None, description="Official website or main listing URL, if any")
    price_per_unit: str = Field(
        ...,
        min_length=1,
        description=(
            "Price per unit / meal / session as found, with currency and unit, e.g. '₹149 per meal'. "
            f"Use '{NOT_LISTED}' if no price could be found."
        ),
    )
    price_value: float | None = Field(
        None, description="Numeric price in local currency for one unit, or null if not listed"
    )
    currency: str = Field("INR", description="ISO currency code of price_value")
    offers: list[str] = Field(
        default_factory=list, description="Current offers, plans, discounts, subscriptions"
    )
    sales_channels: list[str] = Field(
        default_factory=list,
        description="Where they sell: own website, Swiggy, Zomato, Instagram, WhatsApp, physical store, etc.",
    )
    notes: str = Field("", description="Short factual notes (location, positioning) — no speculation")
    source_urls: list[HttpUrl] = Field(
        ..., min_length=1, description="Pages where the facts above were found (at least one)"
    )

    @field_validator("price_per_unit")
    @classmethod
    def _strip_price(cls, v: str) -> str:
        return v.strip()

    @property
    def has_price(self) -> bool:
        return bool(self.price_per_unit)


class CompetitorList(BaseModel):
    """Output of task 1 (market research)."""

    business_idea: str
    city: str
    competitors: list[Competitor] = Field(..., description="3 to 5 real competitors operating in the city")
    search_queries_used: list[str] = Field(default_factory=list)


class Complaint(BaseModel):
    text: str = Field(..., description="The complaint, paraphrased faithfully from real reviews")
    source_urls: list[HttpUrl] = Field(..., min_length=1)


class Praise(BaseModel):
    text: str = Field(..., description="What customers like, paraphrased faithfully from real reviews")
    source_urls: list[HttpUrl] = Field(..., min_length=1)


class CompetitorReviews(BaseModel):
    competitor: str
    rating_summary: str = Field(
        "", description="Ratings found, e.g. '4.1★ on Google Maps (230 reviews)'; empty if none found"
    )
    likes: list[Praise] = Field(default_factory=list)
    complaints: list[Complaint] = Field(default_factory=list)
    review_sources_checked: list[HttpUrl] = Field(default_factory=list)


class PainPoint(BaseModel):
    pain_point: str = Field(..., description="A recurring customer complaint in this market")
    competitors: list[str] = Field(..., min_length=1, description="Competitors this pain point applies to")
    source_urls: list[HttpUrl] = Field(..., min_length=1)


class ReviewInsights(BaseModel):
    """Output of task 2 (review analysis)."""

    reviews: list[CompetitorReviews]
    common_pain_points: list[PainPoint]


class MatrixRow(BaseModel):
    competitor: str
    price_per_unit: str
    price_value: float | None = None
    channel: str
    strength: str
    weakness: str
    differentiation_score: int = Field(
        ..., ge=1, le=10, description="1 = commodity offer, 10 = highly differentiated"
    )
    source_urls: list[HttpUrl] = Field(..., min_length=1)


class StrategyMatrix(BaseModel):
    """Output of task 3 (strategy)."""

    matrix: list[MatrixRow]
    market_gap: str = Field(..., description="The single clearest opportunity nobody serves well today")
    gap_evidence: list[str] = Field(
        default_factory=list, description="Facts from tasks 1-2 supporting the gap"
    )
    recommended_offer: str = Field(..., description="One-line offer for the new business")
    recommended_price: str = Field(..., description="Recommended price with currency and unit")
    recommended_price_value: float | None = None
    positioning_rationale: str
    risks: list[str] = Field(default_factory=list)
