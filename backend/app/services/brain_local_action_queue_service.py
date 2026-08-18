from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.models import (
    BrainLongFormIngestRequest,
    BrainSignal,
    BrainSignalCreateRequest,
    BrainSignalReviewRequest,
    BrainSignalRouteRequest,
    BrainYouTubeWatchlistIngestRequest,
    LinkedinPerformanceLocalActionRequest,
    PMCard,
    PMCardCreate,
    PMCardUpdate,
)
from app.security.execution_authorization import execution_signing_configured, verify_execution_payload
from app.services import pm_card_service
from app.services.brain_response_privacy_service import sanitize_brain_text


BRAIN_LOCAL_ACTION_SCHEMA = "brain_local_action/v1"
BRAIN_LOCAL_ACTION_MAX_BYTES = 256 * 1024
BRAIN_LOCAL_ACTIONS = frozenset(
    {
        "signal_create",
        "signal_review",
        "signal_route",
        "signal_intake",
        "long_form_ingest",
        "linkedin_performance_record",
        "youtube_watchlist_ingest",
        "refresh_feezie_workspace",
        "refresh_persona_review",
    }
)

_ACTION_TITLES = {
    "signal_create": "Brain: create local signal",
    "signal_review": "Brain: apply local signal review",
    "signal_route": "Brain: route local signal",
    "signal_intake": "Brain: run local signal intake",
    "long_form_ingest": "Brain: ingest long-form source locally",
    "linkedin_performance_record": "Brain: record LinkedIn evidence locally",
    "youtube_watchlist_ingest": "Brain: ingest YouTube source locally",
    "refresh_feezie_workspace": "Brain: refresh FEEZIE workspace locally",
    "refresh_persona_review": "Brain: refresh persona review locally",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _validate_exact_keys(value: Any, allowed: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object.")
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unexpected)}.")
    return dict(value)


def _validated_model_payload(model_type: Any, value: Any, *, label: str) -> dict[str, Any]:
    raw = _validate_exact_keys(value, set(model_type.model_fields), label=label)
    try:
        model = model_type.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return model.model_dump(mode="json", exclude_none=True)


def validate_brain_local_action(value: Any) -> dict[str, Any]:
    envelope = _validate_exact_keys(
        value,
        {"schema_version", "action", "parameters", "idempotency_key", "requested_at"},
        label="brain_local_action",
    )
    if envelope.get("schema_version") != BRAIN_LOCAL_ACTION_SCHEMA:
        raise ValueError("Unsupported Brain local-action schema.")
    action = str(envelope.get("action") or "").strip()
    if action not in BRAIN_LOCAL_ACTIONS:
        raise ValueError("Unsupported Brain local action.")
    parameters = envelope.get("parameters")
    if action == "signal_create":
        raw = _validate_exact_keys(parameters, {"signal"}, label="signal_create parameters")
        normalized = {
            "signal": _validated_model_payload(BrainSignalCreateRequest, raw.get("signal"), label="signal_create signal")
        }
    elif action == "signal_review":
        raw = _validate_exact_keys(parameters, {"signal_id", "review"}, label="signal_review parameters")
        signal_id = str(raw.get("signal_id") or "").strip()
        if not signal_id or len(signal_id) > 128:
            raise ValueError("signal_review requires a bounded signal_id.")
        normalized = {
            "signal_id": signal_id,
            "review": _validated_model_payload(BrainSignalReviewRequest, raw.get("review"), label="signal_review review"),
        }
    elif action == "signal_route":
        raw = _validate_exact_keys(parameters, {"signal_id", "signal", "route"}, label="signal_route parameters")
        signal_id = str(raw.get("signal_id") or "").strip()
        if not signal_id or len(signal_id) > 128:
            raise ValueError("signal_route requires a bounded signal_id.")
        try:
            signal = BrainSignal.model_validate(raw.get("signal"))
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        if signal.id != signal_id:
            raise ValueError("signal_route signal id does not match signal_id.")
        normalized = {
            "signal_id": signal_id,
            "signal": signal.model_dump(mode="json"),
            "route": _validated_model_payload(BrainSignalRouteRequest, raw.get("route"), label="signal_route route"),
        }
    elif action == "signal_intake":
        raw = _validate_exact_keys(
            parameters,
            {
                "include_source_intelligence",
                "include_workspace_attention",
                "include_automation_outputs",
                "source_limit",
                "include_quiet_automation",
            },
            label="signal_intake parameters",
        )
        source_limit_raw = raw.get("source_limit")
        if source_limit_raw is not None:
            try:
                source_limit = int(source_limit_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("signal_intake source_limit must be an integer.") from exc
            if not 1 <= source_limit <= 500:
                raise ValueError("signal_intake source_limit must be between 1 and 500.")
        else:
            source_limit = None
        normalized = {
            "include_source_intelligence": bool(raw.get("include_source_intelligence", True)),
            "include_workspace_attention": bool(raw.get("include_workspace_attention", True)),
            "include_automation_outputs": bool(raw.get("include_automation_outputs", True)),
            "source_limit": source_limit,
            "include_quiet_automation": bool(raw.get("include_quiet_automation", False)),
        }
    elif action == "long_form_ingest":
        raw = _validate_exact_keys(parameters, {"request"}, label="long_form_ingest parameters")
        normalized = {
            "request": _validated_model_payload(BrainLongFormIngestRequest, raw.get("request"), label="long_form_ingest request")
        }
    elif action == "linkedin_performance_record":
        raw = _validate_exact_keys(parameters, {"request"}, label="linkedin_performance_record parameters")
        normalized = {
            "request": _validated_model_payload(
                LinkedinPerformanceLocalActionRequest,
                raw.get("request"),
                label="linkedin_performance_record request",
            )
        }
    elif action == "youtube_watchlist_ingest":
        raw = _validate_exact_keys(parameters, {"request"}, label="youtube_watchlist_ingest parameters")
        normalized = {
            "request": _validated_model_payload(
                BrainYouTubeWatchlistIngestRequest,
                raw.get("request"),
                label="youtube_watchlist_ingest request",
            )
        }
    elif action in {"refresh_feezie_workspace", "refresh_persona_review"}:
        _validate_exact_keys(parameters, set(), label=f"{action} parameters")
        normalized = {}
    else:  # pragma: no cover - the action allowlist rejects this branch first.
        raise ValueError("Unsupported Brain local action.")

    expected_key = hashlib.sha256(_canonical_json({"action": action, "parameters": normalized}).encode("utf-8")).hexdigest()
    supplied_key = str(envelope.get("idempotency_key") or "").strip()
    if supplied_key != expected_key:
        raise ValueError("Brain local-action idempotency key is invalid.")
    requested_at = str(envelope.get("requested_at") or "").strip()
    if not requested_at or len(requested_at) > 64:
        raise ValueError("Brain local-action requested_at is missing or invalid.")
    try:
        datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Brain local-action requested_at must be an ISO-8601 timestamp.") from exc

    validated = {
        "schema_version": BRAIN_LOCAL_ACTION_SCHEMA,
        "action": action,
        "parameters": normalized,
        "idempotency_key": expected_key,
        "requested_at": requested_at,
    }
    if len(_canonical_json(validated).encode("utf-8")) > BRAIN_LOCAL_ACTION_MAX_BYTES:
        raise ValueError("Brain local-action payload exceeds the 256 KB limit.")
    return validated


def build_brain_local_action(action: str, parameters: dict[str, Any]) -> dict[str, Any]:
    normalized_action = str(action or "").strip()
    seed = {"action": normalized_action, "parameters": parameters}
    envelope = {
        "schema_version": BRAIN_LOCAL_ACTION_SCHEMA,
        **seed,
        "idempotency_key": hashlib.sha256(_canonical_json(seed).encode("utf-8")).hexdigest(),
        "requested_at": _now_iso(),
    }
    return validate_brain_local_action(envelope)


def build_brain_local_action_card_request(action: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical PM request that Railway will gate and sign.

    Local launchd jobs use this shape through the authenticated PM endpoint;
    they never need the execution-signing secret and cannot self-sign work.
    """

    envelope = build_brain_local_action(action, parameters)
    trigger_key = f"brain-local-action:{envelope['action']}:{envelope['idempotency_key']}"
    now = _now_iso()
    request = PMCardCreate(
        title=_ACTION_TITLES[envelope["action"]],
        owner="Jean-Claude",
        status="todo",
        source=f"brain_local_action:{envelope['action']}",
        link_type="brain_local_action",
        link_id=str(envelope["parameters"].get("signal_id") or "").strip() or None,
        payload={
            "workspace_key": "shared_ops",
            "scope": "shared_ops",
            "front_door_agent": "Neo",
            "source_agent": "Brain",
            "requested_by": "Neo",
            "trigger_origin": "brain_authenticated_control_plane",
            "trigger_key": trigger_key,
            "reason": "Authenticated Brain mutation requires deterministic execution on the local Codex host.",
            "brain_local_action": envelope,
            "execution": {
                "lane": "codex",
                "state": "queued",
                "manager_agent": "Jean-Claude",
                "target_agent": "Brain Local Action",
                "execution_mode": "brain_local_action",
                "requested_by": "Neo",
                "assigned_runner": "codex_workspace_execution",
                "reason": f"Run signed Brain local action `{envelope['action']}` without model invocation.",
                "queued_at": now,
                "last_transition_at": now,
                "source": "brain_authenticated_control_plane",
            },
        },
    )
    return request.model_dump(mode="json", exclude_none=True)


def enqueue_brain_local_action(action: str, parameters: dict[str, Any]) -> tuple[PMCard, str]:
    if not execution_signing_configured():
        raise RuntimeError("Brain local-action queue is unavailable because signed-job authorization is not configured.")
    card_request = build_brain_local_action_card_request(action, parameters)
    envelope = validate_brain_local_action(card_request["payload"]["brain_local_action"])
    trigger_key = str(card_request["payload"]["trigger_key"])
    existing = pm_card_service.find_active_card_by_trigger_key(trigger_key)
    if existing is not None:
        existing_action = validate_brain_local_action(dict(existing.payload or {}).get("brain_local_action"))
        comparable_keys = ("schema_version", "action", "parameters", "idempotency_key")
        if any(existing_action[key] != envelope[key] for key in comparable_keys):
            raise RuntimeError("Existing Brain local-action card does not match its idempotency key.")
        if not verify_execution_payload(existing.id, dict(existing.payload or {})):
            raise RuntimeError("Existing Brain local-action PM card signature is invalid.")
        existing_payload = dict(existing.payload or {})
        existing_execution = dict(existing_payload.get("execution") or {})
        if str(existing_execution.get("executor_status") or "").strip().lower() == "failed" or str(
            existing_execution.get("state") or ""
        ).strip().lower() == "failed":
            now = _now_iso()
            history = list(existing_execution.get("history") or [])
            history.append(
                {
                    "event": "brain_local_action_requeued",
                    "state": "queued",
                    "requested_by": "Neo",
                    "at": now,
                }
            )
            existing_payload["execution"] = {
                **existing_execution,
                "state": "queued",
                "executor_status": "queued",
                "executor_worker_id": None,
                "executor_started_at": None,
                "executor_finished_at": None,
                "executor_last_error": None,
                "manager_attention_required": False,
                "queued_at": now,
                "last_transition_at": now,
                "history": history[-16:],
            }
            updated = pm_card_service.update_card(existing.id, PMCardUpdate(status="todo", payload=existing_payload))
            if updated is None or not verify_execution_payload(updated.id, dict(updated.payload or {})):
                raise RuntimeError("Failed to requeue the signed Brain local-action PM card.")
            return updated, "requeued"
        return existing, "already_active"
    card = pm_card_service.create_card(PMCardCreate.model_validate(card_request))
    if not verify_execution_payload(card.id, dict(card.payload or {})):
        raise RuntimeError("Brain local-action PM card was not signed correctly.")
    return card, "queued"


def authorize_brain_local_action_card(card_id: str, expected_action: str) -> tuple[PMCard, dict[str, Any]]:
    card = pm_card_service.get_card(card_id)
    if card is None:
        raise ValueError("Brain local-action PM card not found.")
    if not verify_execution_payload(card.id, dict(card.payload or {})):
        raise ValueError("Brain local-action PM card signature is invalid.")
    action = validate_brain_local_action(dict(card.payload or {}).get("brain_local_action"))
    if action["action"] != expected_action:
        raise ValueError("Brain local-action PM card does not authorize this operation.")
    return card, action


def get_linkedin_performance_record_job(card_id: str) -> dict[str, Any]:
    """Return a bounded browser-facing status for one signed ledger action."""

    card, _ = authorize_brain_local_action_card(card_id, "linkedin_performance_record")
    payload = dict(card.payload or {})
    execution = dict(payload.get("execution") or {})
    latest_result = dict(payload.get("latest_execution_result") or {})
    card_status = str(card.status or "todo").strip().lower()
    executor_status = str(execution.get("executor_status") or "").strip().lower()
    execution_state = str(execution.get("state") or "queued").strip().lower()
    if card_status in {"done", "closed"} or latest_result.get("status") == "done":
        status = "completed"
    elif card_status in {"blocked", "failed"} or executor_status == "failed":
        status = "failed"
    elif executor_status == "running" or execution_state == "running":
        status = "running"
    else:
        status = "queued"
    return {
        "job_id": card.id,
        "card_id": card.id,
        "status": status,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
        "completed_at": execution.get("executor_finished_at"),
        "message": sanitize_brain_text(str(latest_result.get("summary") or "")) or None,
        "error": (
            sanitize_brain_text(str(execution.get("executor_last_error") or "")) or None
            if status == "failed"
            else None
        ),
    }


def get_feezie_workspace_refresh_job(card_id: str) -> dict[str, Any]:
    """Return fixed, payload-free status for one signed FEEZIE workspace refresh."""

    card, _ = authorize_brain_local_action_card(card_id, "refresh_feezie_workspace")
    payload = dict(card.payload or {})
    execution = dict(payload.get("execution") or {})
    latest_result = dict(payload.get("latest_execution_result") or {})
    card_status = str(card.status or "todo").strip().lower()
    executor_status = str(execution.get("executor_status") or "").strip().lower()
    execution_state = str(execution.get("state") or "queued").strip().lower()
    if card_status in {"done", "closed"} or latest_result.get("status") == "done":
        status = "completed"
    elif card_status in {"blocked", "failed"} or executor_status == "failed":
        status = "failed"
    elif executor_status == "running" or execution_state == "running":
        status = "running"
    else:
        status = "queued"

    completed_at_raw = execution.get("executor_finished_at")
    if isinstance(completed_at_raw, datetime):
        completed_at_value = completed_at_raw
    elif isinstance(completed_at_raw, str) and 1 <= len(completed_at_raw.strip()) <= 64:
        try:
            completed_at_value = datetime.fromisoformat(completed_at_raw.strip().replace("Z", "+00:00"))
        except ValueError:
            completed_at_value = None
    else:
        completed_at_value = None
    completed_at = (
        completed_at_value.astimezone(timezone.utc).isoformat()
        if completed_at_value is not None
        and completed_at_value.tzinfo is not None
        and completed_at_value.utcoffset() is not None
        else None
    )
    messages = {
        "queued": "FEEZIE workspace refresh is queued for the signed local runner.",
        "running": "FEEZIE workspace refresh is running on the signed local runner.",
        "completed": "FEEZIE workspace refresh completed successfully.",
        "failed": "FEEZIE workspace refresh did not complete.",
    }
    return {
        "job_id": card.id,
        "card_id": card.id,
        "status": status,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
        "completed_at": completed_at,
        "message": messages[status],
        "error_code": "feezie_workspace_refresh_failed" if status == "failed" else None,
    }


def list_youtube_ingest_jobs(limit: int = 12) -> list[dict[str, Any]]:
    cards = pm_card_service.list_cards(limit=max(50, min(500, int(limit or 12) * 6)))
    jobs: list[dict[str, Any]] = []
    for card in cards:
        payload = dict(card.payload or {})
        action = payload.get("brain_local_action")
        if not isinstance(action, dict) or action.get("action") != "youtube_watchlist_ingest":
            continue
        request = dict((action.get("parameters") or {}).get("request") or {})
        execution = dict(payload.get("execution") or {})
        latest_result = dict(payload.get("latest_execution_result") or {})
        card_status = str(card.status or "todo").lower()
        executor_status = str(execution.get("executor_status") or "").strip().lower()
        status = (
            "completed"
            if card_status in {"done", "closed"}
            else "failed"
            if card_status == "blocked" or executor_status == "failed"
            else "running"
            if executor_status == "running"
            else "queued"
        )
        jobs.append(
            {
                "job_id": card.id,
                "card_id": card.id,
                "status": status,
                "url": request.get("url"),
                "title": request.get("title"),
                "channel_name": request.get("channel_name"),
                "created_at": card.created_at,
                "updated_at": card.updated_at,
                "completed_at": execution.get("executor_finished_at"),
                "ingestion_mode": "local_runner",
                "error": execution.get("executor_last_error"),
                "result": latest_result or None,
            }
        )
        if len(jobs) >= max(1, min(int(limit or 12), 100)):
            break
    return jobs
