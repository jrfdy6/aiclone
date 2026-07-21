from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import PMCard, PMExecutionClaimRequest
from app.routes import pm_board as pm_board_routes
from app.services import pm_card_service
from app.services.execution_gate_service import apply_execution_gate


class _Cursor:
    def __init__(self, row: dict, *, cas_miss: bool = False) -> None:
        self.row = row
        self.cas_miss = cas_miss
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
        if "UPDATE pm_cards" in query:
            status, payload, card_id, expected_updated_at, execution_mode, target_agent = params
            self.next_row = None
            execution = dict((self.row.get("payload") or {}).get("execution") or {})
            matches = (
                not self.cas_miss
                and card_id == self.row["id"]
                and expected_updated_at == self.row["updated_at"]
                and str(self.row.get("status") or "todo").lower()
                not in {"done", "closed", "cancelled", "blocked", "failed"}
                and str(execution.get("state") or "").lower() in {"queued", "running"}
                and str(execution.get("executor_status") or "").lower() in {"", "queued"}
                and execution.get("execution_mode") == execution_mode
                and execution.get("target_agent") == target_agent
            )
            if not matches:
                return
            self.row = {
                **self.row,
                "status": status,
                "payload": payload,
                "updated_at": datetime.now(timezone.utc),
            }
            self.update_count += 1
            self.next_row = dict(self.row)
            return
        raise AssertionError(query)

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


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self.connection_instance = connection

    def connection(self):
        return self.connection_instance


def _row(**execution_overrides) -> dict:
    now = datetime.now(timezone.utc)
    execution = {
        "state": "queued",
        "executor_status": "queued",
        "execution_mode": "brain_local_action",
        "target_agent": "Brain Local Action",
        "history": [],
        **execution_overrides,
    }
    row = {
        "id": str(uuid4()),
        "title": "Claim deterministic work",
        "owner": "Jean-Claude",
        "status": "todo",
        "source": "brain_local_action:signal_intake",
        "link_type": None,
        "link_id": None,
        "due_at": None,
        "payload": {
            "workspace_key": "shared_ops",
            "brain_local_action": {
                "action": "signal_intake",
                "parameters": {},
            },
            "execution": execution,
            "_control_plane_authorization": {"signature": "test"},
        },
        "created_at": now,
        "updated_at": now,
    }
    row["payload"] = apply_execution_gate(
        card_id=row["id"],
        title=row["title"],
        source=row["source"],
        workspace_key="shared_ops",
        payload=row["payload"],
    )
    return row


def _request(*, claim_id: str | None = None, worker_id: str = "mac-worker", **overrides) -> PMExecutionClaimRequest:
    return PMExecutionClaimRequest(
        claim_id=claim_id or str(uuid4()),
        worker_id=worker_id,
        workspace_key=overrides.get("workspace_key", "shared_ops"),
        execution_mode=overrides.get("execution_mode", "brain_local_action"),
        target_agent=overrides.get("target_agent", "Brain Local Action"),
        execution_packet_path=overrides.get("execution_packet_path", "/private/work-order.json"),
    )


def _install(monkeypatch, row: dict, *, cas_miss: bool = False) -> _Cursor:
    cursor = _Cursor(row, cas_miss=cas_miss)
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(_Connection(cursor)))
    monkeypatch.setattr(pm_card_service, "Json", lambda value: value)
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: True)
    monkeypatch.setattr(pm_card_service, "sign_execution_payload", lambda _card_id, value: value)
    return cursor


def test_atomic_claim_promotes_card_and_exact_retry_is_idempotent(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row)
    request = _request()

    first = pm_card_service.claim_execution(row["id"], request)
    second = pm_card_service.claim_execution(row["id"], request)

    assert first is not None and first[1] == "claimed"
    assert second is not None and second[1] == "already_claimed"
    assert cursor.update_count == 1
    execution = first[0].payload["execution"]
    assert first[0].status == "in_progress"
    assert execution["state"] == "running"
    assert execution["executor_status"] == "running"
    assert execution["claim_id"] == str(request.claim_id)
    assert execution["executor_worker_id"] == request.worker_id


def test_two_worker_contention_allows_only_first_claim(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row)

    first = pm_card_service.claim_execution(row["id"], _request(worker_id="worker-a"))
    with pytest.raises(pm_card_service.PMExecutionClaimConflict, match="different active"):
        pm_card_service.claim_execution(row["id"], _request(worker_id="worker-b"))

    assert first is not None and first[1] == "claimed"
    assert cursor.update_count == 1
    assert cursor.row["payload"]["execution"]["executor_worker_id"] == "worker-a"


def test_stale_running_claim_cannot_be_replaced(monkeypatch) -> None:
    row = _row(
        state="running",
        executor_status="running",
        claim_id=str(uuid4()),
        executor_worker_id="dead-worker",
        execution_packet_path="/private/old-work-order.json",
    )
    cursor = _install(monkeypatch, row)

    with pytest.raises(pm_card_service.PMExecutionClaimConflict, match="different active"):
        pm_card_service.claim_execution(row["id"], _request(worker_id="new-worker"))
    assert cursor.update_count == 0


def test_invalid_signature_cannot_be_claimed(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row)
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: False)

    with pytest.raises(pm_card_service.PMExecutionClaimConflict, match="authorization"):
        pm_card_service.claim_execution(row["id"], _request())
    assert cursor.update_count == 0


@pytest.mark.parametrize(
    ("request_overrides", "message"),
    [
        ({"workspace_key": "feezie-os"}, "workspace"),
        ({"execution_mode": "direct"}, "mode"),
        ({"target_agent": "Jean-Claude"}, "target"),
    ],
)
def test_claim_rejects_workspace_mode_and_target_mismatch(monkeypatch, request_overrides, message) -> None:
    row = _row()
    cursor = _install(monkeypatch, row)

    with pytest.raises(pm_card_service.PMExecutionClaimConflict, match=message):
        pm_card_service.claim_execution(row["id"], _request(**request_overrides))
    assert cursor.update_count == 0


@pytest.mark.parametrize("status", ["blocked", "failed", "done"])
def test_claim_rejects_nonclaimable_card_status(monkeypatch, status: str) -> None:
    row = _row()
    row["status"] = status
    cursor = _install(monkeypatch, row)

    with pytest.raises(pm_card_service.PMExecutionClaimConflict, match="claimable status"):
        pm_card_service.claim_execution(row["id"], _request())
    assert cursor.update_count == 0


def test_claim_compare_and_swap_miss_fails_closed(monkeypatch) -> None:
    row = _row()
    cursor = _install(monkeypatch, row, cas_miss=True)

    with pytest.raises(pm_card_service.PMExecutionClaimConflict, match="changed"):
        pm_card_service.claim_execution(row["id"], _request())
    assert cursor.update_count == 0


def test_claim_route_maps_conflict_to_409(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    client = TestClient(app)
    row = _row()
    request = _request()
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "claim_execution",
        lambda *_args: (_ for _ in ()).throw(pm_card_service.PMExecutionClaimConflict("claim conflict")),
    )

    response = client.post(f"/api/pm/cards/{row['id']}/claim-execution", json=request.model_dump(mode="json"))

    assert response.status_code == 409
    assert response.json()["detail"] == "claim conflict"


def test_claim_route_returns_claimed_card(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    client = TestClient(app)
    row = _row()
    request = _request()
    card = PMCard.model_validate(row)
    monkeypatch.setattr(pm_board_routes.pm_card_service, "claim_execution", lambda *_args: (card, "claimed"))

    response = client.post(f"/api/pm/cards/{row['id']}/claim-execution", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.json()["disposition"] == "claimed"
    assert response.json()["card"]["id"] == row["id"]
