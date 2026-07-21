from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import PMStaleExecutionClaimRecoveryRequest, PMStaleExecutionClaimRecoveryResult
from app.routes import pm_board as pm_board_routes
from app.services import pm_card_service
from app.services.brain_local_action_queue_service import build_brain_local_action


NOW = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
WORKER_ID = "neo-mac-codex-workspace-executor"


class _RecoveryCursor:
    def __init__(self, rows: list[dict], *, cas_fail_ids: set[str] | None = None) -> None:
        self.rows = rows
        self.cas_fail_ids = cas_fail_ids or set()
        self.selected_rows: list[dict] = []
        self.next_row: dict | None = None
        self.update_count = 0
        self.select_params: tuple | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params: tuple) -> None:
        if "FOR UPDATE SKIP LOCKED" in query:
            worker_id, cutoff, limit = params
            self.select_params = params
            eligible: list[dict] = []
            for row in self.rows:
                execution = dict((row.get("payload") or {}).get("execution") or {})
                if str(row.get("status") or "todo").lower() in {"done", "closed", "cancelled", "blocked"}:
                    continue
                if str(execution.get("state") or "").lower() != "running":
                    continue
                if str(execution.get("executor_status") or "").lower() != "running":
                    continue
                if execution.get("executor_worker_id") != worker_id or not execution.get("claim_id"):
                    continue
                if row["updated_at"] > cutoff:
                    continue
                eligible.append(dict(row))
            self.selected_rows = sorted(eligible, key=lambda item: item["updated_at"])[:limit]
            self.next_row = None
            return
        if "UPDATE pm_cards" in query:
            if "SET status = 'blocked'" in query:
                card_id, expected_updated_at, cutoff, worker_id, claim_id = params
                self.next_row = None
                row = next((candidate for candidate in self.rows if candidate["id"] == card_id), None)
                if row is None or card_id in self.cas_fail_ids:
                    return
                execution = dict((row.get("payload") or {}).get("execution") or {})
                if not (
                    row["updated_at"] == expected_updated_at
                    and row["updated_at"] <= cutoff
                    and str(execution.get("state") or "").lower() == "running"
                    and str(execution.get("executor_status") or "").lower() == "running"
                    and execution.get("executor_worker_id") == worker_id
                    and execution.get("claim_id") == claim_id
                ):
                    return
                row.update({"status": "blocked", "updated_at": NOW})
                self.update_count += 1
                self.next_row = {"id": card_id}
                return
            status, payload, card_id, expected_updated_at, cutoff, worker_id, claim_id = params
            self.next_row = None
            row = next((candidate for candidate in self.rows if candidate["id"] == card_id), None)
            if row is None or card_id in self.cas_fail_ids:
                return
            execution = dict((row.get("payload") or {}).get("execution") or {})
            cas_matches = (
                row["updated_at"] == expected_updated_at
                and row["updated_at"] <= cutoff
                and str(execution.get("state") or "").lower() == "running"
                and str(execution.get("executor_status") or "").lower() == "running"
                and execution.get("executor_worker_id") == worker_id
                and execution.get("claim_id") == claim_id
            )
            if not cas_matches:
                return
            row.update({"status": status, "payload": payload, "updated_at": NOW})
            self.update_count += 1
            self.next_row = {"id": card_id}
            return
        raise AssertionError(query)

    def fetchall(self):
        return list(self.selected_rows)

    def fetchone(self):
        return self.next_row


class _Connection:
    def __init__(self, cursor: _RecoveryCursor) -> None:
        self.cursor_instance = cursor
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self) -> None:
        self.commit_count += 1


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self.connection_instance = connection

    def connection(self):
        return self.connection_instance


def _brain_action() -> dict:
    return build_brain_local_action("refresh_persona_review", {})


def _row(
    *,
    execution_mode: str = "brain_local_action",
    target_agent: str = "Brain Local Action",
    worker_id: str = WORKER_ID,
    age_seconds: int = 1_901,
    brain_action: dict | None = None,
) -> dict:
    card_id = str(uuid4())
    claim_id = str(uuid4())
    updated_at = NOW - timedelta(seconds=age_seconds)
    payload = {
        "workspace_key": "shared_ops",
        "execution": {
            "state": "running",
            "executor_status": "running",
            "executor_worker_id": worker_id,
            "claim_id": claim_id,
            "executor_started_at": updated_at.isoformat(),
            "manager_agent": "Jean-Claude",
            "target_agent": target_agent,
            "execution_mode": execution_mode,
            "history": [],
        },
        "_control_plane_authorization": {"signature": "test"},
    }
    if brain_action is not None or execution_mode == "brain_local_action":
        payload["brain_local_action"] = brain_action if brain_action is not None else _brain_action()
    return {
        "id": card_id,
        "title": "Execute local work",
        "owner": "Jean-Claude",
        "status": "in_progress",
        "source": "test",
        "link_type": None,
        "link_id": None,
        "due_at": None,
        "payload": payload,
        "created_at": updated_at - timedelta(minutes=5),
        "updated_at": updated_at,
    }


def _install_db(monkeypatch, rows: list[dict], *, cas_fail_ids: set[str] | None = None):
    cursor = _RecoveryCursor(rows, cas_fail_ids=cas_fail_ids)
    connection = _Connection(cursor)
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(connection))
    monkeypatch.setattr(pm_card_service, "execution_signing_configured", lambda: True)
    monkeypatch.setattr(pm_card_service, "Json", lambda value: value)
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: True)
    monkeypatch.setattr(pm_card_service, "sign_execution_payload", lambda _card_id, value: value)
    return cursor, connection


def _request(**overrides) -> PMStaleExecutionClaimRecoveryRequest:
    return PMStaleExecutionClaimRecoveryRequest(
        worker_id=overrides.get("worker_id", WORKER_ID),
        stale_after_seconds=overrides.get("stale_after_seconds", 1_800),
        limit=overrides.get("limit", 50),
    )


def test_stale_signed_brain_claim_is_requeued_once_by_idempotency_key(monkeypatch) -> None:
    row = _row()
    original_claim_id = row["payload"]["execution"]["claim_id"]
    cursor, _ = _install_db(monkeypatch, [row])

    first = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)
    second = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    execution = row["payload"]["execution"]
    assert first.requeued_count == 1
    assert first.surfaced_count == 0
    assert first.items[0].disposition == "requeued_brain_action"
    assert first.items[0].action == "refresh_persona_review"
    assert execution["state"] == "queued"
    assert execution["executor_status"] == "queued"
    assert execution["claim_id"] is None
    assert execution["executor_worker_id"] is None
    assert execution["last_recovered_claim"]["claim_id"] == original_claim_id
    assert execution["last_recovered_claim"]["automatic_replay"] is True
    assert second.examined_count == 0
    assert cursor.update_count == 1


def test_fresh_claim_and_other_workers_are_not_selected(monkeypatch) -> None:
    fresh = _row(age_seconds=1_799)
    other_worker = _row(worker_id="other-mac-codex-workspace-executor")
    cursor, _ = _install_db(monkeypatch, [fresh, other_worker])

    result = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    assert result.examined_count == 0
    assert cursor.update_count == 0
    assert cursor.select_params == (WORKER_ID, NOW - timedelta(seconds=1_800), 50)
    assert fresh["payload"]["execution"]["state"] == "running"
    assert other_worker["payload"]["execution"]["state"] == "running"


def test_stale_codex_claim_is_surfaced_and_never_replayed(monkeypatch) -> None:
    row = _row(execution_mode="direct", target_agent="Jean-Claude")
    claim_id = row["payload"]["execution"]["claim_id"]
    cursor, _ = _install_db(monkeypatch, [row])

    first = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)
    second = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    execution = row["payload"]["execution"]
    assert first.requeued_count == 0
    assert first.surfaced_count == 1
    assert first.items[0].disposition == "surfaced_manual_review"
    assert row["status"] == "blocked"
    assert execution["state"] == "stale_claim"
    assert execution["executor_status"] == "stale_claim"
    assert execution["claim_id"] == claim_id
    assert execution["manager_attention_required"] is True
    assert execution["stale_claim"]["automatic_replay"] is False
    assert second.examined_count == 0
    assert cursor.update_count == 1


def test_invalid_brain_envelope_is_surfaced_instead_of_replayed(monkeypatch) -> None:
    invalid_action = _brain_action()
    invalid_action["idempotency_key"] = "0" * 64
    row = _row(brain_action=invalid_action)
    _install_db(monkeypatch, [row])

    result = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    assert result.requeued_count == 0
    assert result.surfaced_count == 1
    assert result.items[0].action is None
    assert row["payload"]["execution"]["state"] == "stale_claim"


def test_brain_ingestion_claim_is_surfaced_because_destination_is_not_replay_stable(monkeypatch) -> None:
    ingestion = build_brain_local_action(
        "long_form_ingest",
        {
            "request": {
                "url": "https://example.com/source",
                "title": "Replay boundary",
                "run_refresh": True,
            }
        },
    )
    row = _row(brain_action=ingestion)
    _install_db(monkeypatch, [row])

    result = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    assert result.requeued_count == 0
    assert result.surfaced_count == 1
    assert result.items[0].action == "long_form_ingest"
    assert "not guaranteed stable" in result.items[0].reason
    assert row["payload"]["execution"]["state"] == "stale_claim"


def test_invalid_signature_is_reported_without_mutating_claim(monkeypatch) -> None:
    row = _row()
    original_payload = row["payload"]
    cursor, _ = _install_db(monkeypatch, [row])
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: False)

    result = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    assert result.quarantined_count == 1
    assert result.items[0].disposition == "quarantined_invalid_signature"
    assert row["status"] == "blocked"
    assert row["payload"] is original_payload
    assert row["payload"]["execution"]["state"] == "running"
    assert cursor.update_count == 1


def test_compare_and_swap_miss_cannot_overwrite_changed_claim(monkeypatch) -> None:
    row = _row()
    original_payload = row["payload"]
    cursor, _ = _install_db(monkeypatch, [row], cas_fail_ids={row["id"]})

    result = pm_card_service.recover_stale_execution_claims(_request(), now=NOW)

    assert result.cas_miss_count == 1
    assert result.requeued_count == 0
    assert result.items[0].disposition == "cas_miss"
    assert row["payload"] is original_payload
    assert row["payload"]["execution"]["state"] == "running"
    assert cursor.update_count == 0


def test_recovery_route_returns_typed_result(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    client = TestClient(app)
    expected = PMStaleExecutionClaimRecoveryResult(
        worker_id=WORKER_ID,
        stale_after_seconds=1_800,
        cutoff_at=NOW - timedelta(seconds=1_800),
    )
    monkeypatch.setattr(pm_board_routes.pm_card_service, "recover_stale_execution_claims", lambda _payload: expected)

    response = client.post(
        "/api/pm/execution-claims/recover-stale",
        json={
            "schema_version": "pm_stale_execution_claim_recovery/v1",
            "worker_id": WORKER_ID,
            "stale_after_seconds": 1_800,
            "limit": 50,
        },
    )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "pm_stale_execution_claim_recovery_result/v1"


def test_recovery_request_rejects_an_unsafe_immediate_lease() -> None:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    response = TestClient(app).post(
        "/api/pm/execution-claims/recover-stale",
        json={"worker_id": WORKER_ID, "stale_after_seconds": 1, "limit": 50},
    )

    assert response.status_code == 422
