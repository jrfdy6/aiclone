from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import BrainSignal, BrainSignalCreateRequest, BrainSignalReviewRequest, BrainSignalRouteRequest, PMCardCreate, StandupCreate
from app.services import pm_card_service, standup_service
from app.services.brain_system_route_service import validate_brain_pm_route
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.workspace_runtime_contract_service import default_standup_kind_for_workspace, standup_participants_for
from app.services.workspace_registry_service import canonicalize_workspace_key


ROOT = Path(__file__).resolve().parents[3]
SIGNALS_PATH = ROOT / "memory" / "brain_signals.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _clean_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _clean_text(value)
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _load_signals() -> list[BrainSignal]:
    if not SIGNALS_PATH.exists():
        return []
    signals: list[BrainSignal] = []
    for line in SIGNALS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            signals.append(BrainSignal.model_validate(payload))
        except Exception:
            continue
    return signals


def _write_signals(signals: list[BrainSignal]) -> None:
    SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(signal.model_dump(mode="json"), sort_keys=True) for signal in signals)
    SIGNALS_PATH.write_text((text + "\n") if text else "", encoding="utf-8")


def _source_signature(signal: BrainSignal | BrainSignalCreateRequest) -> tuple[str, str] | None:
    source_ref = _clean_text(signal.source_ref)
    if not source_ref:
        return None
    return (_clean_text(signal.source_kind).lower(), source_ref)


def list_signals(
    *,
    limit: int = 50,
    review_status: str | None = None,
    workspace_key: str | None = None,
) -> list[BrainSignal]:
    normalized_status = _clean_text(review_status).lower()
    normalized_workspace = canonicalize_workspace_key(workspace_key, default="") if workspace_key else ""
    signals = _load_signals()
    if normalized_status:
        signals = [signal for signal in signals if _clean_text(signal.review_status).lower() == normalized_status]
    if normalized_workspace:
        signals = [
            signal
            for signal in signals
            if signal.source_workspace_key == normalized_workspace or normalized_workspace in signal.workspace_candidates
        ]
    return sorted(signals, key=lambda signal: signal.updated_at, reverse=True)[: max(1, min(int(limit or 50), 500))]


def get_signal(signal_id: str) -> BrainSignal | None:
    for signal in _load_signals():
        if signal.id == signal_id:
            return signal
    return None


def create_signal(payload: BrainSignalCreateRequest) -> BrainSignal:
    now = _now()
    workspace_key = canonicalize_workspace_key(payload.source_workspace_key, default="shared_ops")
    candidates = [canonicalize_workspace_key(item, default=item) for item in _clean_list(payload.workspace_candidates)]
    if workspace_key and workspace_key not in candidates:
        candidates.insert(0, workspace_key)

    signals = _load_signals()
    signature = _source_signature(payload)
    existing_index = None
    if signature is not None:
        for index, signal in enumerate(signals):
            if _source_signature(signal) == signature:
                existing_index = index
                break

    if existing_index is not None:
        existing = signals[existing_index]
        updated = existing.model_copy(
            update={
                "source_workspace_key": workspace_key,
                "raw_summary": _clean_text(payload.raw_summary) or existing.raw_summary,
                "digest": _clean_text(payload.digest) or existing.digest,
                "signal_types": _clean_list([*existing.signal_types, *payload.signal_types]),
                "durability": _clean_text(payload.durability) or existing.durability,
                "confidence": _clean_text(payload.confidence) or existing.confidence,
                "actionability": _clean_text(payload.actionability) or existing.actionability,
                "identity_relevance": _clean_text(payload.identity_relevance) or existing.identity_relevance,
                "workspace_candidates": _clean_list([*existing.workspace_candidates, *candidates]),
                "executive_interpretation": {
                    **(existing.executive_interpretation or {}),
                    **(payload.executive_interpretation or {}),
                },
                "route_decision": {
                    **(existing.route_decision or {}),
                    **(payload.route_decision or {}),
                },
                "updated_at": now,
            }
        )
        signals[existing_index] = updated
        _write_signals(signals)
        return updated

    signal = BrainSignal(
        id=str(uuid4()),
        source_kind=_clean_text(payload.source_kind),
        source_ref=_clean_text(payload.source_ref) or None,
        source_workspace_key=workspace_key,
        raw_summary=_clean_text(payload.raw_summary) or _clean_text(payload.digest),
        digest=_clean_text(payload.digest) or None,
        signal_types=_clean_list(payload.signal_types),
        durability=_clean_text(payload.durability) or "unknown",
        confidence=_clean_text(payload.confidence) or "unknown",
        actionability=_clean_text(payload.actionability) or "unknown",
        identity_relevance=_clean_text(payload.identity_relevance) or "unknown",
        workspace_candidates=candidates,
        executive_interpretation=payload.executive_interpretation or {},
        route_decision=payload.route_decision or {},
        review_status="new",
        created_at=now,
        updated_at=now,
    )
    signals.append(signal)
    _write_signals(signals)
    return signal


def review_signal(signal_id: str, payload: BrainSignalReviewRequest) -> BrainSignal | None:
    signals = _load_signals()
    for index, signal in enumerate(signals):
        if signal.id != signal_id:
            continue
        update: dict[str, Any] = {"updated_at": _now()}
        for field in (
            "digest",
            "durability",
            "confidence",
            "actionability",
            "identity_relevance",
            "review_status",
        ):
            value = getattr(payload, field)
            if value is not None:
                update[field] = _clean_text(value)
        if payload.signal_types is not None:
            update["signal_types"] = _clean_list(payload.signal_types)
        if payload.workspace_candidates is not None:
            update["workspace_candidates"] = [
                canonicalize_workspace_key(item, default=item) for item in _clean_list(payload.workspace_candidates)
            ]
        if payload.executive_interpretation is not None:
            update["executive_interpretation"] = {
                key: _clean_text(value)
                for key, value in payload.executive_interpretation.items()
                if _clean_text(key) and _clean_text(value)
            }
        if payload.route_decision is not None:
            update["route_decision"] = payload.route_decision
        updated = signal.model_copy(update=update)
        signals[index] = updated
        _write_signals(signals)
        return updated
    return None


def route_signal(signal_id: str, payload: BrainSignalRouteRequest) -> BrainSignal | None:
    signals = _load_signals()
    for index, signal in enumerate(signals):
        if signal.id != signal_id:
            continue

        workspace_key = canonicalize_workspace_key(payload.workspace_key, default=signal.source_workspace_key or "shared_ops")
        summary = _clean_text(payload.summary) or _clean_text(payload.route_reason) or signal.digest or signal.raw_summary
        now = _now()
        route_result: dict[str, Any] = {
            "route": payload.route,
            "workspace_key": workspace_key,
            "summary": summary,
            "route_reason": _clean_text(payload.route_reason),
            "canonical_memory_targets": _clean_list(payload.canonical_memory_targets),
            "routed_at": now.isoformat(),
        }
        executive_interpretation = {
            **(signal.executive_interpretation or {}),
            **{
                _clean_text(key): _clean_text(value)
                for key, value in (payload.executive_interpretation or {}).items()
                if _clean_text(key) and _clean_text(value)
            },
        }

        if payload.route == "standup":
            standup = _create_signal_standup(signal=signal, workspace_key=workspace_key, summary=summary, requested_kind=payload.standup_kind)
            route_result["standup"] = standup.model_dump(mode="json")
        elif payload.route == "pm":
            pm_card = _create_signal_pm_card(signal=signal, workspace_key=workspace_key, summary=summary, pm_title=payload.pm_title)
            route_result["pm_card"] = pm_card.model_dump(mode="json")
        elif payload.route == "ignore":
            route_result["ignored_reason"] = summary or "Signal explicitly ignored."

        updated = signal.model_copy(
            update={
                "source_workspace_key": workspace_key,
                "workspace_candidates": _clean_list([*signal.workspace_candidates, workspace_key]),
                "executive_interpretation": executive_interpretation,
                "route_decision": {
                    **(signal.route_decision or {}),
                    "latest": route_result,
                    "history": [*(signal.route_decision or {}).get("history", []), route_result],
                },
                "review_status": "ignored" if payload.route == "ignore" else "routed",
                "updated_at": now,
            }
        )
        signals[index] = updated
        _write_signals(signals)
        return updated
    return None


def _create_signal_standup(*, signal: BrainSignal, workspace_key: str, summary: str, requested_kind: str) -> Any:
    standup_kind = requested_kind if requested_kind and requested_kind != "auto" else default_standup_kind_for_workspace(workspace_key)
    participants = standup_participants_for(workspace_key, standup_kind)
    return standup_service.create_standup(
        StandupCreate(
            owner="Jean-Claude",
            workspace_key=workspace_key,
            status="queued",
            needs=[f"Brain Signal routed for meeting review: {signal.raw_summary}"],
            source="brain_signal",
            payload={
                "standup_kind": standup_kind,
                "summary": summary,
                "agenda": [
                    f"Review Brain Signal: {signal.raw_summary}",
                    "Decide whether this stays source-only, becomes memory, becomes PM work, or remains workspace-local.",
                ],
                "participants": participants,
                "brain_signal_id": signal.id,
                "source_kind": signal.source_kind,
                "source_ref": signal.source_ref,
            },
        )
    )


def _create_signal_pm_card(*, signal: BrainSignal, workspace_key: str, summary: str, pm_title: str | None) -> Any:
    title = _clean_text(pm_title)
    if not title:
        raise ValueError("Provide pm_title for PM routes.")
    source_signature = f"brain-signal:{signal.id}:{workspace_key}"
    execution_defaults = pm_card_service.execution_defaults_for_workspace(workspace_key)
    owner = str(execution_defaults.get("manager_agent") or "Jean-Claude").strip() or "Jean-Claude"
    why_pm_now = f"Brain Signal review routed this into executable work: {summary}"
    contract = build_execution_contract(
        title=title,
        workspace_key=workspace_key,
        source="brain_signal",
        reason=why_pm_now,
        instructions=[
            "Use the Brain Signal digest and executive interpretation as the source of truth.",
            "Convert the signal into one bounded workspace outcome without forwarding raw global source intelligence.",
            "Write back the execution result with concrete outcome, artifact, and blocker state.",
        ],
        acceptance_criteria=[
            f"`{title}` produces a bounded execution result inside `{workspace_key}`.",
            "PM write-back cites the Brain Signal and includes a concrete outcome or artifact.",
        ],
        artifacts_expected=[
            "updated PM execution result",
            "workspace-local artifact or execution memo tied to the Brain Signal",
        ],
    )
    source_signal = {
        "kind": "brain_signal",
        "signal_id": signal.id,
        "source_kind": signal.source_kind,
        "source_ref": signal.source_ref,
        "summary": summary,
    }
    validation = validate_brain_pm_route(
        title=title,
        workspace_key=workspace_key,
        summary=summary,
        owner=owner,
        why_pm_now=why_pm_now,
        acceptance_criteria=contract["acceptance_criteria"],
        completion_contract=contract["completion_contract"],
        source_signal=source_signal,
    )
    if not validation["ok"]:
        raise ValueError(str(validation["reason"]))
    existing = pm_card_service.find_card_by_signature(title, source_signature)
    if existing is None:
        existing = pm_card_service.find_active_card_by_title(title, workspace_key)
    if existing is not None:
        raise ValueError("Brain Signal PM route rejected: duplicate active PM card already exists.")
    return pm_card_service.create_card(
        PMCardCreate(
            title=title,
            owner=owner,
            status="todo",
            source=source_signature,
            link_type="brain_signal",
            link_id=signal.id,
            payload={
                "workspace_key": workspace_key,
                "reason": why_pm_now,
                "why_pm_now": why_pm_now,
                "source_signal": source_signal,
                "brain_signal_id": signal.id,
                "brain_signal_summary": summary,
                "route_guardrail": validation,
                "instructions": contract["instructions"],
                "acceptance_criteria": contract["acceptance_criteria"],
                "artifacts_expected": contract["artifacts_expected"],
                "completion_contract": contract["completion_contract"],
                "writeback_requirements": contract["completion_contract"].get("result_requirements", {}),
                "execution": {
                    "lane": "codex",
                    "state": "queued",
                    "manager_agent": execution_defaults["manager_agent"],
                    "target_agent": execution_defaults["target_agent"],
                    "workspace_agent": execution_defaults.get("workspace_agent"),
                    "execution_mode": execution_defaults["execution_mode"],
                    "requested_by": "Brain",
                    "assigned_runner": "codex",
                    "reason": f"Brain routed signal {signal.id}.",
                    "queued_at": _now().isoformat(),
                    "last_transition_at": _now().isoformat(),
                    "source": "brain_signal",
                },
            },
        )
    )
