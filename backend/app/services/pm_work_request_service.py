from __future__ import annotations

from datetime import datetime, timezone

from app.models import (
    PMCard,
    PMCardCreate,
    PMCardDispatchRequest,
    PMWorkRequestCreate,
    PMWorkRequestResult,
    PMWorkRequestRouting,
)
from app.security.execution_authorization import execution_signing_configured
from app.services import pm_card_service
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.execution_gate_service import BOUNDED_PROJECT_CAPABILITY
from app.services.workspace_registry_service import canonicalize_workspace_key, workspace_registry_map


REQUEST_SOURCE = "codex_native:remote_queue"
REQUEST_ORIGIN = "codex_native_remote_queue"
REQUESTED_BY = "Neo"


def enqueue_work_request(request: PMWorkRequestCreate) -> PMWorkRequestResult:
    """Create one signed PM work order and deliberately place it on the Codex queue."""

    if not execution_signing_configured():
        raise RuntimeError("The signed Codex work queue is not configured.")

    workspace_key, routing = _routing_for_workspace(request.workspace_key)
    outcome = _clean_text(request.outcome)
    if len(outcome) < 3:
        raise ValueError("Describe the outcome you want Codex to deliver.")

    trigger_key = f"codex:request-work:{request.request_id}"
    existing = pm_card_service.find_active_card_by_trigger_key(trigger_key)
    if existing is not None:
        return _ensure_queued(existing, routing=routing, existing_request=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    context = _clean_text(request.context)
    reason = context or outcome
    contract = build_execution_contract(
        title=_work_request_title(outcome),
        workspace_key=workspace_key,
        source=REQUEST_ORIGIN,
        reason=reason,
        acceptance_criteria=request.acceptance_criteria,
        artifacts_expected=request.artifacts_expected,
    )
    contract["instructions"] = _clean_items(
        [f"Deliver this owner-requested outcome: {outcome}", *contract["instructions"]]
    )[:6]

    execution = {
        "lane": "codex",
        "state": "ready",
        "manager_agent": routing.manager_agent,
        "target_agent": routing.target_agent,
        "workspace_agent": routing.workspace_agent,
        "execution_mode": routing.execution_mode,
        "requested_by": REQUESTED_BY,
        "assigned_runner": "codex",
        "reason": reason,
        "last_transition_at": now_iso,
        "source": REQUEST_ORIGIN,
        "capability_id": BOUNDED_PROJECT_CAPABILITY,
    }
    card_payload = {
        "workspace_key": workspace_key,
        "scope": "shared_ops" if workspace_key == "shared_ops" else "workspace",
        "front_door_agent": REQUESTED_BY,
        "source_agent": REQUESTED_BY,
        "requested_by": REQUESTED_BY,
        "goal": outcome,
        "context": context or None,
        "reason": reason,
        "capability_id": BOUNDED_PROJECT_CAPABILITY,
        "instructions": contract["instructions"],
        "acceptance_criteria": contract["acceptance_criteria"],
        "artifacts_expected": contract["artifacts_expected"],
        "completion_contract": contract["completion_contract"],
        "execution": execution,
        "downstream_route": {
            "manager_agent": routing.manager_agent,
            "target_agent": routing.target_agent,
            "workspace_agent": routing.workspace_agent,
            "execution_mode": routing.execution_mode,
        },
        "queue_approval": {
            "approved": True,
            "approved_by": REQUESTED_BY,
            "approved_at": now_iso,
            "surface": "authenticated_railway_frontend",
            "action": "queue_bounded_codex_execution",
            "external_actions_require_separate_approval": True,
        },
        "trigger_key": trigger_key,
        "trigger_origin": REQUEST_ORIGIN,
        "triggered_at": now_iso,
    }
    card = pm_card_service.create_card(
        PMCardCreate(
            title=_work_request_title(outcome),
            owner=REQUESTED_BY,
            status="todo",
            source=REQUEST_SOURCE,
            payload=card_payload,
        )
    )
    return _ensure_queued(card, routing=routing, existing_request=False)


def _ensure_queued(
    card: PMCard,
    *,
    routing: PMWorkRequestRouting,
    existing_request: bool,
) -> PMWorkRequestResult:
    queue_entry = pm_card_service.build_execution_queue_entry(card)
    current_state = str(queue_entry.execution_state if queue_entry is not None else "ready").strip().lower()
    if current_state == "approval_required":
        if queue_entry is None:
            raise RuntimeError("The work order requires approval but has no execution policy record.")
        return PMWorkRequestResult(
            card=pm_card_service.decorate_card_for_client(card) or card,
            queue_entry=queue_entry,
            routing=routing,
            disposition="approval_required",
        )
    if current_state != "ready":
        if queue_entry is None:
            raise RuntimeError("The work order exists but has no execution queue contract.")
        return PMWorkRequestResult(
            card=pm_card_service.decorate_card_for_client(card) or card,
            queue_entry=queue_entry,
            routing=routing,
            disposition="already_active" if existing_request else "queued",
        )

    dispatched = pm_card_service.dispatch_card(
        card.id,
        PMCardDispatchRequest(
            lane="codex",
            requested_by=REQUESTED_BY,
            execution_state="queued",
        ),
    )
    if dispatched is None:
        raise RuntimeError("The work order was created but could not be queued.")
    return PMWorkRequestResult(
        card=pm_card_service.decorate_card_for_client(dispatched.card) or dispatched.card,
        queue_entry=dispatched.queue_entry,
        routing=routing,
        disposition="queued",
    )


def _routing_for_workspace(raw_workspace_key: str) -> tuple[str, PMWorkRequestRouting]:
    canonical = canonicalize_workspace_key(raw_workspace_key, default="shared_ops")
    registry = workspace_registry_map()
    entry = registry.get(canonical)
    if entry is None:
        raise ValueError(f"Unknown project workspace: {raw_workspace_key}")
    return canonical, PMWorkRequestRouting(
        workspace_key=canonical,
        manager_agent=str(entry.get("manager_agent") or "Jean-Claude"),
        target_agent=str(entry.get("target_agent") or entry.get("manager_agent") or "Jean-Claude"),
        workspace_agent=_optional_text(entry.get("workspace_agent")),
        execution_mode=str(entry.get("execution_mode") or "delegated"),
    )


def _work_request_title(outcome: str, limit: int = 108) -> str:
    first_line = next((line.strip() for line in outcome.splitlines() if line.strip()), outcome)
    cleaned = _clean_text(first_line) or "Untitled owner request"
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(1, limit - 1)].rstrip() + "…"


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_items(values: list[object]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        items.append(cleaned)
    return items


def _optional_text(value: object) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None
