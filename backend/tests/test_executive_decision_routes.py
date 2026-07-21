from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import Response
from fastapi.testclient import TestClient

from app.models import ExecutiveDecisionQueue, ExecutiveDecisionSummary
from app.services.executive_decision_service import SOURCE_TYPES


def test_executive_decisions_route_is_authenticated_and_no_store(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_REQUIRED", "1")
    monkeypatch.setenv("CONTROL_PLANE_SERVICE_TOKEN", "executive-test-token")
    monkeypatch.delenv("LOCAL_CODEX_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("CRON_ACCESS_TOKEN", raising=False)

    from app.main import app

    payload = ExecutiveDecisionQueue(
        generated_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        summary=ExecutiveDecisionSummary(verification_status="verified", verified_clear=True),
        source_status={source: "ok" for source in SOURCE_TYPES},
    )
    client = TestClient(app)

    with patch("app.routes.executive.build_executive_decision_queue", return_value=payload):
        assert client.get("/api/executive/decisions").status_code == 401
        response = client.get(
            "/api/executive/decisions",
            headers={"Authorization": "Bearer executive-test-token"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    body = response.json()
    assert set(body) == {"generated_at", "summary", "source_status", "source_errors", "today", "all_pending"}
    assert body["summary"]["verified_clear"] is True


def test_executive_decisions_route_keeps_event_loop_responsive_during_sync_build() -> None:
    from app.routes import executive as executive_route

    payload = ExecutiveDecisionQueue(
        generated_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        summary=ExecutiveDecisionSummary(verification_status="verified", verified_clear=True),
        source_status={source: "ok" for source in SOURCE_TYPES},
    )

    def slow_build() -> ExecutiveDecisionQueue:
        time.sleep(0.12)
        return payload

    async def exercise_route() -> tuple[ExecutiveDecisionQueue, int]:
        finished = asyncio.Event()
        ticks = 0

        async def invoke() -> ExecutiveDecisionQueue:
            try:
                return await executive_route.get_executive_decisions(Response())
            finally:
                finished.set()

        async def heartbeat() -> None:
            nonlocal ticks
            while not finished.is_set():
                ticks += 1
                await asyncio.sleep(0.005)

        result, _ = await asyncio.gather(invoke(), heartbeat())
        return result, ticks

    with patch.object(executive_route, "build_executive_decision_queue", side_effect=slow_build):
        result, ticks = asyncio.run(exercise_route())

    assert result == payload
    assert ticks >= 5
