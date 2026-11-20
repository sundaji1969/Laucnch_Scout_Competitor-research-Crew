"""REST + SSE endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import Health, RunCreate, RunCreated, RunDetail, RunList, RunSummary, SourceOut
from app.api.security import client_ip, ip_hash, verify_turnstile
from app.config import Settings, get_settings
from app.crew.progress import make_event
from app.db.models import Run, RunStatus
from app.db.session import get_session
from app.services.events import TERMINAL, channel, history
from app.services.pdf import render_pdf, report_html

log = logging.getLogger("launchscout.api")
router = APIRouter(prefix="/api")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ACTIVE = (RunStatus.queued, RunStatus.running)
BUSY_MESSAGE = "LaunchScout is busy right now. Please try again in a few minutes."


def _summary(run: Run) -> RunSummary:
    comps = (run.competitors or {}).get("competitors") or []
    return RunSummary(
        id=run.id,
        status=run.status.value,
        business_idea=run.business_idea,
        city=run.city,
        target_customer=run.target_customer,
        created_at=run.created_at,
        finished_at=run.finished_at,
        duration_seconds=run.duration_seconds,
        competitor_count=len(comps),
        market_gap=(run.strategy or {}).get("market_gap"),
    )


def _detail(run: Run) -> RunDetail:
    return RunDetail(
        **_summary(run).model_dump(),
        known_competitors=list(run.known_competitors or []),
        started_at=run.started_at,
        error=run.error,
        competitors=run.competitors,
        reviews=run.reviews,
        strategy=run.strategy,
        report_markdown=run.report_markdown,
        sources=[SourceOut.model_validate(s) for s in run.sources],
        llm_model=run.llm_model,
        total_tokens=run.total_tokens,
        search_calls=run.search_calls,
    )


async def _get_run(session: AsyncSession, run_id: str) -> Run:
    if not run_id.isalnum() or len(run_id) > 32:
        raise HTTPException(status_code=404, detail="Run not found")
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/health", response_model=Health)
async def health(request: Request, session: SessionDep, response: Response) -> Health:
    checks: dict[str, str] = {"api": "ok"}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {type(exc).__name__}"
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = 503
    return Health(status="ok" if ok else "degraded", checks=checks)


async def _reserve_daily_slot(request: Request, settings: Settings) -> str | None:
    """Take one of today's DAILY_RUN_CAP slots (all users, UTC day), or raise 429.

    An atomic Redis INCR, so concurrent requests can't overshoot the cap. Returns the
    counter key so the caller can give the slot back if the request fails a later check.
    """
    cap = settings.daily_run_cap
    if cap <= 0:
        return None
    now = datetime.now(UTC)
    key = f"launchscout:daily_runs:{now:%Y%m%d}"
    redis = request.app.state.redis
    used = await redis.incr(key)
    if used == 1:
        await redis.expire(key, 2 * 86_400)
    if used > cap:
        await redis.decr(key)
        reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        retry = max(1, int((reset - now).total_seconds()))
        log.warning("daily_run_cap_reached", extra={"cap": cap})
        raise HTTPException(
            429,
            detail=(
                f"LaunchScout has reached today's limit of {cap} reports. "
                f"New research opens again in about {retry // 3600 + 1} hours (midnight UTC)."
            ),
            headers={"Retry-After": str(retry)},
        )
    return key


@router.post("/runs", response_model=RunCreated, status_code=202)
async def create_run(
    body: RunCreate, request: Request, session: SessionDep, settings: SettingsDep
) -> RunCreated:
    ip = client_ip(request, settings)
    await verify_turnstile(body.turnstile_token, ip, settings)
    for field, value in (("business_idea", body.business_idea), ("target_customer", body.target_customer)):
        if len(value) > settings.max_input_chars:
            raise HTTPException(422, detail=f"{field} is longer than {settings.max_input_chars} characters")
    day_key = await _reserve_daily_slot(request, settings)
    try:
        await request.app.state.rate_limiter.check(ip_hash(ip))
        active = await session.scalar(select(func.count()).select_from(Run).where(Run.status.in_(ACTIVE)))
        if (active or 0) >= settings.max_concurrent_runs * 3:
            raise HTTPException(503, detail=BUSY_MESSAGE)
    except HTTPException:
        if day_key:  # rejected for another reason: give the day's slot back
            await request.app.state.redis.decr(day_key)
        raise

    run = Run(
        id=uuid.uuid4().hex[:16],
        business_idea=body.business_idea,
        city=body.city,
        target_customer=body.target_customer,
        known_competitors=body.known_competitors,
        client_ip_hash=ip_hash(ip),
        llm_model=settings.llm_model,
    )
    session.add(run)
    await session.commit()
    await request.app.state.enqueue(run.id)
    log.info("run_created", extra={"run_id": run.id, "city": run.city})
    return RunCreated(run_id=run.id, status=run.status.value, events_url=f"/api/runs/{run.id}/events")


@router.get("/runs", response_model=RunList)
async def list_runs(session: SessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 24) -> RunList:
    rows = (await session.execute(select(Run).order_by(Run.created_at.desc()).limit(limit))).scalars()
    return RunList(items=[_summary(r) for r in rows])


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: SessionDep) -> RunDetail:
    return _detail(await _get_run(session, run_id))


def _filename(run: Run, ext: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in f"{run.business_idea}-{run.city}".lower())
    slug = "-".join(p for p in slug.split("-") if p)[:60]
    return f"launchscout-{slug}.{ext}"


@router.get("/runs/{run_id}/report.md")
async def report_md(run_id: str, session: SessionDep) -> Response:
    run = await _get_run(session, run_id)
    if not run.report_markdown:
        raise HTTPException(409, detail="Report not ready")
    return Response(
        run.report_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_filename(run, "md")}"'},
    )


@router.get("/runs/{run_id}/report.pdf")
async def report_pdf(run_id: str, session: SessionDep) -> Response:
    run = await _get_run(session, run_id)
    if not run.report_markdown:
        raise HTTPException(409, detail="Report not ready")
    doc = report_html(
        run.report_markdown,
        idea=run.business_idea,
        city=run.city,
        target_customer=run.target_customer,
        created=run.created_at,
    )
    pdf = await asyncio.to_thread(render_pdf, doc)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(run, "pdf")}"'},
    )


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    session: SessionDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
) -> EventSourceResponse:
    run = await _get_run(session, run_id)
    status_now, run_db_id = run.status, run.id
    redis = request.app.state.redis
    try:
        resume_after = int(last_event_id) if last_event_id else (after or 0)
    except ValueError:
        resume_after = 0
    sent: set[int] = set()

    def fresh_event(event: dict[str, Any]) -> bool:
        """Exact de-duplication (history vs live) plus Last-Event-ID resume."""
        seq = int(event.get("seq", 0))
        if seq and (seq <= resume_after or seq in sent):
            return False
        if seq:
            sent.add(seq)
        return True

    async def stream() -> AsyncIterator[dict[str, Any]]:
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel(run_db_id))
        try:
            saw_terminal = False
            for event in await history(redis, run_db_id):
                if not fresh_event(event):
                    saw_terminal = saw_terminal or event["type"] in TERMINAL
                    continue
                yield {"id": str(event.get("seq", "")), "data": json.dumps(event)}
                saw_terminal = saw_terminal or event["type"] in TERMINAL
            if saw_terminal:
                return
            if status_now not in ACTIVE:  # finished long ago, history expired
                etype = "run_completed" if status_now is RunStatus.completed else "run_failed"
                yield {"data": json.dumps(make_event(etype, run_db_id, message=f"Run {status_now.value}"))}
                return
            idle = 0.0
            while True:
                if await request.is_disconnected():
                    return
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg is None:
                    idle += 5
                    if idle >= 30:  # safety net: worker died without a terminal event
                        idle = 0
                        from app.db.session import get_sessionmaker

                        async with get_sessionmaker()() as s2:
                            fresh = await s2.get(Run, run_db_id)
                        if fresh is not None and fresh.status not in ACTIVE:
                            etype = "run_completed" if fresh.status is RunStatus.completed else "run_failed"
                            msg_text = fresh.error or f"Run {fresh.status.value}"
                            yield {"data": json.dumps(make_event(etype, run_db_id, message=msg_text))}
                            return
                    continue
                idle = 0
                event = json.loads(msg["data"])
                if not fresh_event(event):
                    continue
                yield {"id": str(event.get("seq", "")), "data": json.dumps(event)}
                if event["type"] in TERMINAL:
                    return
        finally:
            await pubsub.unsubscribe(channel(run_db_id))
            await pubsub.aclose()

    return EventSourceResponse(
        stream(),
        ping=15,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
