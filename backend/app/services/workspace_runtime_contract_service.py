from __future__ import annotations

from typing import Any

from app.services.workspace_registry_service import canonicalize_workspace_key, workspace_registry_entry

EXECUTIVE_STANDUP_KINDS = frozenset({"executive_ops", "operations", "weekly_review", "saturday_vision"})

FEEZIE_RUNTIME_CONTRACT: dict[str, Any] = {
    "display_name": "FEEZIE OS",
    "manager_agent": "Jean-Claude",
    "target_agent": "Jean-Claude",
    "workspace_agent": None,
    "execution_mode": "direct",
    "default_standup_kind": "workspace_sync",
    # FEEZIE does not have a static workspace-sync roster. Its canonical
    # standup relevance plan selects zero, one, or multiple role lenses from
    # the current agenda; meeting closure remains a separate Jean-Claude
    # authority. An explicit empty list prevents the registry's historical
    # trio from leaking back into runtime routing as a selected roster.
    "workspace_sync_participants": [],
    "standup_relevance_required": True,
    "pm_review_policy": {
        "interrupt_policy": "owner_gate_only",
        "default_resolution_mode": "close_and_spawn_next",
        "auto_resolve_review_residue": True,
        "policy_label": "FEEZIE should keep moving after accepted review results and only interrupt you for explicit owner gates or blockers.",
        "default_next_title": "Turn accepted FEEZIE result into the next publishing lane",
        "default_next_reason": "The accepted FEEZIE result should continue into the next concrete publishing step.",
        "followup_templates": [
            {
                "match_any": ["seed", "backlog"],
                "title": "Turn seeded FEEZIE backlog into first draft batch",
                "reason": "The accepted backlog seed should now become concrete first-pass draft production.",
            },
            {
                "match_any": ["draft", "copy", "post"],
                "title": "Package accepted FEEZIE draft into scheduling lane",
                "reason": "The accepted draft should now move into scheduling and release prep.",
            },
            {
                "match_any": ["review", "feedback", "signal"],
                "title": "Turn accepted FEEZIE review result into the next publishing lane",
                "reason": "The accepted review result should continue into the next concrete publishing step.",
            },
        ],
    },
}

WORKSPACE_RUNTIME_CONTRACTS: dict[str, dict[str, Any]] = {
    "shared_ops": {
        "display_name": "Executive Standup",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "workspace_agent": None,
        "execution_mode": "direct",
        "default_standup_kind": "executive_ops",
        "workspace_sync_participants": ["Jean-Claude", "Neo", "Yoda"],
        "pm_review_policy": {
            "interrupt_policy": "manager_attention_only",
            "default_resolution_mode": "close_only",
            "auto_resolve_review_residue": True,
            "policy_label": "Shared Ops should close routine review residue on its own and only interrupt you for blockers or explicit owner gates.",
        },
    },
    "feezie-os": FEEZIE_RUNTIME_CONTRACT,
    "linkedin-os": FEEZIE_RUNTIME_CONTRACT,
    "fusion-os": {
        "display_name": "Fusion OS",
        "manager_agent": "Jean-Claude",
        "target_agent": "Fusion Systems Operator",
        "workspace_agent": "Fusion Systems Operator",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Fusion Systems Operator"],
        "pm_review_policy": {
            "interrupt_policy": "manager_attention_only",
            "default_resolution_mode": "close_only",
            "policy_label": "Fusion OS should close routine review results on its own and only interrupt you for blockers or explicit owner gates.",
        },
    },
    "easyoutfitapp": {
        "display_name": "Easy Outfit App",
        "manager_agent": "Jean-Claude",
        "target_agent": "Easy Outfit App Operator Agent",
        "workspace_agent": "Easy Outfit App Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Easy Outfit App Operator Agent"],
        "pm_review_policy": {
            "interrupt_policy": "manager_attention_only",
            "default_resolution_mode": "close_only",
            "policy_label": "Easy Outfit App should close routine review results on its own and only interrupt you for blockers or explicit owner gates.",
        },
    },
    "ai-swag-store": {
        "display_name": "AI Swag Store",
        "manager_agent": "Jean-Claude",
        "target_agent": "AI Swag Store Operator Agent",
        "workspace_agent": "AI Swag Store Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "AI Swag Store Operator Agent"],
        "pm_review_policy": {
            "interrupt_policy": "manager_attention_only",
            "default_resolution_mode": "close_only",
            "policy_label": "AI Swag Store should close routine review results on its own and only interrupt you for blockers or explicit owner gates.",
        },
    },
    "agc": {
        "display_name": "AGC",
        "manager_agent": "Jean-Claude",
        "target_agent": "AGC Operator Agent",
        "workspace_agent": "AGC Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "AGC Operator Agent"],
        "pm_review_policy": {
            "interrupt_policy": "manager_attention_only",
            "default_resolution_mode": "close_only",
            "policy_label": "AGC should close routine review results on its own and only interrupt you for blockers or explicit owner gates.",
        },
    },
    "work-life-tools": {
        "display_name": "Work Life Tools",
        "manager_agent": "Jean-Claude",
        "target_agent": "Work Life Tools Operator Agent",
        "workspace_agent": "Work Life Tools Operator Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Work Life Tools Operator Agent"],
        "pm_review_policy": {
            "interrupt_policy": "manager_attention_only",
            "default_resolution_mode": "close_only",
            "auto_resolve_review_residue": True,
            "policy_label": "Work Life Tools should close routine internal review results on its own and only interrupt you for blockers, consequential actions, or explicit owner gates.",
        },
    },
}


def runtime_contract_for_workspace(workspace_key: str | None) -> dict[str, Any]:
    normalized = canonicalize_workspace_key(workspace_key, default="shared_ops")
    registry = workspace_registry_entry(normalized)
    contract = dict(WORKSPACE_RUNTIME_CONTRACTS.get(normalized) or {})
    manager_agent = str(contract.get("manager_agent") or registry.get("manager_agent") or "Jean-Claude")
    target_agent = str(contract.get("target_agent") or registry.get("target_agent") or manager_agent)
    workspace_agent = contract.get("workspace_agent") if "workspace_agent" in contract else registry.get("workspace_agent")
    configured_participants = (
        contract.get("workspace_sync_participants")
        if "workspace_sync_participants" in contract
        else registry.get("workspace_sync_participants")
    )
    if not isinstance(configured_participants, list):
        configured_participants = [manager_agent, target_agent]
    return {
        "display_name": str(contract.get("display_name") or registry.get("display_name") or normalized),
        "manager_agent": manager_agent,
        "target_agent": target_agent,
        "workspace_agent": workspace_agent,
        "execution_mode": str(contract.get("execution_mode") or registry.get("execution_mode") or "delegated"),
        "default_standup_kind": str(contract.get("default_standup_kind") or registry.get("default_standup_kind") or "workspace_sync"),
        "workspace_sync_participants": list(configured_participants),
        "standup_relevance_required": bool(contract.get("standup_relevance_required")),
        "pm_review_policy": dict(contract.get("pm_review_policy") or {}),
    }


def workspace_agent_name(workspace_key: str | None) -> str:
    contract = runtime_contract_for_workspace(workspace_key)
    return str(contract.get("workspace_agent") or "Workspace Agent")


def execution_defaults_for_workspace(workspace_key: str | None) -> dict[str, object]:
    contract = runtime_contract_for_workspace(workspace_key)
    return {
        "manager_agent": contract["manager_agent"],
        "target_agent": contract["target_agent"],
        "workspace_agent": contract["workspace_agent"],
        "execution_mode": contract["execution_mode"],
    }


def pm_review_policy_for_workspace(workspace_key: str | None) -> dict[str, Any]:
    contract = runtime_contract_for_workspace(workspace_key)
    raw_policy = dict(contract.get("pm_review_policy") or {})
    execution_mode = str(contract.get("execution_mode") or "delegated")
    default_interrupt_policy = "manager_attention_only" if execution_mode == "direct" else "manual_review"
    default_policy_label = (
        "This workspace should only interrupt you for blockers or explicit owner gates."
        if default_interrupt_policy != "manual_review"
        else "This workspace still expects a human review before accepted results are closed or continued."
    )
    followup_templates = raw_policy.get("followup_templates")
    return {
        "interrupt_policy": str(raw_policy.get("interrupt_policy") or default_interrupt_policy),
        "default_resolution_mode": str(raw_policy.get("default_resolution_mode") or "close_only"),
        "auto_resolve_review_residue": bool(raw_policy.get("auto_resolve_review_residue")),
        "policy_label": str(raw_policy.get("policy_label") or default_policy_label),
        "default_next_title": _optional_text(raw_policy.get("default_next_title")),
        "default_next_reason": _optional_text(raw_policy.get("default_next_reason")),
        "followup_templates": list(followup_templates) if isinstance(followup_templates, list) else [],
    }


def default_standup_kind_for_workspace(workspace_key: str | None) -> str:
    contract = runtime_contract_for_workspace(workspace_key)
    return str(contract.get("default_standup_kind") or "workspace_sync")


def canonical_standup_kind_for_workspace(
    workspace_key: str | None,
    requested_kind: str | None,
) -> str:
    """Resolve a requested kind without transferring another lane's authority.

    Shared Ops owns the named executive cadences. Project workspaces own their
    one canonical project-sync kind. Normalizing at this boundary prevents an
    arbitrary ``executive_ops`` string from selecting Neo/Yoda for a project or
    creating a Brain agenda that the canonical project target can never read.
    """

    normalized_workspace = canonicalize_workspace_key(
        workspace_key,
        default="shared_ops",
    )
    default_kind = default_standup_kind_for_workspace(normalized_workspace)
    normalized_kind = str(requested_kind or "").strip()
    if not normalized_kind or normalized_kind == "auto":
        return default_kind
    if normalized_workspace == "shared_ops":
        return (
            normalized_kind
            if normalized_kind in EXECUTIVE_STANDUP_KINDS
            else default_kind
        )
    return default_kind


def standup_relevance_required_for(workspace_key: str | None) -> bool:
    """Return whether participant selection must come from relevance evidence.

    This is intentionally workspace-scoped rather than standup-kind-scoped so
    a caller cannot transfer executive-trio authority into FEEZIE by supplying
    an executive kind for a FEEZIE route.
    """

    contract = runtime_contract_for_workspace(workspace_key)
    return bool(contract.get("standup_relevance_required"))


def standup_participants_for(workspace_key: str | None, standup_kind: str | None) -> list[str]:
    normalized_kind = canonical_standup_kind_for_workspace(
        workspace_key,
        standup_kind,
    )
    if standup_relevance_required_for(workspace_key):
        # No role has been selected until a validated standup_relevance/v1
        # plan exists. The plan's `run` disposition adds Jean-Claude as the
        # non-transferable closer through effective_feezie_meeting_participants.
        return []
    if normalized_kind in EXECUTIVE_STANDUP_KINDS:
        return ["Jean-Claude", "Neo", "Yoda"]
    contract = runtime_contract_for_workspace(workspace_key)
    participants = contract.get("workspace_sync_participants")
    if isinstance(participants, list) and participants:
        return [str(item) for item in participants if str(item).strip()]
    return ["Jean-Claude"]


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
