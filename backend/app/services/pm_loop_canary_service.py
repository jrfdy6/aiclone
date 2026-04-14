from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services import pm_card_service
from app.services.linkedin_owner_review_service import list_owner_review_items


def pm_loop_canary_audit(limit: int = 500) -> dict[str, Any]:
    active_cards = [card for card in pm_card_service.list_cards(limit=limit) if not pm_card_service._is_closed_pm_status(card.status)]
    queue_entries = pm_card_service.list_execution_queue(limit=limit)

    checks = [
        _owner_review_alignment_check(active_cards),
        _host_action_schema_check(active_cards),
        _execution_queue_alignment_check(active_cards, queue_entries),
    ]
    failing = [check for check in checks if check.get("status") != "pass"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "status": "fail" if failing else "pass",
            "checks_run": len(checks),
            "failing_checks": len(failing),
        },
        "checks": checks,
    }


def _owner_review_alignment_check(active_cards: list[Any]) -> dict[str, Any]:
    payload = list_owner_review_items()
    pending_owner_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    pending_queue_ids = sorted(
        str(item.get("queue_id") or "").strip()
        for item in pending_owner_items
        if isinstance(item, dict) and str(item.get("queue_id") or "").strip()
    )
    active_pm_queue_ids = sorted(
        str(((card.payload or {}).get("owner_review") or {}).get("queue_id") or "").strip()
        for card in active_cards
        if pm_card_service._is_owner_decision_gate(card)
        and isinstance((card.payload or {}).get("owner_review"), dict)
        and str(((card.payload or {}).get("owner_review") or {}).get("queue_id") or "").strip()
    )
    missing_in_pm = sorted(set(pending_queue_ids) - set(active_pm_queue_ids))
    extra_in_pm = sorted(set(active_pm_queue_ids) - set(pending_queue_ids))
    return {
        "name": "owner_review_alignment",
        "status": "fail" if missing_in_pm or extra_in_pm else "pass",
        "pending_owner_review_count": len(pending_queue_ids),
        "active_pm_owner_review_count": len(active_pm_queue_ids),
        "missing_in_pm": missing_in_pm,
        "extra_in_pm": extra_in_pm,
    }


def _host_action_schema_check(active_cards: list[Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    checked = 0
    for raw_card in active_cards:
        if not pm_card_service._is_host_action_required_card(raw_card):
            continue
        checked += 1
        card = pm_card_service.decorate_card_for_client(raw_card) or raw_card
        payload = dict(card.payload or {})
        host_action_required = payload.get("host_action_required")
        if not isinstance(host_action_required, dict):
            issues.append({"card_id": card.id, "reason": "missing_host_action_payload"})
            continue
        proof_required = pm_card_service._dedupe_nonempty_strings(host_action_required.get("proof_required"))
        proof_fields = host_action_required.get("proof_fields")
        if proof_required and (not isinstance(proof_fields, list) or len(proof_fields) != len(proof_required)):
            issues.append(
                {
                    "card_id": card.id,
                    "reason": "proof_field_count_mismatch",
                    "required_count": len(proof_required),
                    "field_count": len(proof_fields) if isinstance(proof_fields, list) else 0,
                }
            )
            continue
        if not isinstance(proof_fields, list):
            proof_fields = []
        for index, field in enumerate(proof_fields):
            if not isinstance(field, dict):
                issues.append({"card_id": card.id, "reason": "proof_field_not_object", "index": index})
                continue
            missing_keys = [key for key in ("kind", "label", "requirement") if not str(field.get(key) or "").strip()]
            if missing_keys:
                issues.append(
                    {
                        "card_id": card.id,
                        "reason": "proof_field_missing_keys",
                        "index": index,
                        "missing_keys": missing_keys,
                    }
                )
    return {
        "name": "host_action_schema",
        "status": "fail" if issues else "pass",
        "checked_count": checked,
        "issue_count": len(issues),
        "issues": issues,
    }


def _execution_queue_alignment_check(active_cards: list[Any], queue_entries: list[Any]) -> dict[str, Any]:
    queue_card_ids = {str(entry.card_id) for entry in queue_entries}
    expected_card_ids: list[str] = []
    for card in active_cards:
        if pm_card_service._is_owner_decision_gate(card) or pm_card_service._is_host_action_required_card(card):
            continue
        entry = pm_card_service.build_execution_queue_entry(card)
        if entry is None:
            continue
        execution_state = str(entry.execution_state or "").strip().lower()
        if execution_state in {"queued", "running"}:
            expected_card_ids.append(str(card.id))
    expected_set = set(expected_card_ids)
    missing_from_queue = sorted(expected_set - queue_card_ids)
    extra_in_queue = sorted(queue_card_ids - expected_set)
    return {
        "name": "execution_queue_alignment",
        "status": "fail" if missing_from_queue or extra_in_queue else "pass",
        "expected_count": len(expected_set),
        "actual_count": len(queue_card_ids),
        "missing_from_queue": missing_from_queue,
        "extra_in_queue": extra_in_queue,
    }
