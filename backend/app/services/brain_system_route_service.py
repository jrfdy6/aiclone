from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import PMCard, PMCardCreate, PersonaDelta, PersonaDeltaUpdate, StandupCreate, StandupEntry
from app.services import persona_delta_service, pm_card_service, standup_service
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.workspace_runtime_contract_service import default_standup_kind_for_workspace, standup_participants_for


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

    existing = pm_card_service.find_card_by_signature(title, source_signature)
    if existing is None:
        existing = pm_card_service.find_active_card_by_title(title, workspace_key)
    if existing is not None:
        return existing

    execution_defaults = pm_card_service.execution_defaults_for_workspace(workspace_key)
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
    return pm_card_service.create_card(
        PMCardCreate(
            title=title,
            owner="Jean-Claude",
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
                "instructions": contract["instructions"],
                "acceptance_criteria": contract["acceptance_criteria"],
                "artifacts_expected": contract["artifacts_expected"],
                "completion_contract": contract["completion_contract"],
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
