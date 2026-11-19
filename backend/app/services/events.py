"""Run progress events over Redis.

Each event gets a monotonically increasing ``seq`` per run. It is appended to a capped
list (for replay when a browser reconnects) and published on a pub/sub channel (for
live delivery). The SSE endpoint subscribes first, replays history, then streams live
events, de-duplicating by ``seq`` and honouring ``Last-Event-ID``.
"""

from __future__ import annotations

import json
import threading
from typing import Any, cast

import redis
import redis.asyncio as aioredis

EVENT_TTL_SECONDS = 60 * 60 * 24  # keep replay history for a day
MAX_EVENTS = 2000
TERMINAL = {"run_completed", "run_failed"}


def channel(run_id: str) -> str:
    return f"launchscout:run:{run_id}:events"


def history_key(run_id: str) -> str:
    return f"launchscout:run:{run_id}:history"


def seq_key(run_id: str) -> str:
    return f"launchscout:run:{run_id}:seq"


class SyncEventPublisher:
    """Used inside the crew subprocess (CrewAI callbacks are synchronous)."""

    def __init__(self, redis_url: str, run_id: str) -> None:
        self.r = redis.Redis.from_url(redis_url)
        self.run_id = run_id
        # CrewAI fires tool events from parallel threads; numbering, storing and publishing
        # under one lock keeps the history list and the live channel in seq order.
        self._lock = threading.Lock()

    def publish(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._publish(event)

    def _publish(self, event: dict[str, Any]) -> None:
        seq = int(cast(int, self.r.incr(seq_key(self.run_id))))
        event = {**event, "seq": seq}
        payload = json.dumps(event, default=str)
        pipe = self.r.pipeline()
        pipe.rpush(history_key(self.run_id), payload)
        pipe.ltrim(history_key(self.run_id), -MAX_EVENTS, -1)
        for k in (history_key(self.run_id), seq_key(self.run_id)):
            pipe.expire(k, EVENT_TTL_SECONDS)
        pipe.publish(channel(self.run_id), payload)
        pipe.execute()

    __call__ = publish

    def close(self) -> None:
        self.r.close()


async def publish_async(r: aioredis.Redis, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
    seq = int(await r.incr(seq_key(run_id)))
    event = {**event, "seq": seq}
    payload = json.dumps(event, default=str)
    pipe = r.pipeline()
    pipe.rpush(history_key(run_id), payload)
    pipe.ltrim(history_key(run_id), -MAX_EVENTS, -1)
    pipe.expire(history_key(run_id), EVENT_TTL_SECONDS)
    pipe.expire(seq_key(run_id), EVENT_TTL_SECONDS)
    pipe.publish(channel(run_id), payload)
    await pipe.execute()
    return event


async def history(r: aioredis.Redis, run_id: str) -> list[dict[str, Any]]:
    raw = await cast(Any, r.lrange(history_key(run_id), 0, -1))
    return [json.loads(x) for x in raw]
