from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import PMCard
from app.services.pm_truth_service import classify_pm_card


NOW = datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)


def _card(**overrides):
    payload = overrides.pop("payload", {"workspace_key": "linkedin-os"})
    return PMCard(
        id=overrides.pop("id", "card-1"),
        title=overrides.pop("title", "Test card"),
        owner=overrides.pop("owner", "Jean-Claude"),
        status=overrides.pop("status", "todo"),
        source=overrides.pop("source", "standup_promotion"),
        link_type=None,
        link_id=None,
        due_at=overrides.pop("due_at", None),
        payload=payload,
        created_at=overrides.pop("created_at", NOW - timedelta(hours=2)),
        updated_at=overrides.pop("updated_at", NOW),
        **overrides,
    )


def test_truth_view_canonicalizes_workspace_without_rewriting_card() -> None:
    card = _card()

    truth = classify_pm_card(card, now=NOW)

    assert truth["workspace_key"] == "feezie-os"
    assert card.payload["workspace_key"] == "linkedin-os"


def test_refreshed_updated_at_does_not_hide_stale_source_evidence() -> None:
    card = _card(created_at=NOW - timedelta(days=40), updated_at=NOW)

    truth = classify_pm_card(card, now=NOW)

    assert truth["freshness"] == "stale"
    assert truth["age_hours"] == 960.0


def test_failed_execution_is_visible_even_when_pm_status_says_in_progress() -> None:
    card = _card(
        status="in_progress",
        payload={
            "workspace_key": "agc",
            "execution": {"state": "failed", "last_transition_at": (NOW - timedelta(hours=1)).isoformat()},
            "pm_review_policy": {"attention_class": "autonomous"},
        },
    )

    truth = classify_pm_card(card, now=NOW)

    assert truth["execution_class"] == "failed"
    assert truth["state_mismatch"] is True
    assert truth["needs_operator"] is False


def test_true_host_action_is_kept_out_of_system_failure_bucket() -> None:
    card = _card(
        source="pm_host_action_required",
        payload={
            "workspace_key": "feezie-os",
            "pm_review_policy": {
                "attention_class": "needs_host",
                "attention_reason": "Schedule the approved post.",
            },
        },
    )

    truth = classify_pm_card(card, now=NOW)

    assert truth["execution_class"] == "host_action"
    assert truth["needs_operator"] is True


def test_past_scheduled_host_action_and_retired_path_are_flagged() -> None:
    card = _card(
        title="Review /Users/neo/.openclaw/workspace/legacy.md",
        payload={
            "workspace_key": "fusion-os",
            "scheduled_for": (NOW - timedelta(days=20)).isoformat(),
            "pm_review_policy": {"attention_class": "needs_host"},
        },
    )

    truth = classify_pm_card(card, now=NOW)

    assert truth["freshness"] == "expired"
    assert truth["legacy_instruction"] is True
