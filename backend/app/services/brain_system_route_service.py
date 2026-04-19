from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import PMCard, PMCardCreate, PersonaDelta, PersonaDeltaUpdate, StandupCreate, StandupEntry
from app.services import persona_delta_service, pm_card_service, standup_service
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.workspace_runtime_contract_service import default_standup_kind_for_workspace, standup_participants_for


ACTION_PM_PREFIXES = (
    "align ",
    "backfill ",
    "build ",
    "clarify ",
    "create ",
    "define ",
    "document ",
    "make ",
    "operationalize ",
    "package ",
    "promote ",
    "refine ",
    "resolve ",
    "run ",
    "schedule ",
    "standardize ",
    "tighten ",
    "turn ",
    "validate ",
    "verify ",
    "wire ",
)
ADVISORY_PM_PREFIXES = (
    "workspace execution should ",
    "jean-claude should ",
    "neo should ",
    "yoda should ",
    "keep ",
    "complete ",
    "review ",
    "decide whether ",
    "think about ",
    "consider ",
    "note ",
    "remember ",
)


def route_delta_signal(
    delta_id: str,
    *,
    reflection_excerpt: str | None,
    selected_promotion_items: list[dict[str, Any]] | None,
    workspace_key: str | None,
    workspace_keys: list[str] | None,
    canonical_memory_targets: list[str] | None,
    route_to_standup: bool,
    standup_kind: str,
    route_to_pm: bool,
    pm_title: str | None,
) -> tuple[PersonaDelta, list[str], StandupEntry | None, PMCard | None, list[dict[str, Any]]]:
    delta = persona_delta_service.get_delta(delta_id)
    if delta is None:
        raise ValueError("Persona delta not found.")

    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    selected_items = [item for item in (selected_promotion_items or []) if isinstance(item, dict)]
    if not selected_items:
        existing_items = metadata.get("selected_promotion_items")
        if isinstance(existing_items, list):
            selected_items = [item for item in existing_items if isinstance(item, dict)]

    summary = _build_summary(delta, reflection_excerpt, selected_items)
    if not summary:
        raise ValueError("Add a reflection or select promotion fragments before routing this signal.")

    workspace_targets = _normalize_workspace_targets(primary_workspace_key=workspace_key, workspace_keys=workspace_keys)
    canonical_targets = _normalize_string_list(canonical_memory_targets or [])

    routed_at = _iso_now()
    route_history = list(metadata.get("brain_route_history") or [])
    pending_memory_routes = list(metadata.get("pending_canonical_memory_routes") or [])
    route_results: list[dict[str, Any]] = []

    standup: StandupEntry | None = None
    pm_card: PMCard | None = None

    for index, target_workspace_key in enumerate(workspace_targets):
        resolved_standup_kind = _standup_kind_for_workspace(target_workspace_key, standup_kind)
        target_standup = _create_standup_route(
            delta=delta,
            workspace_key=target_workspace_key,
            standup_kind=resolved_standup_kind,
            summary=summary,
            selected_items=selected_items,
        ) if route_to_standup else None
        target_pm_card = _create_pm_route(
            delta=delta,
            workspace_key=target_workspace_key,
            summary=summary,
            selected_items=selected_items,
            pm_title=pm_title,
        ) if route_to_pm else None

        if index == 0:
            standup = target_standup
            pm_card = target_pm_card

        route_results.append(
            {
                "workspace_key": target_workspace_key,
                "canonical_memory_targets": canonical_targets,
                "standup_kind": resolved_standup_kind if route_to_standup else None,
                "standup": target_standup,
                "pm_card": target_pm_card,
            }
        )

        route_history.append(
            {
                "routed_at": routed_at,
                "workspace_key": target_workspace_key,
                "canonical_memory_targets": canonical_targets,
                "standup_kind": resolved_standup_kind if route_to_standup else None,
                "standup_id": target_standup.id if target_standup else None,
                "pm_card_id": target_pm_card.id if target_pm_card else None,
                "pm_title": target_pm_card.title if target_pm_card else None,
                "selected_promotion_item_ids": [str(item.get("id") or "") for item in selected_items if str(item.get("id") or "")],
                "summary": summary[:500],
            }
        )

        if canonical_targets:
            pending_memory_routes.append(
                {
                    "queued_at": routed_at,
                    "workspace_key": target_workspace_key,
                    "targets": canonical_targets,
                    "summary": summary[:500],
                    "selected_promotion_item_ids": [str(item.get("id") or "") for item in selected_items if str(item.get("id") or "")],
                    "source_delta_id": delta.id,
                    "state": "queued",
                }
            )

    updated = persona_delta_service.update_delta(
        delta.id,
        PersonaDeltaUpdate(
            metadata={
                "brain_route_history": route_history,
                "last_brain_route_at": routed_at,
                "last_brain_route_workspace_key": workspace_targets[0] if workspace_targets else workspace_key,
                "last_brain_route_workspace_keys": workspace_targets,
                "last_brain_route_targets": {
                    "canonical_memory": canonical_targets,
                    "standup": route_to_standup,
                    "standup_kind": standup_kind if route_to_standup else None,
                    "pm": route_to_pm,
                },
                "pending_canonical_memory_routes": pending_memory_routes,
            }
        ),
    )
    if updated is None:
        raise ValueError("Unable to update persona delta route metadata.")

    return updated, canonical_targets, standup, pm_card, route_results


def _build_summary(delta: PersonaDelta, reflection_excerpt: str | None, selected_items: list[dict[str, Any]]) -> str:
    trimmed_reflection = (reflection_excerpt or "").strip()
    if trimmed_reflection:
        return trimmed_reflection
    existing_excerpt = ""
    if isinstance(delta.metadata, dict):
        value = delta.metadata.get("owner_response_excerpt")
        if isinstance(value, str):
            existing_excerpt = value.strip()
    if existing_excerpt:
        return existing_excerpt
    item_fragments = [str(item.get("content") or "").strip() for item in selected_items if str(item.get("content") or "").strip()]
    if item_fragments:
        return f"{delta.trait}: {item_fragments[0][:360]}"
    if (delta.notes or "").strip():
        return (delta.notes or "").strip()
    return (delta.trait or "").strip()


def _create_standup_route(
    *,
    delta: PersonaDelta,
    workspace_key: str,
    standup_kind: str,
    summary: str,
    selected_items: list[dict[str, Any]],
) -> StandupEntry:
    participants = _participants_for(workspace_key, standup_kind)
    agenda = [f"Review routed Brain signal: {delta.trait}"]
    if selected_items:
        agenda.extend(
            [
                f"Evaluate fragment: {str(item.get('label') or item.get('content') or 'promotion fragment')[:120]}"
                for item in selected_items[:3]
            ]
        )
    return standup_service.create_standup(
        StandupCreate(
            owner="Jean-Claude",
            workspace_key=workspace_key,
            status="queued",
            needs=[f"Brain triage queued this signal for meeting review: {delta.trait}"],
            source="brain_triage",
            payload={
                "standup_kind": standup_kind,
                "summary": summary,
                "agenda": agenda,
                "participants": participants,
                "triage_source_delta_id": delta.id,
                "triage_source_capture_id": delta.capture_id,
                "triage_selected_promotion_items": selected_items,
            },
        )
    )


def _create_pm_route(
    *,
    delta: PersonaDelta,
    workspace_key: str,
    summary: str,
    selected_items: list[dict[str, Any]],
    pm_title: str | None,
) -> PMCard:
    source_signature = f"brain-triage:{delta.id}:{workspace_key}"
    title = (pm_title or "").strip() or _default_pm_title(delta)
    execution_defaults = pm_card_service.execution_defaults_for_workspace(workspace_key)
    owner = str(execution_defaults.get("manager_agent") or "Jean-Claude").strip() or "Jean-Claude"
    reason = f"Brain triage routed reviewed signal into executable work: {delta.trait}"
    contract = build_execution_contract(
        title=title,
        workspace_key=workspace_key,
        source="brain_triage",
        reason=reason,
        instructions=[
            "Use the persona-delta routing summary and selected promotion items as the source of truth.",
            "Convert the reviewed signal into a bounded next step inside the target workspace without expanding scope.",
            "Write back a concrete execution result with outcomes and any blockers.",
        ],
        acceptance_criteria=[
            f"`{title}` advances the reviewed signal into a concrete next state inside `{workspace_key}`.",
            "PM write-back includes a bounded summary and at least one concrete outcome or artifact.",
        ],
        artifacts_expected=[
            "updated PM execution result",
            "bounded workspace artifact or execution memo tied to the routed signal",
        ],
    )
    source_signal = {
        "kind": "persona_delta",
        "delta_id": delta.id,
        "capture_id": delta.capture_id,
        "trait": delta.trait,
        "summary": summary,
    }
    validation = validate_brain_pm_route(
        title=title,
        workspace_key=workspace_key,
        summary=summary,
        owner=owner,
        why_pm_now=reason,
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
        raise ValueError("Brain PM route rejected: duplicate active PM card already exists.")

    return pm_card_service.create_card(
        PMCardCreate(
            title=title,
            owner=owner,
            status="todo",
            source=source_signature,
            link_type="persona_delta",
            link_id=delta.id,
            payload={
                "workspace_key": workspace_key,
                "reason": reason,
                "triage_source_delta_id": delta.id,
                "triage_source_capture_id": delta.capture_id,
                "triage_summary": summary,
                "triage_selected_promotion_items": selected_items,
                "source_signal": source_signal,
                "why_pm_now": reason,
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
                    "reason": f"Brain triage routed signal from persona delta {delta.id}.",
                    "queued_at": _iso_now(),
                    "last_transition_at": _iso_now(),
                    "source": "brain_triage",
                },
            },
        )
    )


def _default_pm_title(delta: PersonaDelta) -> str:
    return f"Operationalize reviewed signal: {delta.trait[:120]}".strip()


def validate_brain_pm_route(
    *,
    title: str,
    workspace_key: str,
    summary: str,
    owner: str | None = None,
    why_pm_now: str | None = None,
    acceptance_criteria: list[str] | None = None,
    completion_contract: dict[str, Any] | None = None,
    source_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_title = " ".join(str(title or "").split()).strip()
    normalized_summary = " ".join(str(summary or "").split()).strip()
    normalized_workspace = " ".join(str(workspace_key or "").split()).strip()
    normalized_owner = " ".join(str(owner or "").split()).strip()
    normalized_why_pm_now = " ".join(str(why_pm_now or "").split()).strip()
    if not normalized_title:
        return {"ok": False, "reason": "PM title is required."}
    if not normalized_workspace:
        return {"ok": False, "reason": "Brain PM route rejected: workspace owner boundary is required."}
    lowered = normalized_title.lower()
    if lowered.startswith(ADVISORY_PM_PREFIXES):
        return {
            "ok": False,
            "reason": "Brain PM route rejected: title is advisory language, not executable work.",
            "title": normalized_title,
        }
    if not lowered.startswith(ACTION_PM_PREFIXES):
        return {
            "ok": False,
            "reason": "Brain PM route rejected: title must start with an action-shaped verb.",
            "title": normalized_title,
        }
    if len(normalized_title.split()) < 3:
        return {
            "ok": False,
            "reason": "Brain PM route rejected: title is too short to define bounded work.",
            "title": normalized_title,
        }
    if not normalized_summary:
        return {
            "ok": False,
            "reason": "Brain PM route rejected: routing summary is required.",
            "title": normalized_title,
        }
    if not normalized_owner:
        return {
            "ok": False,
            "reason": "Brain PM route rejected: workspace owner is required.",
            "title": normalized_title,
        }
    if len(normalized_why_pm_now.split()) < 6:
        return {
            "ok": False,
            "reason": "Brain PM route rejected: why_pm_now must explain why this is executable now.",
            "title": normalized_title,
        }
    criteria = [
        " ".join(str(item or "").split()).strip()
        for item in (acceptance_criteria or [])
        if " ".join(str(item or "").split()).strip()
    ]
    if not criteria:
        return {
            "ok": False,
            "reason": "Brain PM route rejected: bounded acceptance criteria are required.",
            "title": normalized_title,
        }
    if any(_looks_unbounded_criterion(item) for item in criteria):
        return {
            "ok": False,
            "reason": "Brain PM route rejected: acceptance criteria are advisory or unbounded.",
            "title": normalized_title,
        }
    contract = completion_contract or {}
    result_requirements = contract.get("result_requirements") if isinstance(contract.get("result_requirements"), dict) else {}
    if not bool(contract.get("writeback_required")) or not bool(result_requirements.get("require_writeback")):
        return {
            "ok": False,
            "reason": "Brain PM route rejected: write-back requirements are missing.",
            "title": normalized_title,
        }
    source_signal_payload = source_signal or {}
    if not isinstance(source_signal_payload, dict) or not str(source_signal_payload.get("kind") or "").strip():
        return {
            "ok": False,
            "reason": "Brain PM route rejected: source signal metadata is required.",
            "title": normalized_title,
        }
    return {
        "ok": True,
        "reason": "Brain PM route accepted: action-shaped title, owner, why-now, bounded criteria, source signal, and write-back contract are present.",
        "title": normalized_title,
        "workspace_key": normalized_workspace,
        "owner": normalized_owner,
        "why_pm_now": normalized_why_pm_now,
        "acceptance_criteria_count": len(criteria),
        "writeback_required": True,
    }


def _looks_unbounded_criterion(value: str) -> bool:
    lowered = value.strip().lower()
    if len(lowered.split()) < 5:
        return True
    return lowered.startswith(
        (
            "review ",
            "consider ",
            "think about ",
            "discuss ",
            "keep in mind ",
            "remember ",
            "note ",
        )
    )


def _participants_for(workspace_key: str, standup_kind: str) -> list[str]:
    return standup_participants_for(workspace_key, standup_kind)


def _normalize_string_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _normalize_workspace_targets(primary_workspace_key: str | None, workspace_keys: list[str] | None) -> list[str]:
    normalized = _normalize_string_list(workspace_keys or [])
    if normalized:
        return normalized
    primary = str(primary_workspace_key or "").strip()
    return [primary] if primary else ["shared_ops"]


def _standup_kind_for_workspace(workspace_key: str, requested_kind: str) -> str:
    if requested_kind and requested_kind != "auto":
        return requested_kind
    return default_standup_kind_for_workspace(workspace_key)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
