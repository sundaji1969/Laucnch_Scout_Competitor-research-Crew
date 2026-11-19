"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.security import RunRateLimiter
from app.config import Settings, get_settings
from app.logging_setup import configure_logging

log = logging.getLogger("launchscout.api")


async def _arq_enqueue_factory(settings: Settings) -> tuple[Callable[[str], Awaitable[None]], Any]:
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    async def enqueue(run_id: str) -> None:
        await pool.enqueue_job("execute_run", run_id, _job_id=f"run-{run_id}")

    return enqueue, pool


def create_app(
    settings: Settings | None = None,
    redis_client: Any | None = None,
    enqueue: Callable[[str], Awaitable[None]] | None = None,
    rate_limiter: RunRateLimiter | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        app.state.redis = redis_client or aioredis.Redis.from_url(settings.redis_url)
        app.state.rate_limiter = rate_limiter or RunRateLimiter(settings)
        pool = None
        if enqueue is None:
            app.state.enqueue, pool = await _arq_enqueue_factory(settings)
        else:
            app.state.enqueue = enqueue
        yield
        if pool is not None:
            await pool.aclose()
        if redis_client is None:
            await app.state.redis.aclose()

    app = FastAPI(
        title="LaunchScout API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": "Please check the form.", "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side."})

    app.include_router(router)
    return app


app = create_app()
