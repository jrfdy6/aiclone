from __future__ import annotations

from typing import Any

from app.services.brain_response_privacy_service import sanitize_brain_payload
from app.services.persona_profile_coverage_service import build_persona_profile_coverage
from app.services.portfolio_workspace_snapshot_service import build_portfolio_workspace_snapshot


PRIORITY_LIMIT = 5
COUNT_KEYS = (
    "active_pm_cards",
    "attention_pm_cards",
    "needs_owner_pm_cards",
    "needs_host_pm_cards",
    "system_issue_pm_cards",
    "latest_standups",
    "standup_blockers",
)


def _safe_priority(card: Any) -> dict[str, Any] | None:
    if not isinstance(card, dict) or not str(card.get("id") or "").strip():
        return None
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "status": card.get("status"),
        "owner": card.get("owner"),
        "attention_kind": card.get("attention_kind"),
        "updated_at": card.get("updated_at"),
        "action_ref": {"kind": "pm_card", "id": card.get("id")},
    }


def _priority_score(card: dict[str, Any]) -> tuple[int, str]:
    attention = str(card.get("attention_kind") or "")
    status = str(card.get("status") or "")
    attention_rank = {
        "needs_owner": 0,
        "needs_host": 1,
        "failed": 2,
        "blocked": 3,
        "review": 4,
    }.get(attention, 5)
    status_rank = {"failed": 0, "blocked": 1, "review": 2, "running": 3}.get(status, 4)
    return attention_rank * 10 + status_rank, str(card.get("updated_at") or "")


def _latest_standup_fact(workspace: dict[str, Any]) -> dict[str, Any] | None:
    standups = workspace.get("latest_standups")
    if not isinstance(standups, list) or not standups or not isinstance(standups[0], dict):
        return None
    latest = standups[0]
    truth = latest.get("truth") if isinstance(latest.get("truth"), dict) else {}
    return {
        "id": latest.get("id"),
        "status": latest.get("status"),
        "created_at": latest.get("created_at"),
        "freshness": truth.get("freshness"),
        "quality": truth.get("quality"),
        "blocker_count": len(latest.get("blockers") or []),
    }


def _compact_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    counts = workspace.get("counts") if isinstance(workspace.get("counts"), dict) else {}
    attention = workspace.get("attention") if isinstance(workspace.get("attention"), dict) else {}
    readiness = workspace.get("readiness") if isinstance(workspace.get("readiness"), dict) else {}
    cards = [card for card in (workspace.get("active_pm_cards") or []) if isinstance(card, dict)]
    priorities = [
        item
        for item in (_safe_priority(card) for card in sorted(cards, key=_priority_score)[:PRIORITY_LIMIT])
        if item is not None
    ]
    return {
        "workspace_key": workspace.get("workspace_key"),
        "display_name": workspace.get("display_name"),
        "short_label": workspace.get("short_label"),
        "kind": workspace.get("kind"),
        "status": workspace.get("status"),
        "priority_order": workspace.get("priority_order"),
        "capability_keys": workspace.get("capability_keys") or [],
        "capabilities": workspace.get("capabilities") or [],
        "attention": {
            "status": attention.get("status"),
            "label": attention.get("label"),
            "needs_operator": bool(attention.get("needs_operator")),
            "has_system_issue": bool(attention.get("has_system_issue")),
        },
        "readiness": {
            "state": readiness.get("state"),
            "label": readiness.get("label"),
            "latest_standup_freshness": readiness.get("latest_standup_freshness"),
            "latest_standup_quality": readiness.get("latest_standup_quality"),
        },
        "counts": {key: int(counts.get(key) or 0) for key in COUNT_KEYS},
        "latest_standup": _latest_standup_fact(workspace),
        "top_priorities": priorities,
    }


def build_decision_snapshot() -> dict[str, Any]:
    """Build the content-minimized shadow snapshot used to validate a local-first cutover."""

    portfolio = build_portfolio_workspace_snapshot()
    workspaces = [
        _compact_workspace(workspace)
        for workspace in portfolio.get("workspaces") or []
        if isinstance(workspace, dict)
    ]
    capability_counts: dict[str, int] = {}
    for workspace in workspaces:
        for capability_key in workspace.get("capability_keys") or []:
            capability_counts[str(capability_key)] = capability_counts.get(str(capability_key), 0) + 1

    payload = {
        "schema_version": "decision_snapshot/v1",
        "generated_at": portfolio.get("generated_at"),
        "mode": "shadow",
        "source": "decision_snapshot_service",
        "data_policy": {
            "private_content_included": False,
            "raw_sources_included": False,
            "full_memory_included": False,
            "full_drafts_included": False,
            "includes": [
                "health",
                "counts",
                "standup_freshness",
                "top_priorities",
                "stable_action_ids",
                "persona_coverage",
            ],
        },
        "counts": {
            **(portfolio.get("counts") or {}),
            "capabilities": capability_counts,
        },
        "persona_profile": build_persona_profile_coverage(),
        "workspaces": workspaces,
    }
    return sanitize_brain_payload(payload)
