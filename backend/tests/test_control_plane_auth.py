from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.control_plane import (
    LOCAL_CODEX_WORKER_SCOPE,
    configured_tokens,
    control_plane_auth_required,
    request_auth_scope,
)


def test_railway_environment_forces_auth_even_without_explicit_flag() -> None:
    with patch.dict("os.environ", {"RAILWAY_ENVIRONMENT": "production"}, clear=True):
        assert control_plane_auth_required() is True
        assert configured_tokens() == ()


def test_control_plane_middleware_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_REQUIRED", "1")
    monkeypatch.setenv("CONTROL_PLANE_SERVICE_TOKEN", "test-control-token")

    # Import after configuring the environment so the full application uses
    # the same production-like contract exercised by this request.
    from app.main import app

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/docs").status_code == 401
    response = client.get(
        "/api/docs",
        headers={"Authorization": "Bearer test-control-token"},
    )
    assert response.status_code == 200


def test_worker_token_is_scoped_to_claim_complete_and_fail(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_REQUIRED", "1")
    monkeypatch.setenv("CONTROL_PLANE_SERVICE_TOKEN", "test-control-token")
    monkeypatch.setenv("LOCAL_CODEX_BRIDGE_TOKEN", "test-worker-token")
    monkeypatch.delenv("CRON_ACCESS_TOKEN", raising=False)

    from app.main import app

    client = TestClient(app)

    assert client.get(
        "/api/docs",
        headers={"X-Local-Codex-Token": "test-worker-token"},
    ).status_code == 401
    assert client.get(
        "/api/docs",
        headers={"Authorization": "Bearer test-worker-token"},
    ).status_code == 401
    assert client.post(
        "/api/content-generation/codex-jobs",
        headers={"X-Local-Codex-Token": "test-worker-token"},
        json={},
    ).status_code == 401

    with patch("app.routes.content_generation.claim_next_codex_job", return_value=None):
        assert client.post(
            "/api/content-generation/codex-jobs/claim-next",
            headers={"Authorization": "Bearer test-control-token"},
            json={"worker_id": "test-worker"},
        ).status_code == 401
        assert client.post(
            "/api/content-generation/codex-jobs/claim-next",
            headers={"X-Local-Codex-Token": "test-control-token"},
            json={"worker_id": "test-worker"},
        ).status_code == 401
        response = client.post(
            "/api/content-generation/codex-jobs/claim-next",
            headers={"X-Local-Codex-Token": "test-worker-token"},
            json={"worker_id": "test-worker"},
        )
    assert response.status_code == 200
    assert response.json()["job_available"] is False


def test_worker_auth_scope_only_matches_intended_post_endpoints() -> None:
    assert request_auth_scope(
        "/api/content-generation/codex-jobs/claim-next",
        "POST",
    ) == LOCAL_CODEX_WORKER_SCOPE
    assert request_auth_scope(
        "/api/content-generation/codex-jobs/job-123/complete",
        "POST",
    ) == LOCAL_CODEX_WORKER_SCOPE
    assert request_auth_scope(
        "/api/content-generation/codex-jobs/job-123/fail",
        "POST",
    ) == LOCAL_CODEX_WORKER_SCOPE

    assert request_auth_scope(
        "/api/content-generation/codex-jobs/job-123",
        "GET",
    ) != LOCAL_CODEX_WORKER_SCOPE
    assert request_auth_scope(
        "/api/content-generation/codex-jobs/job-123/cancel",
        "POST",
    ) != LOCAL_CODEX_WORKER_SCOPE
    assert request_auth_scope(
        "/api/content-generation/codex-jobs/claim-next",
        "GET",
    ) != LOCAL_CODEX_WORKER_SCOPE


def test_duplicate_service_and_worker_tokens_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_SERVICE_TOKEN", "same-token")
    monkeypatch.setenv("LOCAL_CODEX_BRIDGE_TOKEN", "same-token")
    monkeypatch.delenv("CRON_ACCESS_TOKEN", raising=False)

    assert configured_tokens() == ("same-token",)
    assert configured_tokens(LOCAL_CODEX_WORKER_SCOPE) == ()
