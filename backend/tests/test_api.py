"""API tests: SQLite + fakeredis, no worker (enqueue is captured)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import fakeredis
import pytest
from fastapi.testclient import TestClient
from limits.aio.storage import MemoryStorage

from app.api.security import RunRateLimiter
from app.config import Settings, get_settings
from app.db import session as db_session
from app.db.models import Base, Run, RunStatus, Source
from app.services.events import history_key, publish_async

GOOD = (Path(__file__).parent / "fixtures" / "good_report.md").read_text(encoding="utf-8")
BODY = {
    "business_idea": "Healthy millet meal boxes delivered for lunch",
    "city": "Coimbatore",
    "target_customer": "Office workers, age 25 to 40",
    "known_competitors": ["Millet Kitchen"],
}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("RATE_LIMIT_RUNS", "3/hour")
    monkeypatch.setenv("MAX_CONCURRENT_RUNS", "2")
    for fn in (get_settings, db_session.get_engine, db_session.get_sessionmaker):
        fn.cache_clear()

    async def init() -> None:
        async with db_session.get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init())
    yield {"settings": get_settings()}
    asyncio.run(db_session.get_engine().dispose())
    for fn in (get_settings, db_session.get_engine, db_session.get_sessionmaker):
        fn.cache_clear()


@pytest.fixture
def client(env: dict[str, Any]) -> Iterator[TestClient]:
    from app.main import create_app

    enqueued: list[str] = []

    async def enqueue(run_id: str) -> None:
        enqueued.append(run_id)

    settings: Settings = env["settings"]
    app = create_app(
        settings=settings,
        redis_client=fakeredis.FakeAsyncRedis(),
        enqueue=enqueue,
        rate_limiter=RunRateLimiter(settings, storage=MemoryStorage()),
    )
    with TestClient(app) as c:
        c.enqueued = enqueued  # type: ignore[attr-defined]
        yield c


def _insert_completed(client: TestClient, run_id: str = "abc123") -> None:
    async def go() -> None:
        async with db_session.get_sessionmaker()() as s:
            run = Run(
                id=run_id,
                status=RunStatus.completed,
                business_idea="Millet boxes",
                city="Coimbatore",
                target_customer="Office workers",
                known_competitors=[],
                report_markdown=GOOD,
                competitors={"competitors": [{"name": "A"}, {"name": "B"}, {"name": "C"}]},
                strategy={"market_gap": "On-time millet lunches"},
            )
            run.sources.append(Source(number=1, title="Millet Kitchen", url="https://example.com"))
            s.add(run)
            await s.commit()

    client.portal.call(go)  # type: ignore[union-attr]


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["checks"] == {"api": "ok", "database": "ok", "redis": "ok"}


def test_create_run_enqueues(client: TestClient) -> None:
    r = client.post("/api/runs", json=BODY)
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    assert client.enqueued == [run_id]  # type: ignore[attr-defined]
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["status"] == "queued"
    assert detail["known_competitors"] == ["Millet Kitchen"]


@pytest.mark.parametrize(
    "patch",
    [{"business_idea": ""}, {"city": "x"}, {"target_customer": None}, {"business_idea": "x" * 301}],
)
def test_validation_errors(client: TestClient, patch: dict[str, Any]) -> None:
    r = client.post("/api/runs", json={**BODY, **patch})
    assert r.status_code == 422
    assert r.json()["detail"] == "Please check the form."


def test_rate_limit(client: TestClient) -> None:
    codes = [client.post("/api/runs", json=BODY).status_code for _ in range(4)]
    # 3/hour limit; the busy cap (2*3=6 active) is not reached first
    assert codes == [202, 202, 202, 429]


def test_busy_cap(client: TestClient, env: dict[str, Any]) -> None:
    async def fill() -> None:
        async with db_session.get_sessionmaker()() as s:
            for i in range(6):
                s.add(
                    Run(
                        id=f"busy{i}",
                        business_idea="x" * 5,
                        city="Pune",
                        target_customer="y" * 5,
                        known_competitors=[],
                        status=RunStatus.running,
                    )
                )
            await s.commit()

    client.portal.call(fill)  # type: ignore[union-attr]
    r = client.post("/api/runs", json=BODY)
    assert r.status_code == 503


def test_unknown_run_404(client: TestClient) -> None:
    assert client.get("/api/runs/doesnotexist").status_code == 404
    assert client.get("/api/runs/..%2Fetc").status_code == 404


def test_list_and_downloads(client: TestClient) -> None:
    _insert_completed(client)
    items = client.get("/api/runs").json()["items"]
    assert items[0]["id"] == "abc123"
    assert items[0]["competitor_count"] == 3
    assert items[0]["market_gap"] == "On-time millet lunches"

    md = client.get("/api/runs/abc123/report.md")
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert "attachment" in md.headers["content-disposition"]
    assert "## 6. Sources" in md.text
    detail = client.get("/api/runs/abc123").json()
    assert detail["sources"][0]["url"] == "https://example.com"


def test_report_not_ready(client: TestClient) -> None:
    run_id = client.post("/api/runs", json=BODY).json()["run_id"]
    assert client.get(f"/api/runs/{run_id}/report.md").status_code == 409


def _sse_events(text: str) -> list[dict[str, Any]]:
    return [json.loads(line[5:].strip()) for line in text.splitlines() if line.startswith("data:")]


def test_sse_replays_history_and_closes_on_terminal(client: TestClient) -> None:
    run_id = client.post("/api/runs", json=BODY).json()["run_id"]
    redis = client.app.state.redis  # type: ignore[attr-defined]

    async def publish() -> None:
        await publish_async(redis, run_id, {"type": "agent_started", "agent": "market_researcher"})
        await publish_async(redis, run_id, {"type": "tool_called", "message": "Searching: x"})
        await publish_async(redis, run_id, {"type": "run_completed", "message": "done"})

    client.portal.call(publish)  # type: ignore[union-attr]
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _sse_events(r.read().decode())
    assert [e["type"] for e in events] == ["agent_started", "tool_called", "run_completed"]
    assert [e["seq"] for e in events] == [1, 2, 3]

    with client.stream("GET", f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "2"}) as r:
        resumed = _sse_events(r.read().decode())
    assert [e["type"] for e in resumed] == ["run_completed"]


def test_sse_for_old_finished_run(client: TestClient) -> None:
    _insert_completed(client, "old1")
    redis = client.app.state.redis  # type: ignore[attr-defined]
    assert client.portal.call(redis.exists, history_key("old1")) == 0  # type: ignore[union-attr]
    with client.stream("GET", "/api/runs/old1/events") as r:
        events = _sse_events(r.read().decode())
    assert events[-1]["type"] == "run_completed"


def test_sse_delivers_out_of_order_history(client: TestClient) -> None:
    """Parallel tool threads can store events out of seq order; none may be dropped."""
    run_id = client.post("/api/runs", json=BODY).json()["run_id"]
    redis = client.app.state.redis  # type: ignore[attr-defined]
    order = [1, 2, 4, 3, 5]

    async def store() -> None:
        for seq in order:
            etype = "run_completed" if seq == 5 else "tool_called"
            await redis.rpush(history_key(run_id), json.dumps({"type": etype, "seq": seq}))

    client.portal.call(store)  # type: ignore[union-attr]
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        events = _sse_events(r.read().decode())
    assert [e["seq"] for e in events] == order


def test_sync_publisher_is_ordered_under_threads() -> None:
    import threading

    from app.services.events import SyncEventPublisher

    pub = SyncEventPublisher.__new__(SyncEventPublisher)
    pub.r = fakeredis.FakeRedis()
    pub.run_id = "t1"
    pub._lock = threading.Lock()
    threads = [threading.Thread(target=pub.publish, args=({"type": "tool_called"},)) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    seqs = [json.loads(x)["seq"] for x in pub.r.lrange(history_key("t1"), 0, -1)]
    assert seqs == list(range(1, 41))
