"""API request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.crew.inputs import RunInputs


class RunCreate(RunInputs):
    turnstile_token: str | None = Field(None, max_length=4096)


class RunCreated(BaseModel):
    run_id: str
    status: str
    events_url: str


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    number: int
    title: str
    url: str


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    business_idea: str
    city: str
    target_customer: str
    created_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    competitor_count: int = 0
    market_gap: str | None = None


class RunDetail(RunSummary):
    known_competitors: list[str] = []
    started_at: datetime | None = None
    error: str | None = None
    competitors: dict[str, Any] | None = None
    reviews: dict[str, Any] | None = None
    strategy: dict[str, Any] | None = None
    report_markdown: str | None = None
    sources: list[SourceOut] = []
    llm_model: str | None = None
    total_tokens: int | None = None
    search_calls: int | None = None


class RunList(BaseModel):
    items: list[RunSummary]


class Health(BaseModel):
    status: str
    checks: dict[str, str]
