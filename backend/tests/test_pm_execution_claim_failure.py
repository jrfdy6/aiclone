from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import PMCard, PMExecutionClaimFailureRequest, PMExecutionResultCommitRequest
from app.routes import pm_board as pm_board_routes
from app.services import pm_card_service
from app.services.brain_local_action_queue_service import build_brain_local_action
from app.services.execution_gate_service import apply_execution_gate


NOW = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
WORKER_ID = "mac-codex-workspace-executor"


class _Cursor:
    def __init__(self, row: dict, *, fail_cas: bool = False) -> None:
        self.row = row
        self.fail_cas = fail_cas
        self.next_row: dict | None = None
        self.update_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params: tuple) -> None:
        if "FOR UPDATE" in query:
            self.next_row = dict(self.row) if self.row else None
            return
        if "UPDATE pm_cards" not in query:
            raise AssertionError(query)

        # The existing result authority sets status and payload; the failure
        # authority sets payload only and repeats every claim CAS predicate.
        if len(params) == 3:
            status, payload, card_id = params
            assert card_id == self.row["id"]
            self.row.update(
                {
                    "status": status,
                    "payload": payload,
                    "updated_at": self.row["updated_at"] + timedelta(microseconds=1),
                }
            )
            self.update_count += 1
            self.next_row = dict(self.row)
            return

        payload, card_id, expected_updated_at, claim_id, worker_id, gate_intent_hash = params
        execution = dict((self.row.get("payload") or {}).get("execution") or {})
        gate = dict((self.row.get("payload") or {}).get("execution_gate") or {})
        matches = (
            not self.fail_cas
            and card_id == self.row["id"]
            and expected_updated_at == self.row["updated_at"]
            and str(self.row.get("status") or "todo").lower()
            not in {"done", "closed", "cancelled", "blocked", "failed"}
            and str(execution.get("state") or "").lower() == "running"
            and str(execution.get("executor_status") or "").lower() == "running"
            and str(execution.get("claim_id") or "") == claim_id
            and str(execution.get("executor_worker_id") or "") == worker_id
            and str(gate.get("intent_hash") or "") == gate_intent_hash
        )
        self.next_row = None
        if not matches:
            return
        self.row.update(
            {
                "payload": payload,
                "updated_at": self.row["updated_at"] + timedelta(microseconds=1),
            }
        )
        self.update_count += 1
        self.next_row = dict(self.row)

    def fetchone(self):
        return self.next_row


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
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

    def rollback(self) -> None:
        return None


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self.connection_instance = connection

    def connection(self):
        return self.connection_instance


def _row() -> dict:
    card_id = str(uuid4())
    claim_id = str(uuid4())
    payload = {
        "workspace_key": "shared_ops",
        "brain_local_action": build_brain_local_action("refresh_persona_review", {}),
        "execution": {
            "state": "running",
            "executor_status": "running",
            "executor_worker_id": WORKER_ID,
            "claim_id": claim_id,
            "executor_started_at": (NOW - timedelta(minutes=1)).isoformat(),
            "execution_packet_sha256": "sha256:" + "c" * 64,
            "result_runner_id": "brain-local-action",
            "result_author_agent": "Brain Local Action",
            "execution_mode": "brain_local_action",
            "target_agent": "Brain Local Action",
            "manager_agent": "Jean-Claude",
            "history": [],
        },
        "_control_plane_authorization": {"signature": "test"},
    }
    payload = apply_execution_gate(
        card_id=card_id,
        title="Run one bounded local action",
        source="brain_local_action:refresh_persona_review",
        workspace_key="shared_ops",
        payload=payload,
    )
    payload["execution"]["claimed_execution_gate_intent_hash"] = payload[
        "execution_gate"
    ]["intent_hash"]
    return {
        "id": card_id,
        "title": "Run one bounded local action",
        "owner": "Jean-Claude",
        "status": "in_progress",
        "source": "brain_local_action:refresh_persona_review",
        "link_type": None,
        "link_id": None,
        "due_at": None,
        "payload": payload,
        "created_at": NOW - timedelta(minutes=5),
        "updated_at": NOW,
    }


def _failure_request(row: dict, **overrides) -> PMExecutionClaimFailureRequest:
    execution = row["payload"]["execution"]
    return PMExecutionClaimFailureRequest(
        card_id=row["id"],
        claim_id=overrides.get("claim_id", execution["claim_id"]),
        failure_id=overrides.get("failure_id", str(uuid4())),
        worker_id=overrides.get("worker_id", WORKER_ID),
        expected_updated_at=overrides.get("expected_updated_at", row["updated_at"]),
        error_message=overrides.get("error_message", "bounded local action failed"),
    )


def _result_request(row: dict) -> PMExecutionResultCommitRequest:
    return PMExecutionResultCommitRequest(
        card_id=row["id"],
        claim_id=row["payload"]["execution"]["claim_id"],
        worker_id=WORKER_ID,
        result_id=str(uuid4()),
        runner_id="brain-local-action",
        author_agent="Brain Local Action",
        created_at=NOW,
        workspace_key="shared_ops",
        title=row["title"],
        status="done",
        summary="The bounded local action completed.",
        outcomes=["A durable local outcome exists."],
        artifacts=["state://memory/runner-results/result.json"],
        result_path="state://memory/runner-results/result.json",
        memo_path="state://memory/runner-memos/result.md",
        work_order_path="repo://dispatch/work-order.json",
        execution_packet_sha256=row["payload"]["execution"]["execution_packet_sha256"],
    )


def _install(
    monkeypatch,
    row: dict,
    *,
    fail_cas: bool = False,
    real_result_signing: bool = False,
) -> _Cursor:
    if real_result_signing:
        monkeypatch.setenv(
            "CONTROL_PLANE_JOB_SIGNING_SECRET",
            "pm-execution-claim-failure-race-test-secret",
        )
        row["payload"] = pm_card_service.sign_execution_payload(
            row["id"],
            row["payload"],
        )
    cursor = _Cursor(row, fail_cas=fail_cas)
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(_Connection(cursor)))
    monkeypatch.setattr(pm_card_service, "Json", lambda value: value)
    if not real_result_signing:
        monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: True)
        monkeypatch.setattr(pm_card_service, "sign_execution_payload", lambda _card_id, value: value)
    return cursor


def test_atomic_claim_failure_is_signed_cas_and_exact_replay_is_idempotent(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row)
    request = _failure_request(row)

    first = pm_card_service.fail_execution_claim(row["id"], request)
    second = pm_card_service.fail_execution_claim(row["id"], request)

    assert first is not None and first[1] == "failed"
    assert second is not None and second[1] == "already_failed"
    assert cursor.update_count == 1
    execution = cursor.row["payload"]["execution"]
    receipt = cursor.row["payload"]["latest_execution_failure"]
    assert execution["state"] == "failed"
    assert execution["executor_status"] == "failed"
    assert execution["claim_id"] == str(request.claim_id)
    assert receipt["failure_id"] == str(request.failure_id)
    assert receipt["claim_id"] == str(request.claim_id)


def test_result_commit_wins_race_and_delayed_failure_cannot_overwrite(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row, real_result_signing=True)
    failure = _failure_request(row)
    result = _result_request(row)

    committed = pm_card_service.commit_execution_result(row["id"], result)
    committed_payload = cursor.row["payload"]
    with pytest.raises(pm_card_service.PMExecutionClaimFailureConflict):
        pm_card_service.fail_execution_claim(row["id"], failure)

    assert committed is not None and committed[1] == "committed"
    assert cursor.update_count == 1
    assert cursor.row["status"] == "done"
    assert cursor.row["payload"] is committed_payload
    assert "latest_execution_failure" not in cursor.row["payload"]


@pytest.mark.parametrize(
    ("winner", "status", "state", "executor_status", "clear_claim"),
    [
        ("owner_reconciliation", "cancelled", "cancelled", None, True),
        ("stale_recovery", "blocked", "stale_claim", "stale_claim", False),
    ],
)
def test_owner_reconciliation_or_stale_recovery_wins_without_stale_failure_overwrite(
    monkeypatch,
    winner: str,
    status: str,
    state: str,
    executor_status: str | None,
    clear_claim: bool,
) -> None:
    row = _row()
    failure = _failure_request(row)
    execution = dict(row["payload"]["execution"])
    execution.update({"state": state, "executor_status": executor_status})
    if clear_claim:
        execution.update({"claim_id": None, "executor_worker_id": None})
    advanced_payload = dict(row["payload"])
    advanced_payload["execution"] = execution
    if winner == "owner_reconciliation":
        advanced_payload["owner_decision_resolution"] = {
            "schema_version": "pm_owner_decision_resolution/v1",
            "decision_id": "owner-decision-won-race",
            "choice": "reject_recommendation",
            "state": "rejected",
            "decided_at": (NOW + timedelta(seconds=1)).isoformat(),
        }
    else:
        execution["stale_claim"] = {
            "claim_id": str(failure.claim_id),
            "detected_at": (NOW + timedelta(seconds=1)).isoformat(),
            "automatic_replay": False,
        }
    row.update(
        {
            "status": status,
            "payload": apply_execution_gate(
                card_id=row["id"],
                title=row["title"],
                source=row["source"],
                workspace_key="shared_ops",
                payload=advanced_payload,
            ),
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    cursor = _install(monkeypatch, row)
    winner_payload = cursor.row["payload"]

    with pytest.raises(pm_card_service.PMExecutionClaimFailureConflict):
        pm_card_service.fail_execution_claim(row["id"], failure)

    assert cursor.update_count == 0
    assert cursor.row["status"] == status
    assert cursor.row["payload"] is winner_payload
    assert "latest_execution_failure" not in cursor.row["payload"]


def test_claim_failure_compare_and_swap_miss_fails_closed(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row, fail_cas=True)
    original_payload = cursor.row["payload"]

    with pytest.raises(pm_card_service.PMExecutionClaimFailureConflict, match="changed before"):
        pm_card_service.fail_execution_claim(row["id"], _failure_request(row))

    assert cursor.update_count == 0
    assert cursor.row["payload"] is original_payload


def test_claim_failure_route_maps_stale_claim_to_409(monkeypatch) -> None:
    row = _row()
    request = _failure_request(row)
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "fail_execution_claim",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            pm_card_service.PMExecutionClaimFailureConflict("newer PM truth won")
        ),
    )

    response = TestClient(app).post(
        f"/api/pm/cards/{row['id']}/fail-execution-claim",
        json=request.model_dump(mode="json"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "newer PM truth won"


def test_claim_failure_route_returns_typed_receipt(monkeypatch) -> None:
    row = _row()
    request = _failure_request(row)
    card = PMCard.model_validate(row)
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "fail_execution_claim",
        lambda *_args, **_kwargs: (card, "failed"),
    )

    response = TestClient(app).post(
        f"/api/pm/cards/{row['id']}/fail-execution-claim",
        json=request.model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["disposition"] == "failed"
    assert response.json()["card"]["id"] == row["id"]
