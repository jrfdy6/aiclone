from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import Future
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import (  # noqa: E402
    EmailThread,
    EmailThreadListResponse,
    ExecutiveDecision,
    ExecutiveDecisionAction,
    ExecutiveDecisionActionRequest,
    PMCard,
    PersonaDelta,
)
from app.models.automations import AutomationRun  # noqa: E402
from app.services import executive_decision_service as service  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _decision(
    source_type: str,
    source_id: str,
    *,
    workspace_key: str = "shared_ops",
    score: int = 80,
    freshness: str = "today",
    dedupe_key: str | None = None,
    action_id: str = "open_context",
) -> ExecutiveDecision:
    context_href = "/ops"
    action = ExecutiveDecisionAction(
        id=action_id,
        label=action_id.replace("_", " ").title(),
        kind="open_context" if action_id == "open_context" else "delegate",
        method="GET" if action_id == "open_context" else "POST",
        href=context_href if action_id == "open_context" else f"/api/executive/{source_id}/{action_id}",
        source_href=context_href,
        requires_confirmation=action_id != "open_context",
    )
    return ExecutiveDecision(
        id=f"{source_type}:{source_id}",
        dedupe_key=dedupe_key or f"{source_type}:{source_id}",
        source_type=source_type,
        source_id=source_id,
        workspace_key=workspace_key,
        title=f"Decision {source_id}",
        what_changed="Something changed.",
        why_it_matters="It needs a decision.",
        recommendation="Review it.",
        priority="critical" if score >= 90 else ("high" if score >= 75 else "medium"),
        priority_score=score,
        freshness=freshness,
        updated_at=NOW,
        evidence=[f"Evidence {source_id}"],
        context_href=context_href,
        actions=[action],
    )


def _patch_collectors(overrides: dict[str, object]):
    defaults = {
        "_collect_workspace_review_decisions": service._CollectionResult(),
        "_collect_pm_decisions": service._CollectionResult(),
        "_collect_persona_decisions": service._CollectionResult(),
        "_collect_brain_signal_decisions": service._CollectionResult(),
        "_collect_email_decisions": service._CollectionResult(),
        "_collect_standup_decisions": service._CollectionResult(),
        "_collect_system_exception_decisions": service._CollectionResult(),
    }
    defaults.update(overrides)
    stack = ExitStack()
    for name, value in defaults.items():
        if isinstance(value, BaseException):
            stack.enter_context(patch.object(service, name, side_effect=value))
        else:
            stack.enter_context(patch.object(service, name, return_value=value))
    return stack


def test_source_failure_preserves_other_decisions_and_never_reports_verified_clear() -> None:
    pm_decision = _decision("pm", "pm-1", score=86)
    with _patch_collectors(
        {
            "_collect_pm_decisions": service._CollectionResult(items=[pm_decision]),
            "_collect_workspace_review_decisions": RuntimeError("/Users/neo/private/control_plane.env"),
        }
    ):
        payload = service.build_executive_decision_queue(now=NOW)

    assert [item.id for item in payload.all_pending] == [pm_decision.id]
    assert payload.source_status["pm"] == "ok"
    assert payload.source_status["workspace_review"] == "error"
    assert payload.summary.verification_status == "partial"
    assert payload.summary.verified_clear is False
    assert payload.source_errors
    assert "/Users/" not in payload.source_errors[0].message
    assert "control_plane.env" not in payload.source_errors[0].message


def test_hung_source_times_out_as_degraded_without_erasing_fast_sources(capsys: pytest.CaptureFixture[str]) -> None:
    release = threading.Event()
    pm_decision = _decision("pm", "pm-fast", score=86)

    def hang_until_released(_now: datetime) -> service._CollectionResult:
        release.wait(timeout=2)
        return service._CollectionResult()

    with _patch_collectors(
        {"_collect_pm_decisions": service._CollectionResult(items=[pm_decision])}
    ), patch.object(service, "_collect_workspace_review_decisions", side_effect=hang_until_released):
        started_at = time.monotonic()
        try:
            payload = service.build_executive_decision_queue(
                now=NOW,
                source_timeout_seconds=0.05,
                overall_timeout_seconds=0.1,
            )
        finally:
            release.set()
        elapsed = time.monotonic() - started_at

    assert elapsed < 0.5
    assert [item.id for item in payload.all_pending] == [pm_decision.id]
    assert payload.source_status["pm"] == "ok"
    assert payload.source_status["workspace_review"] == "degraded"
    assert payload.summary.verification_status == "partial"
    assert payload.summary.verified_clear is False
    assert any(
        error.source_type == "workspace_review" and "deadline" in error.message
        for error in payload.source_errors
    )
    logs = capsys.readouterr().out
    assert "source `workspace_review` timed out duration_ms=" in logs
    assert "source `pm` completed status=ok items=1 duration_ms=" in logs


def test_standup_collector_propagates_authoritative_read_failure() -> None:
    with patch.object(
        service.standup_service,
        "list_standups",
        side_effect=RuntimeError("database unavailable"),
    ) as list_standups:
        with pytest.raises(RuntimeError, match="database unavailable"):
            service._collect_standup_decisions(NOW)

    list_standups.assert_called_once_with(limit=service.SOURCE_READ_LIMIT)


def test_standup_collector_uses_one_read_and_latest_actionable_item_per_workspace() -> None:
    older = SimpleNamespace(
        id="standup-old",
        workspace_key="agc",
        blockers=["Old blocker"],
        needs=[],
        payload={"summary": "Old status"},
        conversation_path="memory/old.md",
        created_at=NOW - timedelta(days=1),
    )
    latest = SimpleNamespace(
        id="standup-latest",
        workspace_key="agc",
        blockers=["Supplier approval is blocked"],
        needs=["Owner decision on contract language"],
        payload={"summary": "A supplier decision is waiting.", "source_paths": ["memory/latest.md"]},
        conversation_path="memory/conversation.md",
        created_at=NOW,
    )
    with patch.object(
        service.standup_service,
        "list_standups",
        return_value=[older, latest],
    ) as list_standups, patch.object(
        service,
        "workspace_registry_entries",
        return_value=[{"key": "agc", "display_name": "AGC"}],
    ):
        result = service._collect_standup_decisions(NOW)

    list_standups.assert_called_once_with(limit=service.SOURCE_READ_LIMIT)
    assert len(result.items) == 1
    decision = result.items[0]
    assert decision.id == "standup:standup-latest"
    assert decision.title == "AGC standup exception"
    assert decision.context_href == "/ops?focus=standups&standup_id=standup-latest"
    assert "Source: memory/conversation.md" in decision.evidence
    assert "Source: memory/latest.md" in decision.evidence


def test_today_queue_is_small_diverse_and_does_not_promote_stale_noncritical_debt() -> None:
    brain = [
        _decision("brain_signal", f"brain-{index}", score=96 - index, workspace_key="shared_ops")
        for index in range(3)
    ]
    email = _decision("email", "email-1", score=84, workspace_key="agc")
    pm = _decision("pm", "pm-1", score=88, workspace_key="shared_ops")
    stale = _decision("pm", "stale-1", score=89, freshness="stale", workspace_key="fusion-os")
    with _patch_collectors(
        {
            "_collect_brain_signal_decisions": service._CollectionResult(items=brain),
            "_collect_email_decisions": service._CollectionResult(items=[email]),
            "_collect_pm_decisions": service._CollectionResult(items=[pm, stale]),
        }
    ):
        payload = service.build_executive_decision_queue(now=NOW)

    assert len(payload.today) == 5
    assert [item.id for item in payload.today] == [
        "brain_signal:brain-0",
        "brain_signal:brain-1",
        "brain_signal:brain-2",
        "pm:pm-1",
        "email:email-1",
    ]
    assert [item.priority_score for item in payload.today] == sorted(
        (item.priority_score for item in payload.today), reverse=True
    )
    assert stale.id not in {item.id for item in payload.today}
    assert payload.all_pending[0].id == "brain_signal:brain-0"
    assert payload.summary.today_candidate_count == 5


def test_today_caps_a_single_noisy_source_instead_of_backfilling_to_five() -> None:
    noisy_source = [
        _decision("system_exception", f"exception-{index}", score=96 - index)
        for index in range(8)
    ]
    with _patch_collectors(
        {"_collect_system_exception_decisions": service._CollectionResult(items=noisy_source)}
    ):
        payload = service.build_executive_decision_queue(now=NOW)

    assert payload.summary.today_candidate_count == 8
    assert len(payload.today) == 3
    assert {item.source_type for item in payload.today} == {"system_exception"}


def test_owner_review_pm_mirror_collapses_with_workspace_identity() -> None:
    card = PMCard(
        id="pm-owner-review",
        title="Owner review - Draft",
        owner="Neo",
        status="review",
        source="codex_native:workspace-owner-review",
        link_type="owner_review",
        payload={
            "workspace_key": "feezie-os",
            "owner_review": {
                "queue_id": "FEEZIE-101",
                "identity_key": "drafts/example.md",
                "sync_state": "pending_owner_review",
                "title": "Draft from PM",
            },
        },
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(hours=2),
    )
    workspace_item = {
        "queue_id": "FEEZIE-101",
        "identity_key": "drafts/example.md",
        "title": "Canonical workspace draft",
        "created_at": (NOW - timedelta(days=4)).isoformat(),
        "core_angle": "A concrete source-grounded argument.",
        "why_now": "It is ready for this week's owner review.",
        "draft_path": "drafts/example.md",
        "proof_anchors": ["proof.md"],
        "system_assessment": {"suggested_decision": "park", "confidence": "low", "summary": "Ready."},
        "decision_scaffold": {"neo_answer_contract": "Approve on one clean read."},
    }
    with patch.object(service.pm_card_service, "list_cards", return_value=[card]), patch.object(
        service.pm_card_service, "decorate_cards_for_client", return_value=[card]
    ), patch.object(service, "list_owner_review_items", return_value={"items": [workspace_item]}):
        pm_items = service._collect_pm_decisions(NOW).items
        workspace_items = service._collect_workspace_review_decisions(NOW).items

    assert pm_items[0].dedupe_key == workspace_items[0].dedupe_key
    deduped = service._dedupe_decisions([*pm_items, *workspace_items])
    assert len(deduped) == 1
    assert deduped[0].title == "Canonical workspace draft"
    assert deduped[0].priority_score == pm_items[0].priority_score
    assert any(item.startswith("PM card:") for item in deduped[0].evidence)


def test_email_pm_mirror_collapses_through_local_id_to_provider_thread_alias() -> None:
    pm_mirror = _decision(
        "pm",
        "pm-email-1",
        score=99,
        dedupe_key="email:local-thread-1",
    )
    inbox_thread = _decision(
        "email",
        "local-thread-1",
        score=58,
        dedupe_key="email:gmail-thread-1",
    )

    deduped = service._dedupe_decisions([pm_mirror, inbox_thread])

    assert [item.id for item in deduped] == [inbox_thread.id]
    assert deduped[0].dedupe_key == "email:gmail-thread-1"
    assert deduped[0].priority_score == 99
    assert deduped[0].priority == "critical"
    assert {"Evidence pm-email-1", "Evidence local-thread-1"}.issubset(set(deduped[0].evidence))
    assert [action.id for action in deduped[0].actions] == ["open_context"]


def test_email_collector_includes_risk_exception_without_needs_human_and_is_open_only() -> None:
    thread = EmailThread(
        id="thread-1",
        provider="gmail",
        provider_thread_id="gmail-thread-1",
        workspace_key="agc",
        lane="supplier_partner",
        status="routed",
        subject="Urgent contract question",
        from_address="partner@example.com",
        needs_human=False,
        high_value=False,
        high_risk=True,
        sla_at_risk=False,
        summary="A contract exception needs review.",
        last_message_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    response = EmailThreadListResponse(items=[thread], total=1, data_mode="provider_sync")
    with patch.object(
        service.email_ops_service,
        "list_persisted_threads",
        return_value=response,
    ) as list_persisted_threads, patch.object(
        service.email_ops_service,
        "list_threads",
        side_effect=AssertionError("executive reads must not trigger provider sync or seed paths"),
    ):
        result = service._collect_email_decisions(NOW)

    list_persisted_threads.assert_called_once_with(limit=250)
    assert len(result.items) == 1
    assert result.items[0].dedupe_key == "email:gmail-thread-1"
    assert [action.kind for action in result.items[0].actions] == ["open_context"]
    assert result.items[0].context_href == "/inbox/thread-1"


def test_persona_and_brain_items_are_inspect_first_only() -> None:
    persona = PersonaDelta(
        id="persona-1",
        persona_target="feeze.core",
        trait="A selected belief",
        status="approved",
        metadata={
            "queue_stage": "pending_promotion",
            "queue_muted": False,
            "queue_priority_score": 30,
            "queue_target_file": "identity/claims.md",
            "review_key": "voice-review-1",
        },
        created_at=NOW,
    )
    brain = SimpleNamespace(
        id="brain-1",
        source_kind="automation_output",
        source_ref="report-1",
        source_workspace_key="shared_ops",
        raw_summary="An automation exception needs interpretation.",
        digest="Automation exception",
        signal_types=["automation"],
        actionability="high",
        confidence="high",
        identity_relevance="operational",
        executive_interpretation={},
        review_status="new",
        updated_at=NOW,
    )
    with patch.object(service.persona_delta_service, "list_deltas", return_value=[persona]), patch.object(
        service, "prepare_for_brain_queue", return_value=[persona]
    ), patch.object(service, "list_signals", return_value=[brain]):
        persona_items = service._collect_persona_decisions(NOW).items
        brain_items = service._collect_brain_signal_decisions(NOW).items

    assert [action.kind for action in persona_items[0].actions] == ["open_context"]
    assert [action.kind for action in brain_items[0].actions] == ["open_context"]
    assert persona_items[0].dedupe_key == "persona:voice-review-1"
    assert persona_items[0].context_href.endswith("#brain-section-persona")
    assert brain_items[0].dedupe_key == "brain_signal:automation_output:report-1"
    assert brain_items[0].context_href.endswith("#brain-section-dashboard")


def test_actions_disclose_when_a_note_is_required() -> None:
    owner_actions = service._owner_review_actions("workspace_review:FEEZIE-1", "FEEZIE-1", "/ops")
    assert {action.id: action.requires_note for action in owner_actions} == {
        "approve": False,
        "revise": True,
        "park": False,
        "open_context": False,
    }

    card = PMCard(
        id="pm-needs-owner",
        title="Choose the next state",
        owner="Neo",
        status="review",
        payload={"pm_review_policy": {"attention_class": "needs_owner"}},
        created_at=NOW,
        updated_at=NOW,
    )
    with patch.object(service.pm_card_service, "list_cards", return_value=[card]), patch.object(
        service.pm_card_service, "decorate_cards_for_client", return_value=[card]
    ):
        decision = service._collect_pm_decisions(NOW).items[0]

    assert {action.id: action.requires_note for action in decision.actions} == {
        "approve": False,
        "return": True,
        "blocked": True,
        "open_context": False,
    }


def test_bulk_source_intelligence_never_enters_executive_queue_or_today() -> None:
    ingestion = [
        SimpleNamespace(
            id=f"source-{index}",
            source_kind="source_intelligence",
            source_ref=f"video-{index}",
            source_workspace_key="feezie-os",
            raw_summary="A newly ingested source.",
            digest=f"Source {index}",
            signal_types=["framework"],
            actionability="high",
            confidence="high",
            identity_relevance="high",
            executive_interpretation={},
            review_status="new",
            updated_at=NOW,
        )
        for index in range(service.SOURCE_READ_LIMIT)
    ]
    exception = SimpleNamespace(
        id="automation-exception",
        source_kind="automation_output",
        source_ref="run-123",
        source_workspace_key="shared_ops",
        raw_summary="A real automation exception.",
        digest="Automation exception",
        signal_types=["automation"],
        actionability="high",
        confidence="high",
        identity_relevance="operational",
        executive_interpretation={},
        review_status="new",
        updated_at=NOW,
    )
    with patch.object(service, "list_signals", return_value=[*ingestion, exception]):
        brain_result = service._collect_brain_signal_decisions(NOW)
    with _patch_collectors({"_collect_brain_signal_decisions": brain_result}):
        payload = service.build_executive_decision_queue(now=NOW)

    assert [item.id for item in payload.all_pending] == ["brain_signal:automation-exception"]
    assert [item.id for item in payload.today] == ["brain_signal:automation-exception"]
    assert brain_result.status == "degraded"
    assert brain_result.errors
    assert payload.source_status["brain_signal"] == "degraded"
    assert payload.summary.verification_status == "partial"


def test_system_action_required_uses_only_latest_run_per_automation() -> None:
    old = AutomationRun(
        id="run-old",
        automation_id="memory-sync",
        automation_name="Memory Sync",
        status="error",
        action_required=True,
        run_at=NOW - timedelta(hours=2),
    )
    latest = AutomationRun(
        id="run-new",
        automation_id="memory-sync",
        automation_name="Memory Sync",
        status="ok",
        action_required=False,
        run_at=NOW - timedelta(hours=1),
    )
    with patch.object(service.automation_run_service, "list_runs", return_value=[old, latest]), patch.object(
        service, "list_automations", return_value=[]
    ), patch.object(
        service.automation_mismatch_service,
        "build_mismatch_report",
        return_value=SimpleNamespace(mismatches=[]),
    ):
        result = service._collect_system_exception_decisions(NOW)

    assert result.items == []


def test_pm_action_delegates_close_only_and_requires_context_for_negative_actions() -> None:
    decision = _decision("pm", "pm-1", action_id="approve")
    with patch.object(service, "_find_decision_and_action", return_value=(decision, decision.actions[0])), patch.object(
        service.pm_card_service, "act_on_card", return_value={"card_id": "pm-1", "status": "done"}
    ) as act:
        result = service.execute_executive_decision_action(
            decision.id,
            "approve",
            ExecutiveDecisionActionRequest(confirmed=True),
        )

    assert result.status == "completed"
    request = act.call_args.args[1]
    assert request.action == "approve"
    assert request.resolution_mode == "close_only"

    return_decision = _decision("pm", "pm-2", action_id="return")
    with patch.object(
        service,
        "_find_decision_and_action",
        return_value=(return_decision, return_decision.actions[0]),
    ):
        with pytest.raises(service.ExecutiveDecisionActionError, match="reason is required"):
            service.execute_executive_decision_action(
                return_decision.id,
                "return",
                ExecutiveDecisionActionRequest(confirmed=True),
            )


def test_owner_revision_requires_notes_and_delegates_to_existing_contract() -> None:
    decision = _decision("workspace_review", "FEEZIE-101", action_id="revise")
    with patch.object(service, "_find_decision_and_action", return_value=(decision, decision.actions[0])):
        with pytest.raises(service.ExecutiveDecisionActionError, match="Revision notes"):
            service.execute_executive_decision_action(
                decision.id,
                "revise",
                ExecutiveDecisionActionRequest(confirmed=True),
            )

    with patch.object(service, "_find_decision_and_action", return_value=(decision, decision.actions[0])), patch.object(
        service, "record_owner_decision", return_value={"status": "queued"}
    ) as record:
        result = service.execute_executive_decision_action(
            decision.id,
            "revise",
            ExecutiveDecisionActionRequest(confirmed=True, notes="Add one concrete proof line."),
        )

    record.assert_called_once_with("FEEZIE-101", "revise", "Add one concrete proof line.")
    assert result.status == "completed"


def test_action_fails_closed_when_decision_is_no_longer_pending() -> None:
    with patch.object(service, "_collect_pm_decisions", return_value=service._CollectionResult()):
        with pytest.raises(service.ExecutiveDecisionNotFoundError):
            service.execute_executive_decision_action(
                "pm:gone",
                "approve",
                ExecutiveDecisionActionRequest(confirmed=True),
            )


def test_rapid_duplicate_action_revalidates_exact_source_and_ignores_stale_get_future() -> None:
    decision = _decision("pm", "pm-rapid", action_id="approve")
    stale_future: Future[service._CollectionResult] = Future()
    stale_future.set_result(service._CollectionResult(items=[decision]))
    stale_entry = service._InFlightCollection(future=stale_future, started_at=time.monotonic())
    with service._SOURCE_INFLIGHT_LOCK:
        service._SOURCE_INFLIGHT["pm"] = stale_entry

    try:
        with patch.object(
            service,
            "_collect_pm_decisions",
            side_effect=[service._CollectionResult(items=[decision]), service._CollectionResult()],
        ) as collect_pm, patch.object(
            service,
            "build_executive_decision_queue",
            side_effect=AssertionError("action validation must not rebuild the shared queue"),
        ), patch.object(
            service,
            "_collect_workspace_review_decisions",
            side_effect=AssertionError("unrelated source collector must not run"),
        ) as unrelated_collector, patch.object(
            service,
            "_collect_email_decisions",
            side_effect=AssertionError("unrelated source collector must not run"),
        ) as unrelated_email, patch.object(
            service.pm_card_service,
            "act_on_card",
            return_value={"card_id": "pm-rapid", "status": "done"},
        ) as act:
            first = service.execute_executive_decision_action(
                decision.id,
                "approve",
                ExecutiveDecisionActionRequest(confirmed=True),
            )
            with pytest.raises(service.ExecutiveDecisionNotFoundError):
                service.execute_executive_decision_action(
                    decision.id,
                    "approve",
                    ExecutiveDecisionActionRequest(confirmed=True),
                )
    finally:
        with service._SOURCE_INFLIGHT_LOCK:
            if service._SOURCE_INFLIGHT.get("pm") is stale_entry:
                service._SOURCE_INFLIGHT.pop("pm", None)

    assert first.status == "completed"
    assert collect_pm.call_count == 2
    act.assert_called_once()
    unrelated_collector.assert_not_called()
    unrelated_email.assert_not_called()


def test_action_request_requires_explicit_confirmation_and_rejects_caller_actor() -> None:
    with pytest.raises(ValidationError):
        ExecutiveDecisionActionRequest()  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        ExecutiveDecisionActionRequest(confirmed=True, requested_by="Someone else")  # type: ignore[call-arg]
