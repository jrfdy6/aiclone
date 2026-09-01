from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.pm_board import (
    PMCard,
    PMCardCreate,
    PMCardDispatchRequest,
    PMCardUpdate,
)
from app.routes import pm_board as pm_board_routes
from app.security.execution_authorization import sign_execution_payload
from app.services import pm_card_service
from app.services.execution_gate_service import apply_execution_gate


def _owner_resolution(*, decision_id: str = "owner-decision-1") -> dict[str, object]:
    return {
        "schema_version": "pm_owner_decision_resolution/v1",
        "decision_id": decision_id,
        "choice": "retain_until_trigger",
        "state": "retained",
        "decided_by": "Neo",
        "decided_at": "2026-08-26T21:00:00+00:00",
        "bound_execution_gate_intent_hash": "sha256:" + "1" * 64,
        "future_trigger": "Wait for verified new evidence.",
    }


def _execution_approval(*, approval_id: str = "approval-1") -> dict[str, object]:
    return {
        "schema_version": "execution_approval/v1",
        "approval_id": approval_id,
        "approved_by": "Neo",
        "approved_at": "2026-08-26T21:00:00+00:00",
        "surface": "authenticated_railway_frontend",
        "intent_hash": "sha256:" + "2" * 64,
        "policy_version": 1,
        "reason": "Owner approved this exact execution intent.",
        "approved_risk_factors": ["OWNER_JUDGMENT_REQUIRED"],
    }


def _card(*, resolution: dict[str, object] | None = None, status: str = "todo") -> PMCard:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {"workspace_key": "agc", "display_note": "original"}
    if resolution is not None:
        payload["owner_decision_resolution"] = deepcopy(resolution)
    return PMCard(
        id=str(uuid4()),
        title="Keep the bounded AGC recommendation truthful",
        owner="Jean-Claude",
        status=status,
        source="standup-prep:owner-decision-authority-test",
        payload=payload,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize("mutation", ["inject", "alter", "remove"])
@pytest.mark.parametrize("status", ["todo", "review", "done"])
def test_update_card_rejects_generic_owner_decision_receipt_mutation_on_every_card_state(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    status: str,
) -> None:
    receipt = _owner_resolution()
    current = _card(
        resolution=None if mutation == "inject" else receipt,
        status=status,
    )
    proposed_payload = deepcopy(current.payload)
    if mutation == "inject":
        proposed_payload["owner_decision_resolution"] = receipt
    elif mutation == "alter":
        proposed_payload["owner_decision_resolution"] = _owner_resolution(
            decision_id="forged-owner-decision"
        )
    else:
        proposed_payload.pop("owner_decision_resolution")

    monkeypatch.setattr(pm_card_service, "get_pool", lambda: object())
    monkeypatch.setattr(pm_card_service, "get_card", lambda _card_id: current)

    with pytest.raises(
        ValueError,
        match="cannot create, replace, or remove canonical owner-decision authority",
    ):
        pm_card_service.update_card(
            current.id,
            PMCardUpdate(payload=proposed_payload),
        )


def test_owner_decision_receipt_is_preserved_exactly_during_unrelated_safe_update() -> None:
    receipt = _owner_resolution()
    current = _card(resolution=receipt, status="review")
    proposed_payload = {**deepcopy(current.payload), "display_note": "new safe note"}

    pm_card_service._require_update_preserves_owner_decision_resolution(
        current,
        proposed_payload=proposed_payload,
    )

    assert proposed_payload["owner_decision_resolution"] == receipt


def test_generic_create_rejects_client_supplied_owner_decision_receipt() -> None:
    request = PMCardCreate(
        title="Forge a resolved owner decision",
        source="api",
        payload={
            "workspace_key": "agc",
            "owner_decision_resolution": _owner_resolution(),
        },
    )

    with pytest.raises(
        ValueError,
        match="cannot write canonical owner-decision authority",
    ):
        pm_card_service._normalize_card_create_payload(request)


@pytest.mark.parametrize("mutation", ["inject", "alter", "remove"])
@pytest.mark.parametrize("status", ["todo", "review", "done"])
def test_update_card_rejects_generic_execution_approval_mutation_on_every_card_state(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    status: str,
) -> None:
    approval = _execution_approval()
    current = _card(status=status)
    current_payload = deepcopy(current.payload)
    if mutation != "inject":
        current_payload["execution_approval"] = approval
        current = current.model_copy(update={"payload": current_payload})
    proposed_payload = deepcopy(current.payload)
    if mutation == "inject":
        proposed_payload["execution_approval"] = approval
    elif mutation == "alter":
        proposed_payload["execution_approval"] = _execution_approval(
            approval_id="forged-approval"
        )
    else:
        proposed_payload.pop("execution_approval")

    monkeypatch.setattr(pm_card_service, "get_pool", lambda: object())
    monkeypatch.setattr(pm_card_service, "get_card", lambda _card_id: current)

    with pytest.raises(
        ValueError,
        match="cannot create, replace, or remove execution-approval authority",
    ):
        pm_card_service.update_card(
            current.id,
            PMCardUpdate(payload=proposed_payload),
        )


def test_execution_approval_is_preserved_exactly_during_unrelated_safe_update() -> None:
    approval = _execution_approval()
    current = _card(status="review")
    current = current.model_copy(
        update={
            "payload": {
                **deepcopy(current.payload),
                "execution_approval": approval,
            }
        }
    )
    proposed_payload = {**deepcopy(current.payload), "display_note": "new safe note"}

    pm_card_service._require_update_preserves_execution_approval(
        current,
        proposed_payload=proposed_payload,
        proposed_title=current.title,
        proposed_source=current.source,
        governed_transition=False,
    )

    assert proposed_payload["execution_approval"] == approval


def test_generic_create_rejects_client_supplied_execution_approval() -> None:
    request = PMCardCreate(
        title="Forge an approved execution",
        source="api",
        payload={
            "workspace_key": "agc",
            "execution_approval": _execution_approval(),
        },
    )

    with pytest.raises(
        ValueError,
        match="cannot write execution-approval authority",
    ):
        pm_card_service._normalize_card_create_payload(request)


def test_owner_decision_guard_does_not_claim_execution_approval_writer_scope() -> None:
    current = _card()
    proposed_payload = {
        **deepcopy(current.payload),
        "execution_approval": {"schema_version": "execution_approval/v1"},
    }

    # Execution approval still has governed update_card writers that require a
    # separate call-site migration. This narrow guard owns only owner decisions.
    pm_card_service._require_update_preserves_owner_decision_resolution(
        current,
        proposed_payload=proposed_payload,
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(pm_board_routes.router)
    return TestClient(app)


@pytest.mark.parametrize("mutation", ["inject", "alter", "remove"])
def test_generic_patch_route_rejects_owner_decision_receipt_mutation(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    receipt = _owner_resolution()
    current = _card(resolution=None if mutation == "inject" else receipt)
    proposed_payload = deepcopy(current.payload)
    if mutation == "inject":
        proposed_payload["owner_decision_resolution"] = receipt
    elif mutation == "alter":
        proposed_payload["owner_decision_resolution"] = _owner_resolution(
            decision_id="forged-owner-decision"
        )
    else:
        proposed_payload.pop("owner_decision_resolution")

    monkeypatch.setattr(pm_board_routes.pm_card_service, "get_pool", lambda: object())
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "get_card",
        lambda _card_id: current,
    )

    response = _client().patch(
        f"/api/pm/cards/{current.id}",
        json={"payload": proposed_payload},
    )

    assert response.status_code == 400
    assert "cannot create, replace, or remove canonical owner-decision authority" in (
        response.json()["detail"]
    )


def test_generic_patch_route_preserves_exact_receipt_on_unrelated_safe_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _owner_resolution()
    current = _card(resolution=receipt, status="review")
    proposed_payload = {**deepcopy(current.payload), "display_note": "new safe note"}

    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "get_card",
        lambda _card_id: current,
    )

    def safe_update(card_id: str, request: PMCardUpdate) -> PMCard:
        assert card_id == current.id
        assert request.payload is not None
        pm_card_service._require_update_preserves_owner_decision_resolution(
            current,
            proposed_payload=request.payload,
        )
        return current.model_copy(
            update={
                "payload": deepcopy(request.payload),
                "updated_at": datetime.now(timezone.utc),
            }
        )

    monkeypatch.setattr(pm_board_routes.pm_card_service, "update_card", safe_update)
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "decorate_card_for_client",
        lambda card: card,
    )

    response = _client().patch(
        f"/api/pm/cards/{current.id}",
        json={"payload": proposed_payload},
    )

    assert response.status_code == 200
    assert response.json()["payload"]["owner_decision_resolution"] == receipt
    assert response.json()["payload"]["display_note"] == "new safe note"


def test_generic_create_route_rejects_owner_decision_receipt_before_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "get_pool",
        lambda: (_ for _ in ()).throw(AssertionError("forgery reached PM storage")),
    )

    response = _client().post(
        "/api/pm/cards",
        json={
            "title": "Forge a resolved owner decision",
            "source": "api",
            "payload": {
                "workspace_key": "agc",
                "owner_decision_resolution": _owner_resolution(),
            },
        },
    )

    assert response.status_code == 400
    assert "cannot write canonical owner-decision authority" in response.json()["detail"]


@pytest.mark.parametrize("mutation", ["inject", "alter", "remove"])
def test_generic_patch_route_cannot_enable_private_execution_approval_flag(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    approval = _execution_approval()
    current = _card()
    if mutation != "inject":
        current = current.model_copy(
            update={
                "payload": {
                    **deepcopy(current.payload),
                    "execution_approval": approval,
                }
            }
        )
    proposed_payload = deepcopy(current.payload)
    if mutation == "inject":
        proposed_payload["execution_approval"] = approval
    elif mutation == "alter":
        proposed_payload["execution_approval"] = _execution_approval(
            approval_id="forged-approval"
        )
    else:
        proposed_payload.pop("execution_approval")

    monkeypatch.setattr(pm_board_routes.pm_card_service, "get_pool", lambda: object())
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "get_card",
        lambda _card_id: current,
    )

    response = _client().patch(
        f"/api/pm/cards/{current.id}",
        json={
            "payload": proposed_payload,
            "_governed_execution_approval_transition": True,
        },
    )

    assert response.status_code == 400
    assert "cannot create, replace, or remove execution-approval authority" in (
        response.json()["detail"]
    )


def test_generic_create_route_rejects_execution_approval_before_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pm_board_routes.pm_card_service,
        "get_pool",
        lambda: (_ for _ in ()).throw(AssertionError("forgery reached PM storage")),
    )

    response = _client().post(
        "/api/pm/cards",
        json={
            "title": "Forge an approved execution",
            "source": "api",
            "payload": {
                "workspace_key": "agc",
                "execution_approval": _execution_approval(),
            },
        },
    )

    assert response.status_code == 400
    assert "cannot write execution-approval authority" in response.json()["detail"]


class _LockedCursor:
    def __init__(self, pool: "_LockedPool") -> None:
        self.pool = pool
        self.next_row: dict[str, object] | None = None

    def __enter__(self) -> "_LockedCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        if "FOR UPDATE" in query:
            self.pool.lock_count += 1
            self.next_row = deepcopy(self.pool.row)
            return
        if "UPDATE pm_cards" in query:
            self.pool.update_count += 1
            next_status, adapted_payload = params[0], params[1]
            self.pool.row = {
                **self.pool.row,
                "status": next_status,
                "payload": deepcopy(adapted_payload.obj),
                "updated_at": datetime.now(timezone.utc),
            }
            self.next_row = deepcopy(self.pool.row)
            return
        raise AssertionError(f"Unexpected SQL in locked reconciliation test: {query}")

    def fetchone(self) -> dict[str, object] | None:
        return self.next_row


class _LockedConnection:
    def __init__(self, pool: "_LockedPool") -> None:
        self.pool = pool

    def __enter__(self) -> "_LockedConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self, **_kwargs: object) -> _LockedCursor:
        return _LockedCursor(self.pool)

    def commit(self) -> None:
        self.pool.commit_count += 1

    def rollback(self) -> None:
        self.pool.rollback_count += 1


class _LockedPool:
    def __init__(self, card: PMCard) -> None:
        self.row = card.model_dump()
        self.lock_count = 0
        self.update_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def connection(self) -> _LockedConnection:
        return _LockedConnection(self)


def test_locked_owner_decision_reconciliation_and_exact_replay_still_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CONTROL_PLANE_JOB_SIGNING_SECRET",
        "owner-decision-authority-guard-test-secret",
    )
    now = datetime.now(timezone.utc)
    card = PMCard(
        id=str(uuid4()),
        title="Resolve the bounded internal owner-review AGC checklist choice",
        owner="Jean-Claude",
        status="todo",
        source="standup-prep:owner-decision-authority-test",
        payload={
            "workspace_key": "agc",
            "instructions": ["Complete only this bounded internal AGC checklist."],
            "acceptance_criteria": [
                "The bounded internal checklist has a durable receipt."
            ],
            "artifacts_expected": ["bounded AGC checklist receipt"],
            "completion_contract": {
                "source": "standup_promotion",
                "autostart": True,
                "done_when": ["The bounded internal checklist is verified."],
            },
            "execution": {
                "lane": "codex",
                "state": "queued",
                "manager_agent": "Jean-Claude",
                "target_agent": "AGC Operator Agent",
                "workspace_agent": "AGC Operator Agent",
                "execution_mode": "delegated",
                "assigned_runner": "codex",
                "source": "standup_promotion",
            },
        },
        created_at=now,
        updated_at=now,
    )
    gated_payload = apply_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key="agc",
        payload=card.payload,
    )
    card = card.model_copy(
        update={"payload": sign_execution_payload(card.id, gated_payload)}
    )
    gate = pm_card_service._execution_gate_for_card(card)
    pool = _LockedPool(card)
    monkeypatch.setattr(pm_card_service, "get_pool", lambda: pool)

    reconciled, disposition = pm_card_service.reconcile_pm_owner_decision(
        card.id,
        decision_id="canonical-owner-retain-1",
        choice="retain_until_trigger",
        expected_execution_gate_intent_hash=gate["intent_hash"],
        future_trigger="Wait for verified new AGC evidence.",
        decided_by="Neo",
    )
    replayed, replay_disposition = pm_card_service.reconcile_pm_owner_decision(
        card.id,
        decision_id="canonical-owner-retain-1",
        choice="retain_until_trigger",
        expected_execution_gate_intent_hash=gate["intent_hash"],
        future_trigger="Wait for verified new AGC evidence.",
        decided_by="Neo",
    )

    assert disposition == "retained"
    assert replay_disposition == "already_reconciled"
    assert reconciled.payload["owner_decision_resolution"] == (
        replayed.payload["owner_decision_resolution"]
    )
    assert pool.lock_count == 2
    assert pool.update_count == 1
    assert pool.commit_count == 2
    assert pool.rollback_count == 0


def _approval_required_execution_card() -> PMCard:
    now = datetime.now(timezone.utc)
    card = PMCard(
        id=str(uuid4()),
        title="Resolve the bounded internal owner-review AGC checklist choice",
        owner="Jean-Claude",
        status="todo",
        source="standup-prep:execution-approval-authority-test",
        payload={
            "workspace_key": "agc",
            "instructions": ["Complete only this bounded internal AGC checklist."],
            "acceptance_criteria": [
                "The bounded internal checklist has a durable receipt."
            ],
            "artifacts_expected": ["bounded AGC checklist receipt"],
            "completion_contract": {
                "source": "standup_promotion",
                "autostart": True,
                "done_when": ["The bounded internal checklist is verified."],
            },
            "execution": {
                "lane": "codex",
                "state": "queued",
                "manager_agent": "Jean-Claude",
                "target_agent": "AGC Operator Agent",
                "workspace_agent": "AGC Operator Agent",
                "execution_mode": "delegated",
                "assigned_runner": "codex",
                "source": "standup_promotion",
            },
        },
        created_at=now,
        updated_at=now,
    )
    gated_payload = apply_execution_gate(
        card_id=card.id,
        title=card.title,
        source=card.source,
        workspace_key="agc",
        payload=card.payload,
    )
    return card.model_copy(
        update={"payload": sign_execution_payload(card.id, gated_payload)}
    )


def test_confirmed_dispatch_uses_private_governed_execution_approval_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CONTROL_PLANE_JOB_SIGNING_SECRET",
        "execution-approval-dispatch-test-secret",
    )
    card = _approval_required_execution_card()
    assert pm_card_service._execution_gate_for_card(card)["decision"] == "REQUIRE_APPROVAL"
    captured_kwargs: list[dict[str, object]] = []

    def governed_update(
        card_id: str,
        request: PMCardUpdate,
        **kwargs: object,
    ) -> PMCard:
        assert card_id == card.id
        assert request.payload is not None
        captured_kwargs.append(dict(kwargs))
        pm_card_service._require_update_preserves_execution_approval(
            card,
            proposed_payload=request.payload,
            proposed_title=card.title,
            proposed_source=card.source,
            governed_transition=bool(
                kwargs.get("_governed_execution_approval_transition")
            ),
        )
        return card.model_copy(
            update={
                "status": request.status or card.status,
                "payload": sign_execution_payload(card.id, request.payload),
                "updated_at": datetime.now(timezone.utc),
            }
        )

    monkeypatch.setattr(pm_card_service, "get_card", lambda _card_id: card)
    monkeypatch.setattr(pm_card_service, "update_card", governed_update)

    result = pm_card_service.dispatch_card(
        card.id,
        PMCardDispatchRequest(
            target_agent="AGC Operator Agent",
            requested_by="Neo",
            approval_confirmed=True,
            approval_reason="Owner confirmed this exact bounded internal AGC intent.",
        ),
    )

    assert result is not None
    assert captured_kwargs == [{"_governed_execution_approval_transition": True}]
    assert result.card.payload["execution_approval"]["approved_by"] == "Neo"
    assert result.queue_entry.execution_gate_authorization_current is True


@pytest.mark.parametrize("existing_state", ["ready", "queued"])
def test_confirmed_host_action_branches_use_private_governed_approval_writer(
    monkeypatch: pytest.MonkeyPatch,
    existing_state: str,
) -> None:
    monkeypatch.setenv(
        "CONTROL_PLANE_JOB_SIGNING_SECRET",
        "execution-approval-host-action-test-secret",
    )
    now = datetime.now(timezone.utc)
    host_automation = (
        {
            "automation_id": "linkedin_scheduled_writeback",
            "state": "queued",
            "requires_host_confirmation": True,
            "queue_id": "FEEZIE-008",
            "source_card_id": "e548283a-ecac-48f3-b98f-7bcb48dcb35d",
        }
        if existing_state == "queued"
        else None
    )
    payload: dict[str, object] = {
        "workspace_key": "linkedin-os",
        "host_action_required": {
            "summary": (
                "Queue FEEZIE-008 in LinkedIn's native scheduler, then record "
                "the verified scheduled write-back."
            ),
            "steps": [
                "After owner scheduling, update the publishing schedule with the "
                "actual timestamp."
            ],
            "source_card_id": "e548283a-ecac-48f3-b98f-7bcb48dcb35d",
        },
    }
    if host_automation is not None:
        payload["host_action_automation"] = host_automation
    card = PMCard(
        id=str(uuid4()),
        title="Host action required - Schedule FEEZIE-008",
        owner="Neo",
        status="todo",
        source="pm_host_action_required",
        link_type="owner_review",
        payload=payload,
        created_at=now,
        updated_at=now,
    )
    captured_kwargs: list[dict[str, object]] = []

    def governed_update(
        card_id: str,
        request: PMCardUpdate,
        **kwargs: object,
    ) -> PMCard:
        assert card_id == card.id
        assert request.payload is not None
        captured_kwargs.append(dict(kwargs))
        pm_card_service._require_update_preserves_execution_approval(
            card,
            proposed_payload=request.payload,
            proposed_title=card.title,
            proposed_source=card.source,
            governed_transition=bool(
                kwargs.get("_governed_execution_approval_transition")
            ),
        )
        return card.model_copy(
            update={
                "status": request.status or card.status,
                "payload": sign_execution_payload(card.id, request.payload),
                "updated_at": datetime.now(timezone.utc),
            }
        )

    monkeypatch.setattr(pm_card_service, "get_card", lambda _card_id: card)
    monkeypatch.setattr(pm_card_service, "update_card", governed_update)

    result = pm_card_service.queue_host_action_automation(
        card.id,
        legacy_owner_review_compatibility=True,
        requested_by="Neo",
        reason="Owner confirmed the already-completed LinkedIn scheduling write-back.",
        proof_items=["Owner supplied bounded schedule confirmation."],
        queue_id="FEEZIE-008",
    )

    assert result is not None
    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["_governed_execution_approval_transition"] is True
    if existing_state == "queued":
        assert captured_kwargs[0]["_expected_updated_at"] == card.updated_at
    else:
        assert "_expected_updated_at" not in captured_kwargs[0]
    assert result.card.payload["execution_approval"]["approved_by"] == "Neo"
