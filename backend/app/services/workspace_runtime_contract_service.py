from __future__ import annotations

from typing import Any

EXECUTIVE_STANDUP_KINDS = frozenset({"executive_ops", "operations", "weekly_review", "saturday_vision"})

WORKSPACE_RUNTIME_CONTRACTS: dict[str, dict[str, Any]] = {
    "shared_ops": {
        "display_name": "Executive",
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
    "linkedin-os": {
        "display_name": "FEEZIE OS",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "workspace_agent": None,
        "execution_mode": "direct",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Neo", "Yoda"],
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
    },
    "fusion-os": {
        "display_name": "Fusion OS",
        "manager_agent": "Jean-Claude",
        "target_agent": "Fusion Systems Operator",
        "workspace_agent": "Fusion Systems Operator",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Fusion Systems Operator"],
    },
    "easyoutfitapp": {
        "display_name": "EasyOutfitApp",
        "manager_agent": "Jean-Claude",
        "target_agent": "Easy Outfit Product Agent",
        "workspace_agent": "Easy Outfit Product Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Easy Outfit Product Agent"],
    },
    "ai-swag-store": {
        "display_name": "AI Swag Store",
        "manager_agent": "Jean-Claude",
        "target_agent": "Commerce Growth Agent",
        "workspace_agent": "Commerce Growth Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Commerce Growth Agent"],
    },
    "agc": {
        "display_name": "AGC",
        "manager_agent": "Jean-Claude",
        "target_agent": "AGC Strategy Agent",
        "workspace_agent": "AGC Strategy Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "AGC Strategy Agent"],
    },
}


def runtime_contract_for_workspace(workspace_key: str | None) -> dict[str, Any]:
    normalized = str(workspace_key or "").strip() or "shared_ops"
    contract = WORKSPACE_RUNTIME_CONTRACTS.get(normalized)
    if contract is not None:
        return dict(contract)
    return {
        "display_name": normalized,
        "manager_agent": "Jean-Claude",
        "target_agent": "Workspace Agent",
        "workspace_agent": "Workspace Agent",
        "execution_mode": "delegated",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Workspace Agent"],
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


def standup_participants_for(workspace_key: str | None, standup_kind: str | None) -> list[str]:
    normalized_kind = str(standup_kind or "").strip()
    if not normalized_kind or normalized_kind == "auto":
        normalized_kind = default_standup_kind_for_workspace(workspace_key)
    if normalized_kind in EXECUTIVE_STANDUP_KINDS:
        return ["Jean-Claude", "Neo", "Yoda"]
    contract = runtime_contract_for_workspace(workspace_key)
    participants = contract.get("workspace_sync_participants")
    if isinstance(participants, list) and participants:
        return [str(item) for item in participants if str(item).strip()]
    return ["Jean-Claude"]


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
