"""SQLAlchemy 2 models: runs, their inputs, structured outputs, report, sources and metadata."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class RunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), default=RunStatus.queued, index=True
    )

    business_idea: Mapped[str] = mapped_column(String(400))
    city: Mapped[str] = mapped_column(String(120))
    target_customer: Mapped[str] = mapped_column(String(400))
    known_competitors: Mapped[list[Any]] = mapped_column(JSON, default=list)

    competitors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reviews: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    strategy: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sources: Mapped[list[Source]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Source.number", lazy="selectin"
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)

    run: Mapped[Run] = relationship(back_populates="sources")
