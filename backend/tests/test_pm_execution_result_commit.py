from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import PMCard, PMExecutionResultCommitRequest
from app.routes import pm_board as pm_board_routes
from app.services import pm_card_service


class _Cursor:
    def __init__(self, row: dict) -> None:
        self.row = row
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
            status, payload, card_id = params
            assert card_id == self.row["id"]
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


def _row(*, card_id: str, claim_id: str, worker_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": card_id,
        "title": "Finish the deterministic action",
        "owner": "Jean-Claude",
        "status": "in_progress",
        "source": "test",
        "link_type": None,
        "link_id": None,
        "due_at": None,
        "payload": {
            "workspace_key": "shared_ops",
            "execution": {
                "state": "running",
                "executor_status": "running",
                "executor_worker_id": worker_id,
                "claim_id": claim_id,
                "manager_agent": "Jean-Claude",
                "target_agent": "Brain Local Action",
                "execution_mode": "brain_local_action",
                "history": [],
            },
            "_control_plane_authorization": {"signature": "test"},
        },
        "created_at": now,
        "updated_at": now,
    }


def _request(*, card_id: str, claim_id: str, worker_id: str, result_id: str | None = None, summary: str = "Done"):
    return PMExecutionResultCommitRequest(
        card_id=card_id,
        claim_id=claim_id,
        worker_id=worker_id,
        result_id=result_id or str(uuid4()),
        runner_id="brain-local-action",
        author_agent="Brain Local Action",
        created_at=datetime.now(timezone.utc),
        workspace_key="shared_ops",
        title="Finish the deterministic action",
        status="done",
        summary=summary,
        outcomes=["The local action completed."],
        artifacts=["/private/result.json", "/private/result.md", "/private/work-order.json"],
        result_path="/private/result.json",
        memo_path="/private/result.md",
        work_order_path="/private/work-order.json",
    )


def test_atomic_result_commit_requires_current_claim_and_is_idempotent(monkeypatch) -> None:
    card_id, claim_id, worker_id = str(uuid4()), str(uuid4()), "mac-runner"
    cursor = _Cursor(_row(card_id=card_id, claim_id=claim_id, worker_id=worker_id))
    connection = _Connection(cursor)
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(connection))
    monkeypatch.setattr(pm_card_service, "Json", lambda value: value)
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: True)
    monkeypatch.setattr(pm_card_service, "sign_execution_payload", lambda _card_id, value: value)
    request = _request(card_id=card_id, claim_id=claim_id, worker_id=worker_id)

    first = pm_card_service.commit_execution_result(card_id, request)
    second = pm_card_service.commit_execution_result(card_id, request)

    assert first is not None and first[1] == "committed"
    assert second is not None and second[1] == "already_committed"
    assert cursor.update_count == 1
    committed = first[0]
    assert committed.status == "done"
    assert committed.payload["execution"]["executor_status"] == "completed"
    assert committed.payload["execution"]["claim_id"] == claim_id
    assert committed.payload["latest_execution_result"]["result_id"] == str(request.result_id)


def test_atomic_result_commit_rejects_wrong_claim(monkeypatch) -> None:
    card_id, claim_id, worker_id = str(uuid4()), str(uuid4()), "mac-runner"
    cursor = _Cursor(_row(card_id=card_id, claim_id=claim_id, worker_id=worker_id))
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(_Connection(cursor)))
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: True)
    request = _request(card_id=card_id, claim_id=str(uuid4()), worker_id=worker_id)

    with pytest.raises(pm_card_service.PMExecutionResultCommitConflict, match="claim_id"):
        pm_card_service.commit_execution_result(card_id, request)
    assert cursor.update_count == 0


def test_replayed_result_id_rejects_changed_content(monkeypatch) -> None:
    card_id, claim_id, worker_id, result_id = str(uuid4()), str(uuid4()), "mac-runner", str(uuid4())
    cursor = _Cursor(_row(card_id=card_id, claim_id=claim_id, worker_id=worker_id))
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: _Pool(_Connection(cursor)))
    monkeypatch.setattr(pm_card_service, "Json", lambda value: value)
    monkeypatch.setattr(pm_card_service, "verify_execution_payload", lambda *_args: True)
    monkeypatch.setattr(pm_card_service, "sign_execution_payload", lambda _card_id, value: value)
    original = _request(card_id=card_id, claim_id=claim_id, worker_id=worker_id, result_id=result_id)
    changed = _request(
        card_id=card_id,
        claim_id=claim_id,
        worker_id=worker_id,
        result_id=result_id,
        summary="Different content",
    )
    pm_card_service.commit_execution_result(card_id, original)

    with pytest.raises(pm_card_service.PMExecutionResultCommitConflict, match="different content"):
        pm_card_service.commit_execution_result(card_id, changed)


def test_execution_result_route_maps_claim_conflict_to_409(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    client = TestClient(app)
    card_id, claim_id, worker_id = str(uuid4()), str(uuid4()), "mac-runner"
    request = _request(card_id=card_id, claim_id=claim_id, worker_id=worker_id)
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "commit_execution_result",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            pm_card_service.PMExecutionResultCommitConflict("claim mismatch")
        ),
    )

    response = client.post(f"/api/pm/cards/{card_id}/execution-result", json=request.model_dump(mode="json"))

    assert response.status_code == 409
    assert response.json()["detail"] == "claim mismatch"


def test_execution_result_route_returns_committed_card(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    client = TestClient(app)
    card_id, claim_id, worker_id = str(uuid4()), str(uuid4()), "mac-runner"
    request = _request(card_id=card_id, claim_id=claim_id, worker_id=worker_id)
    now = datetime.now(timezone.utc)
    card = PMCard(
        id=card_id,
        title=request.title,
        status="done",
        payload={"execution": {"state": "done"}},
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "commit_execution_result",
        lambda *_args, **_kwargs: (card, "committed"),
    )

    response = client.post(f"/api/pm/cards/{card_id}/execution-result", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.json()["disposition"] == "committed"
    assert response.json()["card"]["id"] == card_id

