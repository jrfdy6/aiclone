from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import StandupEntry
from app.services.standup_truth_service import classify_standup


NOW = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)


def _standup(**overrides) -> StandupEntry:
    return StandupEntry(
        id=overrides.pop("id", "standup-1"),
        owner=overrides.pop("owner", "Jean-Claude"),
        workspace_key=overrides.pop("workspace_key", "shared_ops"),
        status=overrides.pop("status", "completed"),
        blockers=overrides.pop("blockers", []),
        commitments=overrides.pop("commitments", []),
        needs=overrides.pop("needs", []),
        source=overrides.pop("source", "standup_prep"),
        conversation_path=None,
        payload=overrides.pop("payload", {"summary": "Current operating decision.", "decisions": ["Proceed."]}),
        created_at=overrides.pop("created_at", NOW - timedelta(hours=2)),
        **overrides,
    )


def test_shared_ops_standup_has_tighter_freshness_window() -> None:
    truth = classify_standup(_standup(created_at=NOW - timedelta(hours=13)), now=NOW)

    assert truth["freshness_limit_hours"] == 12
    assert truth["freshness"] == "stale"


def test_legacy_feezie_identity_uses_feezie_freshness_contract() -> None:
    truth = classify_standup(
        _standup(workspace_key="linkedin-os", created_at=NOW - timedelta(hours=30)),
        now=NOW,
    )

    assert truth["workspace_key"] == "feezie-os"
    assert truth["freshness"] == "current"


def test_commitment_heavy_standup_without_decision_is_marked_ceremonial() -> None:
    truth = classify_standup(
        _standup(
            commitments=["One", "Two", "Three", "Four", "Five"],
            payload={"summary": "Continue all current commitments."},
        ),
        now=NOW,
    )

    assert truth["quality"] == "ceremonial"
    assert truth["has_decision_output"] is False


def test_pm_handoff_makes_standup_actionable() -> None:
    truth = classify_standup(
        _standup(
            commitments=["One", "Two", "Three", "Four"],
            payload={"summary": "Route one priority.", "pm_updates": [{"title": "Ship it"}]},
        ),
        now=NOW,
    )

    assert truth["quality"] == "actionable"
    assert truth["decision_yield"] == 1
