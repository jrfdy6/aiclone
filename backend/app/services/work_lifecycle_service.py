from __future__ import annotations

from typing import Any

from app.services.brain_signal_service import list_signals
from app.services.pm_card_service import list_cards
from app.services.standup_service import list_standups
from app.services.standup_truth_service import is_verified_meeting_record
from app.utils.ai_clone_clock import clock_receipt, utc_iso, utc_now


LIFECYCLE_STAGES = (
    "captured",
    "interpreted",
    "promoted",
    "routed",
    "executing",
    "written_back",
    "closed",
)


def build_work_lifecycle_report(*, include_samples: bool = True, signal_limit: int = 200, card_limit: int = 200, standup_limit: int = 100) -> dict[str, Any]:
    signals = list_signals(limit=signal_limit)
    try:
        pm_cards = list_cards(limit=card_limit)
    except Exception as exc:
        pm_cards = []
        pm_error = str(exc)
    else:
        pm_error = None
    try:
        standups = list_standups(limit=standup_limit)
    except Exception as exc:
        standups = []
        standup_error = str(exc)
    else:
        standup_error = None

    signal_items = [_signal_item(signal) for signal in signals]
    pm_items = [_pm_card_item(card) for card in pm_cards]
    standup_items: list[dict[str, Any]] = []
    cycle_evaluation_items: list[dict[str, Any]] = []
    unverified_standup_items: list[dict[str, Any]] = []
    for entry in standups:
        record_class = _coordination_record_class(entry)
        if record_class == "verified_meeting":
            standup_items.append(_standup_item(entry))
        elif record_class == "workspace_cycle_evaluation":
            cycle_evaluation_items.append(_cycle_evaluation_item(entry))
        else:
            unverified_standup_items.append(_unverified_standup_item(entry))
    execution_items = [item for item in (_execution_result_item(card) for card in pm_cards) if item is not None]

    summary = {
        "open_count": (
            _count_open(signal_items)
            + _count_open(pm_items)
            + _count_open(standup_items)
            + _count_open(cycle_evaluation_items)
            + _count_open(unverified_standup_items)
        ),
        "written_back_count": _count_stage(pm_items, "written_back") + _count_stage(execution_items, "written_back"),
        "closed_count": (
            _count_stage(signal_items, "closed")
            + _count_stage(pm_items, "closed")
            + _count_stage(standup_items, "closed")
            + _count_stage(cycle_evaluation_items, "closed")
            + _count_stage(unverified_standup_items, "closed")
            + _count_stage(execution_items, "closed")
        ),
    }

    generated_at = utc_now()
    payload: dict[str, Any] = {
        "schema_version": "work_lifecycle_report/v1",
        "generated_at": utc_iso(generated_at),
        "clock": clock_receipt(generated_at),
        "vocabulary": {
            "stages": list(LIFECYCLE_STAGES),
            "sequence": "captured -> interpreted -> promoted -> routed -> executing -> written_back -> closed",
        },
        "summary": summary,
        "brain_signals": _stage_bucket(signal_items, error=None),
        "pm_cards": _stage_bucket(pm_items, error=pm_error),
        "standups": _stage_bucket(standup_items, error=standup_error),
        "workspace_cycle_evaluations": _stage_bucket(cycle_evaluation_items, error=standup_error),
        "unverified_standup_records": _stage_bucket(unverified_standup_items, error=standup_error),
        "execution_results": _stage_bucket(execution_items, error=pm_error),
    }
    if not include_samples:
        for key in (
            "brain_signals",
            "pm_cards",
            "standups",
            "workspace_cycle_evaluations",
            "unverified_standup_records",
            "execution_results",
        ):
            bucket = payload.get(key)
            if isinstance(bucket, dict):
                bucket.pop("samples", None)
    return payload


def _stage_bucket(items: list[dict[str, Any]], *, error: str | None) -> dict[str, Any]:
    counts = {stage: 0 for stage in LIFECYCLE_STAGES}
    for item in items:
        stage = str(item.get("lifecycle_stage") or "")
        if stage in counts:
            counts[stage] += 1
    return {
        "available": error is None,
        "error": error,
        "total": len(items),
        "counts_by_stage": counts,
        "samples": items[:8],
    }


def _count_stage(items: list[dict[str, Any]], stage: str) -> int:
    return sum(1 for item in items if str(item.get("lifecycle_stage") or "") == stage)


def _count_open(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if str(item.get("lifecycle_stage") or "") != "closed")


def _signal_item(signal: Any) -> dict[str, Any]:
    review_status = str(getattr(signal, "review_status", "") or "").lower()
    if review_status == "ignored":
        stage = "closed"
    elif review_status == "routed":
        stage = "routed"
    elif review_status == "reviewed":
        stage = "promoted"
    elif review_status == "in_review":
        stage = "interpreted"
    else:
        stage = "captured"
    route_decision = getattr(signal, "route_decision", {}) or {}
    latest_route = route_decision.get("latest") if isinstance(route_decision, dict) else None
    return {
        "id": getattr(signal, "id", ""),
        "kind": "brain_signal",
        "workspace_key": getattr(signal, "source_workspace_key", "shared_ops"),
        "review_status": getattr(signal, "review_status", ""),
        "lifecycle_stage": stage,
        "downstream_route": latest_route.get("route") if isinstance(latest_route, dict) else None,
        "updated_at": getattr(signal, "updated_at", None).isoformat() if getattr(signal, "updated_at", None) else None,
        "summary": getattr(signal, "digest", None) or getattr(signal, "raw_summary", ""),
    }


def _pm_card_item(card: Any) -> dict[str, Any]:
    payload = getattr(card, "payload", {}) or {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    latest_result = payload.get("latest_execution_result") if isinstance(payload.get("latest_execution_result"), dict) else {}
    stage = _pm_lifecycle_stage(card, execution=execution, latest_result=latest_result)
    return {
        "id": getattr(card, "id", ""),
        "kind": "pm_card",
        "workspace_key": str(payload.get("workspace_key") or payload.get("workspace") or payload.get("belongs_to_workspace") or "shared_ops"),
        "status": getattr(card, "status", ""),
        "execution_state": execution.get("state"),
        "lifecycle_stage": stage,
        "writeback_required": bool(((payload.get("completion_contract") or {}).get("writeback_required"))),
        "has_latest_execution_result": bool(latest_result),
        "updated_at": getattr(card, "updated_at", None).isoformat() if getattr(card, "updated_at", None) else None,
        "title": getattr(card, "title", ""),
    }


def _pm_lifecycle_stage(card: Any, *, execution: dict[str, Any], latest_result: dict[str, Any]) -> str:
    status = str(getattr(card, "status", "") or "").lower()
    execution_state = str(execution.get("state") or "").lower()
    if status in {"done", "closed"} or execution_state == "closed":
        return "closed"
    if latest_result:
        return "written_back"
    if status == "in_progress" or execution_state in {"in_progress", "running", "executing"}:
        return "executing"
    if execution:
        return "routed"
    return "promoted"


def _standup_item(entry: Any) -> dict[str, Any]:
    payload = getattr(entry, "payload", {}) or {}
    status = str(getattr(entry, "status", "") or "").lower()
    if status in {"completed", "closed"}:
        stage = "routed"
    elif status in {"queued", "prepared"}:
        stage = "promoted"
    else:
        stage = "interpreted"
    return {
        "id": getattr(entry, "id", ""),
        "kind": "standup",
        "workspace_key": getattr(entry, "workspace_key", "shared_ops"),
        "status": getattr(entry, "status", ""),
        "source": getattr(entry, "source", None),
        "lifecycle_stage": stage,
        "has_pm_updates": bool(payload.get("pm_updates")),
        "has_memory_promotions": bool(payload.get("memory_promotions")),
        "created_at": getattr(entry, "created_at", None).isoformat() if getattr(entry, "created_at", None) else None,
    }


def _coordination_record_class(entry: Any) -> str:
    payload = getattr(entry, "payload", {}) or {}
    if not isinstance(payload, dict):
        payload = {}
    if (
        payload.get("record_kind") == "workspace_cycle_plan"
        or payload.get("evaluation_only") is True
        or payload.get("meeting_held") is False
    ):
        return "workspace_cycle_evaluation"
    if is_verified_meeting_record(
        payload,
        source=getattr(entry, "source", None),
        workspace_key=getattr(entry, "workspace_key", "shared_ops"),
    ):
        return "verified_meeting"
    return "unverified_standup_record"


def _cycle_evaluation_item(entry: Any) -> dict[str, Any]:
    payload = getattr(entry, "payload", {}) or {}
    status = str(getattr(entry, "status", "") or "").lower()
    stage = "closed" if status in {"completed", "closed"} else "interpreted"
    return {
        "id": getattr(entry, "id", ""),
        "kind": "workspace_cycle_evaluation",
        "workspace_key": getattr(entry, "workspace_key", "shared_ops"),
        "status": getattr(entry, "status", ""),
        "source": getattr(entry, "source", None),
        "lifecycle_stage": stage,
        "meeting_held": False,
        "evaluation_only": True,
        "observed_at": payload.get("observed_at"),
        "created_at": getattr(entry, "created_at", None).isoformat() if getattr(entry, "created_at", None) else None,
    }


def _unverified_standup_item(entry: Any) -> dict[str, Any]:
    payload = getattr(entry, "payload", {}) or {}
    status = str(getattr(entry, "status", "") or "").lower()
    stage = "closed" if status in {"cancelled", "rejected"} else "captured"
    return {
        "id": getattr(entry, "id", ""),
        "kind": "unverified_standup_record",
        "workspace_key": getattr(entry, "workspace_key", "shared_ops"),
        "status": getattr(entry, "status", ""),
        "source": getattr(entry, "source", None),
        "lifecycle_stage": stage,
        "meeting_held": payload.get("meeting_held"),
        "evaluation_only": payload.get("evaluation_only"),
        "created_at": getattr(entry, "created_at", None).isoformat() if getattr(entry, "created_at", None) else None,
    }


def _execution_result_item(card: Any) -> dict[str, Any] | None:
    payload = getattr(card, "payload", {}) or {}
    latest_result = payload.get("latest_execution_result") if isinstance(payload.get("latest_execution_result"), dict) else {}
    if not latest_result:
        return None
    status = str(getattr(card, "status", "") or "").lower()
    stage = "closed" if status in {"done", "closed"} else "written_back"
    return {
        "id": str(latest_result.get("result_id") or ""),
        "kind": "execution_result",
        "workspace_key": str(payload.get("workspace_key") or payload.get("workspace") or payload.get("belongs_to_workspace") or "shared_ops"),
        "card_id": getattr(card, "id", ""),
        "card_title": getattr(card, "title", ""),
        "status": str(latest_result.get("status") or ""),
        "lifecycle_stage": stage,
        "result_path": latest_result.get("result_path"),
        "summary": latest_result.get("summary"),
    }
