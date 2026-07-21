from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.services import neo_guest_service


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_REQUIRED", "1")
    monkeypatch.setenv("CONTROL_PLANE_SERVICE_TOKEN", "operator-test-token")
    monkeypatch.setenv("LOCAL_CODEX_BRIDGE_TOKEN", "worker-test-token")
    monkeypatch.setenv("NEO_GUEST_SIGNING_SECRET", "a-secure-test-secret-that-is-at-least-32-bytes")
    from app.main import app
    return TestClient(app)


def test_guest_access_is_separate_from_operator_auth(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch("app.routes.neo_guest.service.exchange_passcode", return_value={"session_token": "guest-token", "session_id": "s1", "invite_label": "Test"}):
        response = client.post("/api/neo/guest/access", json={"passcode": "a-valid-test-code"})
    assert response.status_code == 200
    assert response.json()["session_token"] == "guest-token"
    assert client.get("/api/neo/operator/inbox").status_code == 401


def test_guest_access_is_rate_limited_per_forwarded_client(monkeypatch) -> None:
    client = _client(monkeypatch)
    from app.routes import neo_guest

    client_ip = "198.51.100.73"
    neo_guest._access_attempts.pop(client_ip, None)
    headers = {"X-Forwarded-For": client_ip}
    with patch(
        "app.routes.neo_guest.service.exchange_passcode",
        return_value={"session_token": "guest-token", "session_id": "s1", "invite_label": "Test"},
    ):
        for _ in range(neo_guest.ACCESS_ATTEMPT_LIMIT):
            assert client.post(
                "/api/neo/guest/access",
                headers=headers,
                json={"passcode": "a-valid-test-code"},
            ).status_code == 200
        limited = client.post(
            "/api/neo/guest/access",
            headers=headers,
            json={"passcode": "a-valid-test-code"},
        )
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "900"
    neo_guest._access_attempts.pop(client_ip, None)


def test_guest_message_revalidates_guest_session(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch("app.routes.neo_guest.service.authenticate_session", return_value={"id": "session-1"}), patch(
        "app.routes.neo_guest.service.enqueue_message",
        return_value={"job_id": "job-1", "message_id": "message-1", "status": "pending"},
    ) as enqueue_message:
        response = client.post(
            "/api/neo/guest/messages",
            headers={"Authorization": "Bearer guest-token"},
            json={
                "client_request_id": "00000000-0000-4000-8000-000000000001",
                "content": "Tell me about Johnnie.",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    enqueue_message.assert_called_once_with(
        "session-1",
        "Tell me about Johnnie.",
        "00000000-0000-4000-8000-000000000001",
    )


def test_legacy_guest_message_mints_key_but_v2_requires_uuid(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.enqueue_message",
        return_value={"job_id": "job-1", "message_id": "message-1", "status": "pending"},
    ) as enqueue:
        legacy = client.post(
            "/api/neo/guest/messages",
            headers={"Authorization": "Bearer guest-token"},
            json={"content": "Tell me about Johnnie."},
        )

    assert legacy.status_code == 200
    generated_key = enqueue.call_args.args[2]
    assert str(UUID(generated_key)) == generated_key

    missing = client.post(
        "/api/neo/guest/v2/messages",
        headers={"Authorization": "Bearer guest-token"},
        json={"content": "Tell me about Johnnie."},
    )
    malformed = client.post(
        "/api/neo/guest/v2/messages",
        headers={"Authorization": "Bearer guest-token"},
        json={"client_request_id": "not-a-uuid", "content": "Tell me about Johnnie."},
    )
    assert missing.status_code == 422
    assert malformed.status_code == 422


def test_guest_message_models_reject_whitespace_after_trim(monkeypatch) -> None:
    client = _client(monkeypatch)
    for path, payload in (
        ("/api/neo/guest/messages", {"content": "   \n  "}),
        (
            "/api/neo/guest/v2/messages",
            {
                "client_request_id": "00000000-0000-4000-8000-000000000005",
                "content": "   \t  ",
            },
        ),
    ):
        assert client.post(
            path,
            headers={"Authorization": "Bearer guest-token"},
            json=payload,
        ).status_code == 422


def test_guest_message_returns_503_when_public_knowledge_is_unavailable(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.enqueue_message",
        side_effect=neo_guest_service.NeoGuestError(
            "Neo's approved professional knowledge is temporarily unavailable."
        ),
    ) as enqueue_message:
        response = client.post(
            "/api/neo/guest/messages",
            headers={"Authorization": "Bearer guest-token"},
            json={
                "client_request_id": "00000000-0000-4000-8000-000000000002",
                "content": "Tell me about Johnnie.",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Neo's approved professional knowledge is temporarily unavailable."
    enqueue_message.assert_called_once_with(
        "session-1",
        "Tell me about Johnnie.",
        "00000000-0000-4000-8000-000000000002",
    )


def test_guest_message_maps_idempotency_conflict_to_409(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.enqueue_message",
        side_effect=neo_guest_service.NeoGuestConflict(
            "client_request_id was already used for a different message."
        ),
    ):
        response = client.post(
            "/api/neo/guest/messages",
            headers={"Authorization": "Bearer guest-token"},
            json={
                "client_request_id": "00000000-0000-4000-8000-000000000003",
                "content": "Changed question",
            },
        )

    assert response.status_code == 409
    assert "different message" in response.json()["detail"]


def test_guest_message_maps_transactional_revocation_race_to_401(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.enqueue_message",
        side_effect=neo_guest_service.NeoGuestUnauthorized(
            "Guest session is invalid or revoked."
        ),
    ):
        response = client.post(
            "/api/neo/guest/messages",
            headers={"Authorization": "Bearer guest-token"},
            json={
                "client_request_id": "00000000-0000-4000-8000-000000000004",
                "content": "Tell me about Johnnie.",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Guest session is invalid or revoked."


def test_guest_meeting_legacy_mints_key_v2_requires_it_and_conflicts_map(monkeypatch) -> None:
    client = _client(monkeypatch)
    meeting = {
        "client_request_id": "00000000-0000-4000-8000-000000000010",
        "visitor_name": "Test Visitor",
        "visitor_email": "visitor@example.com",
        "visitor_phone": "+1 202 555 0100",
        "purpose": "Discuss a professional partnership",
        "preferred_times": ["Tuesday at 2 PM ET"],
        "timezone": "America/New_York",
    }
    missing_key = dict(meeting)
    missing_key.pop("client_request_id")
    assert client.post(
        "/api/neo/guest/v2/meeting-requests",
        headers={"Authorization": "Bearer guest-token"},
        json=missing_key,
    ).status_code == 422

    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.create_meeting_request",
        return_value={"id": "meeting-1", "status": "pending"},
    ) as create_meeting:
        legacy = client.post(
            "/api/neo/guest/meeting-requests",
            headers={"Authorization": "Bearer guest-token"},
            json=missing_key,
        )
    assert legacy.status_code == 200
    generated_key = str(create_meeting.call_args.args[1]["client_request_id"])
    assert str(UUID(generated_key)) == generated_key

    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.create_meeting_request",
        side_effect=neo_guest_service.NeoGuestConflict(
            "client_request_id was already used for a different meeting request."
        ),
    ):
        conflict = client.post(
            "/api/neo/guest/meeting-requests",
            headers={"Authorization": "Bearer guest-token"},
            json=meeting,
        )

    assert conflict.status_code == 409
    assert "different meeting request" in conflict.json()["detail"]


def test_guest_meeting_models_reject_blank_trimmed_fields(monkeypatch) -> None:
    client = _client(monkeypatch)
    base = {
        "visitor_name": "Test Visitor",
        "visitor_email": "visitor@example.com",
        "visitor_phone": "+1 202 555 0100",
        "purpose": "Discuss a professional partnership",
        "preferred_times": ["Tuesday at 2 PM ET"],
        "timezone": "America/New_York",
    }
    for path, changes in (
        ("/api/neo/guest/meeting-requests", {"visitor_name": "   "}),
        (
            "/api/neo/guest/v2/meeting-requests",
            {
                "client_request_id": "00000000-0000-4000-8000-000000000012",
                "preferred_times": [" \n "],
            },
        ),
    ):
        payload = {**base, **changes}
        assert client.post(
            path,
            headers={"Authorization": "Bearer guest-token"},
            json=payload,
        ).status_code == 422


def test_guest_session_bootstrap_is_guest_owned_and_no_store(monkeypatch) -> None:
    client = _client(monkeypatch)
    bootstrap = {
        "messages": [
            {
                "id": "message-1",
                "role": "user",
                "content": "Hello",
                "created_at": "2026-07-21T12:00:00+00:00",
            }
        ],
        "active_job": {
            "job_id": "job-1",
            "client_request_id": "00000000-0000-4000-8000-000000000013",
            "user_message": "Hello",
            "partial_response": "Hi",
        },
    }
    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.get_session_bootstrap",
        return_value=bootstrap,
    ) as get_bootstrap:
        response = client.get(
            "/api/neo/guest/session",
            headers={"Authorization": "Bearer guest-token"},
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.json() == bootstrap
    get_bootstrap.assert_called_once_with("session-1")


def test_guest_meeting_maps_transactional_revocation_race_to_401(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch(
        "app.routes.neo_guest.service.authenticate_session",
        return_value={"id": "session-1"},
    ), patch(
        "app.routes.neo_guest.service.create_meeting_request",
        side_effect=neo_guest_service.NeoGuestUnauthorized(
            "Guest session is invalid or revoked."
        ),
    ):
        response = client.post(
            "/api/neo/guest/meeting-requests",
            headers={"Authorization": "Bearer guest-token"},
            json={
                "client_request_id": "00000000-0000-4000-8000-000000000011",
                "visitor_name": "Test Visitor",
                "visitor_email": "visitor@example.com",
                "visitor_phone": "+1 202 555 0100",
                "purpose": "Discuss a professional partnership",
                "preferred_times": ["Tuesday at 2 PM ET"],
                "timezone": "America/New_York",
            },
        )

    assert response.status_code == 401


def test_guest_job_returns_progress_only_for_authenticated_session(monkeypatch) -> None:
    client = _client(monkeypatch)
    job_payload = {
        "id": "job-1",
        "status": "running",
        "partial_response": "A grounded partial answer",
        "claimed_at": "2026-07-21T11:59:59+00:00",
        "model_started_at": "2026-07-21T12:00:00+00:00",
        "first_token_at": "2026-07-21T12:00:01+00:00",
        "progress_at": "2026-07-21T12:00:02+00:00",
        "response": None,
    }
    with patch("app.routes.neo_guest.service.authenticate_session", return_value={"id": "session-1"}), patch(
        "app.routes.neo_guest.service.get_job",
        return_value=job_payload,
    ) as get_job:
        response = client.get(
            "/api/neo/guest/jobs/job-1",
            headers={"Authorization": "Bearer guest-token"},
        )

    assert response.status_code == 200
    assert response.json()["partial_response"] == "A grounded partial answer"
    assert response.json()["claimed_at"] == "2026-07-21T11:59:59+00:00"
    assert response.json()["first_token_at"] == "2026-07-21T12:00:01+00:00"
    get_job.assert_called_once_with("session-1", "job-1")


def test_worker_progress_requires_worker_scope_and_bounds_partial_response(monkeypatch) -> None:
    client = _client(monkeypatch)
    result = {
        "id": "job-1",
        "status": "running",
        "partial_response": "Draft",
        "model_started_at": "2026-07-21T12:00:00+00:00",
        "first_token_at": "2026-07-21T12:00:01+00:00",
        "progress_at": "2026-07-21T12:00:01+00:00",
    }
    with patch("app.routes.neo_guest.service.progress_job", return_value=result) as progress_job:
        accepted = client.post(
            "/api/neo/worker/jobs/job-1/progress",
            headers={"X-Local-Codex-Token": "worker-test-token"},
            json={"worker_id": "worker-1", "partial_response": "Draft"},
        )
        operator_only = client.post(
            "/api/neo/worker/jobs/job-1/progress",
            headers={"Authorization": "Bearer operator-test-token"},
            json={"worker_id": "worker-1", "partial_response": "Draft"},
        )
        too_large = client.post(
            "/api/neo/worker/jobs/job-1/progress",
            headers={"X-Local-Codex-Token": "worker-test-token"},
            json={"worker_id": "worker-1", "partial_response": "x" * 8001},
        )

    assert accepted.status_code == 200
    assert accepted.headers["Cache-Control"] == "no-store, max-age=0"
    assert operator_only.status_code == 401
    assert too_large.status_code == 422
    progress_job.assert_called_once_with("job-1", "worker-1", "Draft")


def test_worker_capabilities_requires_worker_scope_and_is_no_store(monkeypatch) -> None:
    client = _client(monkeypatch)

    accepted = client.post(
        "/api/neo/worker/capabilities",
        headers={"X-Local-Codex-Token": "worker-test-token"},
    )
    operator_only = client.post(
        "/api/neo/worker/capabilities",
        headers={"Authorization": "Bearer operator-test-token"},
    )
    unauthenticated = client.post("/api/neo/worker/capabilities")

    assert accepted.status_code == 200
    assert accepted.headers["Cache-Control"] == "no-store, max-age=0"
    assert accepted.json() == {
        "protocol_version": 2,
        "lease_seconds": neo_guest_service.NEO_GUEST_JOB_LEASE_SECONDS,
        "claim_token_required": True,
    }
    assert operator_only.status_code == 401
    assert unauthenticated.status_code == 401


def test_v2_worker_claim_returns_protocol_envelope_and_requires_worker_scope(monkeypatch) -> None:
    client = _client(monkeypatch)
    claimed_job = {"id": "job-1", "claim_token": "claim-token", "context_packet": {}}
    with patch(
        "app.routes.neo_guest.service.claim_next_job",
        return_value=claimed_job,
    ) as claim_next:
        accepted = client.post(
            "/api/neo/worker/v2/jobs/claim-next",
            headers={"X-Local-Codex-Token": "worker-test-token"},
            json={"worker_id": "worker-1"},
        )
        operator_only = client.post(
            "/api/neo/worker/v2/jobs/claim-next",
            headers={"Authorization": "Bearer operator-test-token"},
            json={"worker_id": "worker-1"},
        )

    assert accepted.status_code == 200
    assert accepted.headers["Cache-Control"] == "no-store, max-age=0"
    assert accepted.json() == {
        "protocol_version": 2,
        "lease_seconds": 45,
        "claim_token_required": True,
        "job_available": True,
        "job": claimed_job,
    }
    assert operator_only.status_code == 401
    claim_next.assert_called_once_with("worker-1")


def test_worker_progress_accepts_empty_model_start_signal(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch(
        "app.routes.neo_guest.service.progress_job",
        return_value={"id": "job-1", "status": "running", "partial_response": None},
    ) as progress_job:
        response = client.post(
            "/api/neo/worker/jobs/job-1/progress",
            headers={"X-Local-Codex-Token": "worker-test-token"},
            json={"worker_id": "worker-1", "partial_response": ""},
        )

    assert response.status_code == 200
    progress_job.assert_called_once_with("job-1", "worker-1", "")


def test_worker_token_cannot_open_operator_inbox(monkeypatch) -> None:
    client = _client(monkeypatch)
    with patch("app.routes.neo_guest.service.claim_next_job", return_value=None):
        response = client.post("/api/neo/worker/jobs/claim-next", headers={"X-Local-Codex-Token": "worker-test-token"}, json={"worker_id": "test-worker"})
    assert response.status_code == 200
    assert response.json()["job_available"] is False
    assert client.get("/api/neo/operator/inbox", headers={"X-Local-Codex-Token": "worker-test-token"}).status_code == 401
