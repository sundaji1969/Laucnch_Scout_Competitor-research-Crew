"""Public-use hardening: client IP, per-IP rate limiting, optional Turnstile captcha."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import cast

import httpx
from fastapi import HTTPException, Request, status
from limits import parse
from limits.aio.storage import MemoryStorage, Storage
from limits.aio.strategies import MovingWindowRateLimiter
from limits.storage import storage_from_string

from app.config import Settings

log = logging.getLogger("launchscout.security")

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


def ip_hash(ip: str) -> str:
    return hashlib.sha256(f"launchscout:{ip}".encode()).hexdigest()[:32]


class RunRateLimiter:
    def __init__(self, settings: Settings, storage: Storage | None = None) -> None:
        self.item = parse(settings.rate_limit_runs)
        if storage is None:
            url = settings.redis_url
            storage = cast(
                Storage,
                storage_from_string("async+" + url, implementation="redispy")
                if url.startswith("redis")
                else MemoryStorage(),
            )
        self.limiter = MovingWindowRateLimiter(storage)

    async def check(self, key: str) -> None:
        if not await self.limiter.hit(self.item, "runs", key):
            stats = await self.limiter.get_window_stats(self.item, "runs", key)
            retry = max(1, int(stats.reset_time - time.time()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit reached ({self.item}). Please try again in {retry // 60 + 1} minutes.",
                headers={"Retry-After": str(retry)},
            )


async def verify_turnstile(token: str | None, ip: str, settings: Settings) -> None:
    if not settings.turnstile_enabled:
        return
    if not token:
        raise HTTPException(status_code=400, detail="Please complete the captcha.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TURNSTILE_VERIFY_URL,
                data={"secret": settings.turnstile_secret_key, "response": token, "remoteip": ip},
            )
        ok = bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError):
        log.warning("turnstile_unreachable")
        raise HTTPException(status_code=503, detail="Captcha service unavailable, try again.") from None
    if not ok:
        raise HTTPException(status_code=400, detail="Captcha verification failed.")
