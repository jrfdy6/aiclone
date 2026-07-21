from __future__ import annotations

import inspect
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest

from app.services import neo_guest_service, open_brain_db


def _service_db(rows):
    cursor = MagicMock()
    cursor.fetchone.side_effect = rows
    cursor.fetchall.return_value = []
    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor
    connection = MagicMock()
    connection.cursor.return_value = cursor_context
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    pool = Mock()
    pool.connection.return_value = connection_context
    return pool, connection, cursor


def _normalized(query: str) -> str:
    return " ".join(str(query).split())


def _approved_selection() -> dict:
    return {
        "pack_version": "7.8.9",
        "entry_ids": ["bio-approved", "win-approved"],
        "selected_count": 2,
        "context": "APPROVED PUBLIC PROFESSIONAL KNOWLEDGE — v7.8.9\nApproved facts only.",
        "response": "Approved facts only.",
    }


def _active_session_rows(*tail):
    return [
        {"invite_id": "invite-1"},
        {"id": "invite-1"},
        {"id": "session-1", "invite_id": "invite-1"},
        *tail,
    ]


def _meeting_payload(client_request_id: str = "00000000-0000-4000-8000-000000000090") -> dict:
    return {
        "client_request_id": client_request_id,
        "visitor_name": "  Test   Visitor ",
        "visitor_email": " Visitor@Example.COM ",
        "visitor_phone": " +1 202  555 0100 ",
        "purpose": " Discuss   a professional partnership ",
        "preferred_times": [" Tuesday   at 2 PM ET "],
        "timezone": " America/New_York ",
    }


def test_professional_profile_has_no_unversioned_factual_bypass() -> None:
    pool, connection, cursor = _service_db(_active_session_rows(None))
    selection = _approved_selection()

    with (
        patch.object(
            neo_guest_service.neo_public_knowledge_service,
            "build_public_knowledge_selection",
            return_value=selection,
        ),
        patch.object(neo_guest_service, "get_pool", return_value=pool),
        patch.object(neo_guest_service, "Json", side_effect=lambda value: value),
    ):
        neo_guest_service.enqueue_message(
            "session-1",
            "Tell me about Johnnie.",
            "00000000-0000-4000-8000-000000000001",
        )

    packet = cursor.execute.call_args_list[-1].args[1][4]
    assert packet["professional_profile"] == selection["context"]
    assert packet["approved_public_response"] == selection["response"]
    assert packet["public_knowledge_metadata"] == {
        "pack_version": "7.8.9",
        "entry_ids": ["bio-approved", "win-approved"],
        "selected_count": 2,
    }
    assert not hasattr(neo_guest_service, "PUBLIC_PROFESSIONAL_PROFILE")
    assert "PUBLIC_PROFESSIONAL_PROFILE" not in inspect.getsource(neo_guest_service)
    connection.commit.assert_called_once_with()


def test_new_client_request_creates_exactly_one_message_and_one_job() -> None:
    pool, connection, cursor = _service_db(_active_session_rows(None))
    request_id = "00000000-0000-4000-8000-000000000010"
    message_id = UUID("00000000-0000-4000-8000-000000000011")
    job_id = UUID("00000000-0000-4000-8000-000000000012")

    with (
        patch.object(neo_guest_service, "get_pool", return_value=pool),
        patch.object(
            neo_guest_service.neo_public_knowledge_service,
            "build_public_knowledge_selection",
            return_value=_approved_selection(),
        ) as build_selection,
        patch.object(neo_guest_service, "uuid4", side_effect=[message_id, job_id]),
        patch.object(neo_guest_service, "Json", side_effect=lambda value: value),
    ):
        result = neo_guest_service.enqueue_message(
            "session-1",
            "Tell me about Johnnie.",
            request_id,
        )

    statements = [_normalized(call.args[0]) for call in cursor.execute.call_args_list]
    assert statements[0] == "SELECT invite_id FROM neo_guest_sessions WHERE id=%s"
    assert "expires_at > clock_timestamp()" in statements[1]
    assert statements[1].endswith("FOR SHARE")
    assert "status='active' FOR UPDATE" in statements[2]
    assert "j.client_request_id=%s" in statements[3]
    assert sum("INSERT INTO neo_guest_messages" in sql for sql in statements) == 1
    assert sum("INSERT INTO neo_guest_jobs" in sql for sql in statements) == 1
    job_insert = cursor.execute.call_args_list[-1]
    assert "client_request_id" in job_insert.args[0]
    assert job_insert.args[1][3] == request_id
    assert result == {
        "job_id": str(job_id),
        "message_id": str(message_id),
        "status": "pending",
    }
    build_selection.assert_called_once_with(
        "Tell me about Johnnie.",
        limit=3,
        max_chars=1_800,
    )
    connection.commit.assert_called_once_with()


def test_same_content_retry_returns_existing_job_without_selection_or_creation() -> None:
    existing = {
        "job_id": UUID("00000000-0000-4000-8000-000000000020"),
        "message_id": UUID("00000000-0000-4000-8000-000000000021"),
        "status": "running",
        "content": "Tell me about Johnnie.",
    }
    pool, connection, cursor = _service_db(_active_session_rows(existing))

    with (
        patch.object(neo_guest_service, "get_pool", return_value=pool),
        patch.object(
            neo_guest_service.neo_public_knowledge_service,
            "build_public_knowledge_selection",
        ) as build_selection,
        patch.object(neo_guest_service, "uuid4") as uuid4,
    ):
        result = neo_guest_service.enqueue_message(
            "session-1",
            "Tell me about Johnnie.",
            "00000000-0000-4000-8000-000000000019",
        )

    assert result == {
        "job_id": str(existing["job_id"]),
        "message_id": str(existing["message_id"]),
        "status": "running",
    }
    build_selection.assert_not_called()
    uuid4.assert_not_called()
    assert len(cursor.execute.call_args_list) == 4
    assert not any(
        "INSERT" in _normalized(call.args[0])
        for call in cursor.execute.call_args_list
    )
    connection.commit.assert_called_once_with()


def test_same_client_request_with_different_content_fails_closed() -> None:
    existing = {
        "job_id": "job-1",
        "message_id": "message-1",
        "status": "pending",
        "content": "Original question",
    }
    pool, connection, cursor = _service_db(_active_session_rows(existing))

    with (
        patch.object(neo_guest_service, "get_pool", return_value=pool),
        patch.object(
            neo_guest_service.neo_public_knowledge_service,
            "build_public_knowledge_selection",
        ) as build_selection,
        patch.object(neo_guest_service, "uuid4") as uuid4,
    ):
        with pytest.raises(neo_guest_service.NeoGuestConflict, match="different message"):
            neo_guest_service.enqueue_message(
                "session-1",
                "Changed question",
                "00000000-0000-4000-8000-000000000029",
            )

    build_selection.assert_not_called()
    uuid4.assert_not_called()
    assert len(cursor.execute.call_args_list) == 4
    connection.commit.assert_not_called()


def test_new_key_pack_failure_persists_nothing() -> None:
    pool, connection, cursor = _service_db(_active_session_rows(None))
    with (
        patch.object(neo_guest_service, "get_pool", return_value=pool),
        patch.object(
            neo_guest_service.neo_public_knowledge_service,
            "build_public_knowledge_selection",
            side_effect=neo_guest_service.neo_public_knowledge_service.NeoPublicKnowledgeError(
                "unsafe source detail"
            ),
        ),
    ):
        with pytest.raises(neo_guest_service.NeoGuestError, match="temporarily unavailable"):
            neo_guest_service.enqueue_message(
                "session-1",
                "Tell me about Johnnie.",
                "00000000-0000-4000-8000-000000000039",
            )

    assert not any(
        "INSERT" in _normalized(call.args[0])
        for call in cursor.execute.call_args_list
    )
    connection.commit.assert_not_called()


def test_schema_adds_lease_column_and_claim_index_idempotently() -> None:
    statements = "\n".join(open_brain_db._BASE_SCHEMA_STATEMENTS)
    assert "lease_expires_at TIMESTAMPTZ" in statements
    assert "claim_token TEXT" in statements
    assert (
        "ALTER TABLE neo_guest_jobs ADD COLUMN IF NOT EXISTS claim_token TEXT"
        in statements
    )
    assert "terminal_claim_token_digest TEXT" in statements
    assert (
        "ALTER TABLE neo_guest_jobs ADD COLUMN IF NOT EXISTS terminal_claim_token_digest TEXT"
        in statements
    )
    assert (
        "ALTER TABLE neo_guest_jobs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ"
        in statements
    )
    assert (
        "CREATE INDEX IF NOT EXISTS neo_guest_jobs_claim_idx "
        "ON neo_guest_jobs(status, lease_expires_at, created_at)"
        in statements
    )
    assert "client_request_id UUID" in statements
    assert (
        "ALTER TABLE neo_guest_jobs ADD COLUMN IF NOT EXISTS client_request_id UUID"
        in statements
    )
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS neo_guest_jobs_session_client_request_uidx "
        "ON neo_guest_jobs(session_id, client_request_id)"
        in statements
    )
    assert "client_request_id UUID, request_fingerprint TEXT" in statements
    assert (
        "ALTER TABLE neo_meeting_requests ADD COLUMN IF NOT EXISTS client_request_id UUID"
        in statements
    )
    assert (
        "ALTER TABLE neo_meeting_requests ADD COLUMN IF NOT EXISTS request_fingerprint TEXT"
        in statements
    )
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS neo_meeting_requests_session_client_request_uidx "
        "ON neo_meeting_requests(session_id, client_request_id)"
        in statements
    )
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS neo_meeting_requests_session_fingerprint_uidx "
        "ON neo_meeting_requests(session_id, request_fingerprint)"
        in statements
    )


def test_claim_atomically_selects_pending_or_stale_running_and_resets_generation() -> None:
    lease_at = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    pool, connection, cursor = _service_db(
        [
            {
                "id": "job-1",
                "session_id": "session-1",
                "context_packet": {},
                "lease_expires_at": lease_at,
                "claim_token": "claim-token-2",
            }
        ]
    )

    with (
        patch.object(neo_guest_service, "get_pool", return_value=pool),
        patch.object(neo_guest_service.secrets, "token_urlsafe", return_value="claim-token-2"),
    ):
        result = neo_guest_service.claim_next_job("worker-2")

    query, params = cursor.execute.call_args.args
    sql = _normalized(query)
    assert "status='pending' OR ( status='running' AND (" in sql
    assert "lease_expires_at <= NOW()" in sql
    assert "lease_expires_at IS NULL" in sql
    assert "GREATEST(progress_at, updated_at, claimed_at, created_at)" in sql
    assert "TIMESTAMPTZ 'epoch'" in sql
    assert "<= NOW() - (%s * INTERVAL '1 second')" in sql
    assert "FOR UPDATE SKIP LOCKED LIMIT 1" in sql
    assert "claimed_by=%s, claim_token=%s" in sql
    assert "lease_expires_at=NOW() + (%s * INTERVAL '1 second')" in sql
    assert "terminal_claim_token_digest=NULL" in sql
    assert "partial_response=NULL" in sql
    assert "model_started_at=NULL" in sql
    assert "first_token_at=NULL" in sql
    assert "progress_at=NULL" in sql
    assert params == (
        neo_guest_service.NEO_GUEST_JOB_LEASE_SECONDS,
        "worker-2",
        "claim-token-2",
        neo_guest_service.NEO_GUEST_JOB_LEASE_SECONDS,
    )
    assert neo_guest_service.NEO_GUEST_JOB_LEASE_SECONDS == 45
    assert result and result["lease_expires_at"] == lease_at.isoformat()
    assert result and result["claim_token"] == "claim-token-2"
    connection.commit.assert_called_once_with()


def test_progress_renews_only_the_current_live_claim() -> None:
    lease_at = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    pool, connection, cursor = _service_db(
        [
            {
                "id": "job-1",
                "status": "running",
                "partial_response": "Draft",
                "lease_expires_at": lease_at,
            }
        ]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        neo_guest_service.progress_job("job-1", "worker-1", "Draft")

    query, params = cursor.execute.call_args.args
    sql = _normalized(query)
    assert "lease_expires_at=NOW() + (%s * INTERVAL '1 second')" in sql
    assert "WHERE id=%s AND status='running' AND claim_token=%s" in sql
    assert "AND lease_expires_at > NOW()" in sql
    assert params == (
        True,
        True,
        "Draft",
        neo_guest_service.NEO_GUEST_JOB_LEASE_SECONDS,
        "job-1",
        "worker-1",
    )
    connection.commit.assert_called_once_with()


def test_completion_is_fenced_and_clears_the_lease() -> None:
    completed_at = datetime(2026, 7, 21, 12, 1, tzinfo=timezone.utc)
    pool, connection, cursor = _service_db(
        [
            {
                "id": "job-1",
                "session_id": "session-1",
                "status": "running",
                "claim_token": "worker-1",
                "terminal_claim_token_digest": None,
                "completed_at": None,
                "lease_is_live": True,
            },
            {"id": "job-1", "status": "completed", "completed_at": completed_at},
        ]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        neo_guest_service.complete_job("job-1", "worker-1", "Final")

    select_sql = _normalized(cursor.execute.call_args_list[0].args[0])
    terminal_sql = _normalized(cursor.execute.call_args_list[-1].args[0])
    assert "FROM neo_guest_jobs WHERE id=%s FOR UPDATE" in select_sql
    assert "lease_expires_at > clock_timestamp()" in select_sql
    assert "lease_expires_at=NULL" in terminal_sql
    assert "claim_token=NULL" in terminal_sql
    assert "terminal_claim_token_digest=%s" in terminal_sql
    assert "WHERE id=%s AND status='running' AND claim_token=%s" in terminal_sql
    assert "AND lease_expires_at > clock_timestamp()" in terminal_sql
    terminal_params = cursor.execute.call_args_list[-1].args[1]
    assert terminal_params[0] == neo_guest_service._claim_token_digest("worker-1")
    assert terminal_params[-2:] == ("job-1", "worker-1")
    connection.commit.assert_called_once_with()


def test_completion_retry_with_same_terminal_token_is_idempotent() -> None:
    completed_at = datetime(2026, 7, 21, 12, 1, tzinfo=timezone.utc)
    digest = neo_guest_service._claim_token_digest("claim-token-1")
    pool, connection, cursor = _service_db(
        [
            {
                "id": "job-1",
                "session_id": "session-1",
                "status": "completed",
                "claim_token": None,
                "terminal_claim_token_digest": digest,
                "completed_at": completed_at,
                "lease_is_live": False,
            }
        ]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool), patch.object(
        neo_guest_service,
        "uuid4",
    ) as uuid4:
        result = neo_guest_service.complete_job(
            "job-1",
            "claim-token-1",
            "A retried payload must not create another message.",
        )

    assert result == {
        "id": "job-1",
        "status": "completed",
        "completed_at": completed_at.isoformat(),
    }
    assert len(cursor.execute.call_args_list) == 1
    assert "INSERT INTO neo_guest_messages" not in _normalized(
        cursor.execute.call_args.args[0]
    )
    uuid4.assert_not_called()
    connection.commit.assert_called_once_with()


def test_completion_retry_with_different_terminal_token_fails_closed() -> None:
    digest = neo_guest_service._claim_token_digest("claim-token-original")
    pool, connection, cursor = _service_db(
        [
            {
                "id": "job-1",
                "session_id": "session-1",
                "status": "completed",
                "claim_token": None,
                "terminal_claim_token_digest": digest,
                "completed_at": datetime(2026, 7, 21, 12, 1, tzinfo=timezone.utc),
                "lease_is_live": False,
            }
        ]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        with pytest.raises(neo_guest_service.NeoGuestConflict, match="not claimed"):
            neo_guest_service.complete_job(
                "job-1",
                "claim-token-stale",
                "Final",
            )

    assert len(cursor.execute.call_args_list) == 1
    connection.commit.assert_not_called()


def test_failure_is_fenced_and_clears_the_lease() -> None:
    failed_at = datetime(2026, 7, 21, 12, 1, tzinfo=timezone.utc)
    pool, connection, cursor = _service_db(
        [{"id": "job-1", "status": "failed", "failed_at": failed_at}]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        neo_guest_service.fail_job("job-1", "worker-1", "safe failure")

    query, params = cursor.execute.call_args.args
    sql = _normalized(query)
    assert "lease_expires_at=NULL" in sql
    assert "claim_token=NULL" in sql
    assert "terminal_claim_token_digest=%s" in sql
    assert "WHERE id=%s AND status='running' AND claim_token=%s" in sql
    assert "AND lease_expires_at > clock_timestamp()" in sql
    assert params == (
        neo_guest_service._claim_token_digest("worker-1"),
        "safe failure",
        "job-1",
        "worker-1",
    )
    connection.commit.assert_called_once_with()


def test_expired_or_wrong_claimant_cannot_write_terminal_state() -> None:
    complete_pool, complete_connection, _complete_cursor = _service_db([None])
    with patch.object(neo_guest_service, "get_pool", return_value=complete_pool):
        try:
            neo_guest_service.complete_job("job-1", "stale-worker", "Final")
        except neo_guest_service.NeoGuestConflict:
            pass
        else:
            raise AssertionError("expired completion must be fenced")
    complete_connection.commit.assert_not_called()

    fail_pool, fail_connection, _fail_cursor = _service_db([None])
    with patch.object(neo_guest_service, "get_pool", return_value=fail_pool):
        try:
            neo_guest_service.fail_job("job-1", "stale-worker", "failure")
        except neo_guest_service.NeoGuestConflict:
            pass
        else:
            raise AssertionError("expired failure must be fenced")
    fail_connection.commit.assert_not_called()


def test_revoked_session_is_rejected_inside_message_transaction() -> None:
    pool, connection, cursor = _service_db(
        [{"invite_id": "invite-1"}, None]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        with pytest.raises(neo_guest_service.NeoGuestUnauthorized, match="revoked"):
            neo_guest_service.enqueue_message(
                "session-1",
                "Tell me about Johnnie.",
                "00000000-0000-4000-8000-000000000080",
            )

    statements = [_normalized(call.args[0]) for call in cursor.execute.call_args_list]
    assert len(statements) == 2
    assert "FOR SHARE" in statements[-1]
    assert "clock_timestamp()" in statements[-1]
    assert not any("INSERT" in statement for statement in statements)
    connection.commit.assert_not_called()


def test_new_meeting_request_is_normalized_serialized_and_idempotent() -> None:
    request_id = UUID("00000000-0000-4000-8000-000000000091")
    pool, connection, cursor = _service_db(_active_session_rows(None, None))

    with patch.object(neo_guest_service, "get_pool", return_value=pool), patch.object(
        neo_guest_service,
        "uuid4",
        return_value=request_id,
    ), patch.object(neo_guest_service, "Json", side_effect=lambda value: value):
        result = neo_guest_service.create_meeting_request(
            "session-1",
            _meeting_payload(),
        )

    statements = [_normalized(call.args[0]) for call in cursor.execute.call_args_list]
    assert statements[0] == "SELECT invite_id FROM neo_guest_sessions WHERE id=%s"
    assert statements[1].endswith("FOR SHARE")
    assert "status='active' FOR UPDATE" in statements[2]
    assert "client_request_id=%s" in statements[3]
    assert "request_fingerprint=%s" in statements[4]
    assert sum("INSERT INTO neo_meeting_requests" in sql for sql in statements) == 1
    meeting_insert = next(
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO neo_meeting_requests" in call.args[0]
    )
    params = meeting_insert.args[1]
    assert params[0] == request_id
    assert params[2] == "00000000-0000-4000-8000-000000000090"
    assert params[4:] == (
        "Test Visitor",
        "visitor@example.com",
        "+1 202 555 0100",
        "Discuss a professional partnership",
        ["Tuesday at 2 PM ET"],
        "America/New_York",
    )
    assert result["id"] == str(request_id)
    connection.commit.assert_called_once_with()


def test_same_normalized_meeting_retry_returns_original_without_insert() -> None:
    normalized = neo_guest_service._normalize_meeting_payload(_meeting_payload())
    existing = {
        "id": UUID("00000000-0000-4000-8000-000000000092"),
        "status": "approved",
        "request_fingerprint": neo_guest_service._meeting_request_fingerprint(normalized),
    }
    pool, connection, cursor = _service_db(_active_session_rows(existing))
    equivalent = _meeting_payload()
    equivalent.update(
        {
            "visitor_name": "Test Visitor",
            "visitor_email": "visitor@example.com",
            "purpose": "Discuss a professional partnership",
            "preferred_times": ["Tuesday at 2 PM ET"],
        }
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool), patch.object(
        neo_guest_service,
        "uuid4",
    ) as uuid4:
        result = neo_guest_service.create_meeting_request("session-1", equivalent)

    assert result["id"] == str(existing["id"])
    assert result["status"] == "approved"
    assert not any(
        "INSERT" in _normalized(call.args[0])
        for call in cursor.execute.call_args_list
    )
    uuid4.assert_not_called()
    connection.commit.assert_called_once_with()


def test_new_meeting_key_with_same_fingerprint_returns_original() -> None:
    original = neo_guest_service._normalize_meeting_payload(_meeting_payload())
    existing = {
        "id": UUID("00000000-0000-4000-8000-000000000093"),
        "status": "pending",
    }
    pool, connection, cursor = _service_db(_active_session_rows(None, existing))
    reloaded = _meeting_payload(
        client_request_id="00000000-0000-4000-8000-000000000094"
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool), patch.object(
        neo_guest_service,
        "uuid4",
    ) as uuid4:
        result = neo_guest_service.create_meeting_request("session-1", reloaded)

    assert result["id"] == str(existing["id"])
    assert result["status"] == "pending"
    fingerprint_query = _normalized(cursor.execute.call_args_list[-1].args[0])
    assert "session_id=%s AND request_fingerprint=%s" in fingerprint_query
    assert cursor.execute.call_args_list[-1].args[1] == (
        "session-1",
        neo_guest_service._meeting_request_fingerprint(original),
    )
    assert not any(
        "INSERT" in _normalized(call.args[0])
        for call in cursor.execute.call_args_list
    )
    uuid4.assert_not_called()
    connection.commit.assert_called_once_with()


def test_same_meeting_key_with_different_payload_fails_closed() -> None:
    original = neo_guest_service._normalize_meeting_payload(_meeting_payload())
    existing = {
        "id": "meeting-1",
        "status": "pending",
        "request_fingerprint": neo_guest_service._meeting_request_fingerprint(original),
    }
    pool, connection, cursor = _service_db(_active_session_rows(existing))
    changed = _meeting_payload()
    changed["purpose"] = "A different purpose"

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        with pytest.raises(neo_guest_service.NeoGuestConflict, match="different meeting"):
            neo_guest_service.create_meeting_request("session-1", changed)

    assert not any(
        "INSERT" in _normalized(call.args[0])
        for call in cursor.execute.call_args_list
    )
    connection.commit.assert_not_called()


def test_revoked_session_is_rejected_inside_meeting_transaction() -> None:
    pool, connection, cursor = _service_db(
        [{"invite_id": "invite-1"}, None]
    )

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        with pytest.raises(neo_guest_service.NeoGuestUnauthorized, match="revoked"):
            neo_guest_service.create_meeting_request(
                "session-1",
                _meeting_payload(),
            )

    statements = [_normalized(call.args[0]) for call in cursor.execute.call_args_list]
    assert len(statements) == 2
    assert not any("INSERT" in statement for statement in statements)
    connection.commit.assert_not_called()


def test_service_rejects_whitespace_only_guest_writes_before_database_access() -> None:
    with patch.object(neo_guest_service, "get_pool") as get_pool:
        with pytest.raises(neo_guest_service.NeoGuestValidationError, match="Message"):
            neo_guest_service.enqueue_message(
                "session-1",
                " \n\t ",
                "00000000-0000-4000-8000-000000000095",
            )
        with pytest.raises(neo_guest_service.NeoGuestValidationError, match="blank"):
            neo_guest_service.create_meeting_request(
                "session-1",
                {**_meeting_payload(), "purpose": "   "},
            )
    get_pool.assert_not_called()


def test_session_bootstrap_is_bounded_chronological_and_resumes_oldest_job() -> None:
    active_job = {
        "job_id": UUID("00000000-0000-4000-8000-000000000096"),
        "client_request_id": UUID("00000000-0000-4000-8000-000000000097"),
        "user_message": "Tell me about Johnnie.",
        "partial_response": "Johnnie is",
    }
    pool, connection, cursor = _service_db(_active_session_rows(active_job))
    cursor.fetchall.return_value = [
        {
            "id": UUID("00000000-0000-4000-8000-000000000099"),
            "role": "assistant",
            "content": "Earlier answer",
            "created_at": datetime(2026, 7, 21, 12, 1, tzinfo=timezone.utc),
        },
        {
            "id": UUID("00000000-0000-4000-8000-000000000098"),
            "role": "user",
            "content": "Tell me about Johnnie.",
            "created_at": datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
        },
    ]

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        result = neo_guest_service.get_session_bootstrap("session-1")

    message_query = _normalized(cursor.execute.call_args_list[3].args[0])
    message_params = cursor.execute.call_args_list[3].args[1]
    job_query = _normalized(cursor.execute.call_args_list[4].args[0])
    assert "ORDER BY created_at DESC, id DESC LIMIT %s" in message_query
    assert message_params == (
        "session-1",
        neo_guest_service.NEO_GUEST_BOOTSTRAP_MESSAGE_LIMIT,
    )
    assert "status IN ('pending', 'running')" in job_query
    assert "ORDER BY j.created_at ASC, j.id ASC LIMIT 1" in job_query
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["id"] == "00000000-0000-4000-8000-000000000098"
    assert result["active_job"] == {
        "job_id": "00000000-0000-4000-8000-000000000096",
        "client_request_id": "00000000-0000-4000-8000-000000000097",
        "user_message": "Tell me about Johnnie.",
        "partial_response": "Johnnie is",
    }
    connection.commit.assert_called_once_with()


def test_session_bootstrap_uses_newest_messages_within_aggregate_content_budget() -> None:
    active_job = {
        "job_id": UUID("00000000-0000-4000-8000-000000000100"),
        "client_request_id": UUID("00000000-0000-4000-8000-000000000101"),
        "user_message": "Latest active question",
        "partial_response": "Latest partial answer",
    }
    pool, _connection, cursor = _service_db(_active_session_rows(active_job))
    cursor.fetchall.return_value = [
        {
            "id": UUID(f"00000000-0000-4000-8000-{index:012d}"),
            "role": "assistant" if index % 2 == 0 else "user",
            "content": chr(65 + (index - 101)) * 8_000,
            "created_at": datetime(
                2026,
                7,
                21,
                12,
                index - 100,
                tzinfo=timezone.utc,
            ),
        }
        for index in (105, 104, 103, 102, 101)
    ]

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        result = neo_guest_service.get_session_bootstrap("session-1")

    assert [item["id"] for item in result["messages"]] == [
        "00000000-0000-4000-8000-000000000102",
        "00000000-0000-4000-8000-000000000103",
        "00000000-0000-4000-8000-000000000104",
        "00000000-0000-4000-8000-000000000105",
    ]
    assert sum(len(item["content"]) for item in result["messages"]) == (
        neo_guest_service.NEO_GUEST_BOOTSTRAP_CONTENT_LIMIT
    )
    assert result["active_job"]["user_message"] == "Latest active question"
    assert result["active_job"]["partial_response"] == "Latest partial answer"


def test_session_bootstrap_rechecks_revocation_before_returning_history() -> None:
    pool, connection, cursor = _service_db(
        [{"invite_id": "invite-1"}, None]
    )
    cursor.fetchall.return_value = [
        {"role": "user", "content": "must not be returned"}
    ]

    with patch.object(neo_guest_service, "get_pool", return_value=pool):
        with pytest.raises(neo_guest_service.NeoGuestUnauthorized, match="revoked"):
            neo_guest_service.get_session_bootstrap("session-1")

    statements = [_normalized(call.args[0]) for call in cursor.execute.call_args_list]
    assert len(statements) == 2
    assert "expires_at > clock_timestamp()" in statements[-1]
    assert not any("neo_guest_messages" in statement for statement in statements)
    connection.commit.assert_not_called()
