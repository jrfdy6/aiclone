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
    },
    "linkedin-os": {
        "display_name": "FEEZIE OS",
        "manager_agent": "Jean-Claude",
        "target_agent": "Jean-Claude",
        "workspace_agent": None,
        "execution_mode": "direct",
        "default_standup_kind": "workspace_sync",
        "workspace_sync_participants": ["Jean-Claude", "Neo", "Yoda"],
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
