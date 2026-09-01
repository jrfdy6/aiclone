from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Mapping

from app.services.portfolio_cycle_service import (
    WORKSPACE_GOAL_AUTHORITY_FUTURE_TRIGGER,
    PortfolioCycleService,
    workspace_goal_contract_validation_error,
)
from app.services.standup_relevance_service import (
    effective_feezie_meeting_participants,
    validate_standup_relevance_plan,
)
from app.services.standup_truth_service import is_verified_meeting_record
from app.services.workspace_registry_service import workspace_registry_entry
from app.services.workspace_runtime_contract_service import standup_participants_for
from app.utils.ai_clone_clock import (
    resolve_payload_observation,
    same_utc_observation_second,
)


_FEEZIE_WORKSPACE_KEY = "feezie-os"
_WORKSPACE_CYCLE_PLAN_RECORD_KIND = "workspace_cycle_plan"
_WORKSPACE_CYCLE_EVALUATION_SCHEMA_VERSION = "workspace_cycle_evaluation/v1"
_ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION = "standup_async_role_evidence/v1"
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_TERMINAL_RECOMMENDATION_STATES = frozenset(
    {
        "executed_automatically",
        "placed_in_execution_queue",
        "bounded_owner_decision",
        "blocked",
        "rejected_by_policy",
        "intentionally_retained",
    }
)
_SYNTHETIC_ROLE_PROVENANCE = frozenset(
    {"deterministic_policy", "synthesized_lens", "synthesized_role_lens"}
)


def _parse_explicit_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _ai_clone_utc_observation(value: datetime) -> datetime:
    """Require an explicit timezone before normalizing onto ai_clone_utc."""

    if not isinstance(value, datetime):
        raise TypeError("observed_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "observed_at must include a timezone offset for ai_clone_utc"
        )
    return value.astimezone(timezone.utc)


def _canonical_workspace_goal(workspace_key: str) -> dict[str, Any] | None:
    entry = workspace_registry_entry(workspace_key)
    goal = entry.get("goal_contract") if isinstance(entry.get("goal_contract"), Mapping) else {}
    normalized = dict(goal)
    if workspace_goal_contract_validation_error(workspace_key, normalized):
        return None
    return normalized


def _non_meeting_conclusion_fields() -> dict[str, list[Any]]:
    return {
        "changes_since_prior": [],
        "system_decisions": [],
        "actions_taken": [],
        "work_underway": [],
        "completed_work": [],
        "failed_work": [],
        "carried_forward": [],
        "blockers": [],
        "urgent_escalations": [],
        "decisions": [],
        "owner_decisions": [],
        "recommendation_resolutions": [],
        "recommended_next_actions": [],
        "reference_only": [],
    }


def _recursion_items(recursion: Mapping[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = recursion.get(key)
        if isinstance(value, list):
            return value
    return []


def _recursion_no_action(
    recursion: Mapping[str, Any],
    *,
    canonical_goal: Mapping[str, Any],
) -> list[dict[str, Any]]:
    canonical_trigger = " ".join(
        str(canonical_goal.get("no_action_trigger") or "").split()
    )
    value = recursion.get("no_action")
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for raw in value:
            if not isinstance(raw, Mapping) or raw.get("selected") is not True:
                continue
            summary = " ".join(str(raw.get("reason") or raw.get("summary") or "").split())
            if summary and canonical_trigger:
                projected = {
                    key: cell
                    for key, cell in dict(raw).items()
                    if key not in {"future_trigger", "trigger"}
                }
                items.append(
                    {
                        **projected,
                        "summary": summary,
                        "trigger": canonical_trigger,
                        "selected": True,
                    }
                )
        return items
    if not isinstance(value, Mapping) or value.get("selected") is not True:
        return []
    summary = " ".join(str(value.get("reason") or "").split())
    if not summary or not canonical_trigger:
        return []
    return [
        {
            "summary": summary,
            "trigger": canonical_trigger,
            "selected": True,
        }
    ]


def _recursion_work_underway(recursion: Mapping[str, Any]) -> list[Any]:
    explicit = _recursion_items(recursion, "work_underway")
    if explicit:
        return explicit
    underway: list[Any] = []
    for raw in _recursion_items(recursion, "carried_forward", "carried"):
        if not isinstance(raw, Mapping):
            continue
        truth = raw.get("effective_pm_truth") if isinstance(raw.get("effective_pm_truth"), Mapping) else {}
        state = str(raw.get("effective_state") or truth.get("effective_state") or "").strip().lower()
        if state in {"queued", "in_progress"}:
            underway.append(raw)
    return underway


def _recommendation_authority_explanation(
    payload: Mapping[str, Any],
    recursion: Mapping[str, Any],
) -> tuple[bool, str, str, str]:
    """Read terminal recommendation authority only from the server-owned top level.

    Nested meeting-attempt data remains useful failure evidence, but it cannot
    authorize a proposal after the canonical closer or backend has withheld it.
    """

    authorized = payload.get("recommendations_authorized") is True
    state = " ".join(
        str(payload.get("recommendation_authority_state") or "").split()
    ) or "recommendation_authority_unverified"
    ratification = (
        payload.get("meeting_ratification")
        if isinstance(payload.get("meeting_ratification"), Mapping)
        else {}
    )
    attempt = (
        recursion.get("meeting_attempt")
        if isinstance(recursion.get("meeting_attempt"), Mapping)
        else {}
    )
    reason = " ".join(
        str(
            ratification.get("ratification_reason")
            or attempt.get("reason")
            or payload.get("meeting_evidence_reason")
            or "The terminal canonical authority did not authorize this cycle's recommendations."
        ).split()
    )
    trigger = " ".join(
        str(
            ratification.get("next_step_or_trigger")
            or attempt.get("future_trigger")
            or "A terminal canonical authority record authorizes a bounded recommendation."
        ).split()
    )
    return authorized, state, reason, trigger


def _standup_source_observed_at(payload: Mapping[str, Any]) -> datetime | None:
    """Return the standup's semantic observation, never its database write time."""

    observed_at, source = resolve_payload_observation(
        payload,
        created_at=None,
    )
    if source not in {"semantic_observed_at", "semantic_cycle_observation"}:
        return None
    return observed_at


def _discussion_rounds(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = payload.get("discussion")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _is_synthetic_planning_record(
    raw: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> bool:
    """Keep planning-shaped role lenses out of the real-standup adapter.

    New records carry an explicit kind. Historical prep rows predate that field,
    so source/provenance remain a fail-closed compatibility check. An explicitly
    classified standup is left to the existing meeting-evidence writer.
    """

    record_kind = str(payload.get("record_kind") or "").strip()
    if record_kind == _WORKSPACE_CYCLE_PLAN_RECORD_KIND:
        return True
    rounds = _discussion_rounds(payload)
    all_rounds_synthetic = bool(rounds) and all(
        str(item.get("provenance") or "").strip().lower()
        in _SYNTHETIC_ROLE_PROVENANCE
        for item in rounds
    )
    if all_rounds_synthetic:
        return True
    if record_kind == "standup":
        return False
    return bool(
        str(raw.get("source") or "").strip().lower() == "standup_prep"
        or payload.get("prep_id")
    )


def _adapt_workspace_coordination_record(
    raw: Mapping[str, Any],
    *,
    workspace: str,
    cycle_id: str,
    source_observed_at: datetime,
    evidence_ref_prefix: str,
    summary_prefix: str = "",
) -> dict[str, Any]:
    payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else {}
    sections = payload.get("standup_sections") if isinstance(payload.get("standup_sections"), Mapping) else {}
    recursion = payload.get("recursion") if isinstance(payload.get("recursion"), Mapping) else {}
    continuity = payload.get("continuity") if isinstance(payload.get("continuity"), Mapping) else {}
    (
        recommendations_authorized,
        recommendation_authority_state,
        recommendation_authority_reason,
        recommendation_authority_trigger,
    ) = _recommendation_authority_explanation(payload, recursion)
    goal = _canonical_workspace_goal(workspace) or {}
    goal_error = workspace_goal_contract_validation_error(workspace, goal)
    summary = " ".join(
        str(payload.get("summary") or raw.get("summary") or "Completed workspace evaluation.").split()
    )
    if summary_prefix:
        summary = f"{summary_prefix}{summary}"
    changes_since_prior = _recursion_items(recursion, "changes_since_prior") or continuity.get("changes") or []
    proposed_system_decisions = _recursion_items(recursion, "system_decisions")
    proposed_owner_decisions = _recursion_items(
        recursion,
        "owner_decisions",
        "owner_required",
    )
    payload_recommendation_resolutions = payload.get(
        "recommendation_resolutions"
    )
    recursion_recommendation_resolutions = _recursion_items(
        recursion,
        "recommendation_resolutions",
    )
    if (
        isinstance(payload_recommendation_resolutions, list)
        and payload_recommendation_resolutions
    ):
        proposed_recommendation_resolutions = payload_recommendation_resolutions
    elif recursion_recommendation_resolutions:
        proposed_recommendation_resolutions = recursion_recommendation_resolutions
    elif isinstance(payload_recommendation_resolutions, list):
        proposed_recommendation_resolutions = payload_recommendation_resolutions
    else:
        proposed_recommendation_resolutions = []
    system_decisions = (
        proposed_system_decisions if recommendations_authorized else []
    )
    recommendation_authority_explicit = bool(
        "recommendations_authorized" in payload
        or str(payload.get("recommendation_authority_state") or "").strip()
    )
    pending_recommendation_projection = bool(
        proposed_system_decisions
        or _recursion_items(recursion, "recommendations")
        or sections.get("recommended_next_actions")
        or sections.get("next_focus")
        or _recursion_items(recursion, "decisions")
        or proposed_owner_decisions
        or proposed_recommendation_resolutions
    )
    recommendation_authority_withheld = bool(
        not recommendations_authorized
        and (recommendation_authority_explicit or pending_recommendation_projection)
    )
    actions_taken = _recursion_items(recursion, "actions_taken", "actions_since_prior")
    completed_work = _recursion_items(
        recursion,
        "completed_work",
        "current_cycle_completed_work",
    )
    failed_work = _recursion_items(recursion, "failed_work", "failed") or continuity.get("failed") or []
    carried_forward = _recursion_items(recursion, "carried_forward", "carried") or continuity.get("carried") or []
    # A recursion body is a producer claim, not independent proof of a
    # canonical owner decision or PM disposition. When Jean-Claude's terminal
    # recommendation authority is withheld, this adapter has no signed
    # decision/PM receipt authority with which to re-admit either lane. Fail
    # closed here; verified prior decisions remain available through their
    # canonical decision and PM continuity sources instead of being promoted
    # from the unratified current-cycle proposal.
    owner_decisions = (
        proposed_owner_decisions if recommendations_authorized else []
    )
    recommendation_resolutions = (
        proposed_recommendation_resolutions
        if recommendations_authorized
        else []
    )
    current_recommendations = (
        _recursion_items(recursion, "recommendations")
        or sections.get("recommended_next_actions")
        or sections.get("next_focus")
        or []
    )
    if not isinstance(current_recommendations, list):
        current_recommendations = []
    reference_only = (
        _recursion_items(recursion, "reference_only")
        or sections.get("reference_only")
        or []
    )
    if not isinstance(reference_only, list):
        reference_only = []
    no_action = _recursion_no_action(recursion, canonical_goal=goal)
    blockers = recursion.get("blocked") or sections.get("blockers") or []
    if not isinstance(blockers, list):
        blockers = [blockers]
    if goal_error and not any(
        isinstance(item, Mapping)
        and item.get("reason_code") == "workspace_goal_authority_blocked"
        for item in blockers
    ):
        blockers = [
            *blockers,
            {
                "kind": "workspace_goal_authority_blocked",
                "reason_code": "workspace_goal_authority_blocked",
                "summary": "Goal-directed workspace evaluation is blocked by unavailable or invalid canonical goal authority.",
                "reason": goal_error,
                "future_trigger": WORKSPACE_GOAL_AUTHORITY_FUTURE_TRIGGER,
            },
        ]
    if recommendation_authority_withheld and not any(
        isinstance(item, Mapping)
        and item.get("kind") == "recommendation_authority_withheld"
        for item in blockers
    ):
        blockers = [
            *blockers,
            {
                "kind": "recommendation_authority_withheld",
                "reason_code": recommendation_authority_state,
                "summary": recommendation_authority_reason,
                "future_trigger": recommendation_authority_trigger,
            },
        ]
    evidence_links = []
    record_id = str(raw.get("id") or "").strip()
    if record_id:
        evidence_links.append(
            {
                "ref": f"{evidence_ref_prefix}:{record_id}",
                "source_observed_at": source_observed_at.isoformat(),
            }
        )
    async_contribution = (
        recursion.get("async_role_contribution")
        if isinstance(recursion.get("async_role_contribution"), Mapping)
        else {}
    )
    async_run_id = str(
        async_contribution.get("participant_report_run_id") or ""
    ).strip()
    if async_run_id:
        evidence_links.append(
            {
                "ref": f"automation-run:{async_run_id}",
                "source_observed_at": source_observed_at.isoformat(),
            }
        )
    if recommendations_authorized:
        next_cycle_inputs = [
            {
                **{
                    key: cell
                    for key, cell in dict(item).items()
                    if key not in {"future_trigger", "trigger"}
                },
                **(
                    {"trigger": str(goal.get("no_action_trigger") or "")}
                    if no_action and str(goal.get("no_action_trigger") or "")
                    else {}
                ),
            }
            for item in (recursion.get("next_cycle_inputs") or [])
            if isinstance(item, Mapping)
        ]
    elif recommendation_authority_withheld:
        next_cycle_inputs = [
            {
                "summary": recommendation_authority_reason,
                "trigger": recommendation_authority_trigger,
                "reason_code": recommendation_authority_state,
            }
        ]
    else:
        next_cycle_inputs = [
            dict(item)
            for item in (recursion.get("next_cycle_inputs") or [])
            if isinstance(item, Mapping)
        ]
    return {
        "summary": summary,
        "cycle_id": cycle_id,
        "observed_at": source_observed_at.isoformat(),
        "goal": goal,
        "recommendations_authorized": recommendations_authorized,
        "recommendation_authority_state": recommendation_authority_state,
        "changes_since_prior": changes_since_prior,
        "system_decisions": system_decisions,
        "actions_taken": actions_taken,
        "work_underway": _recursion_work_underway(recursion),
        "completed_work": completed_work,
        "failed_work": failed_work,
        "carried_forward": carried_forward,
        "blockers": blockers,
        "urgent_escalations": sections.get("urgent_escalations") or [],
        "decisions": (
            _recursion_items(recursion, "decisions")
            or system_decisions
            or sections.get("decisions")
            or []
        ) if recommendations_authorized else [],
        "owner_decisions": owner_decisions,
        "no_action": no_action,
        "recommendation_resolutions": recommendation_resolutions,
        "next_cycle_inputs": next_cycle_inputs,
        "evidence_links": evidence_links,
        "recommended_next_actions": (
            current_recommendations
        ) if recommendations_authorized else [],
        # This lane is explicit by design. Prior/static evidence must never be
        # inferred from an absence of action or presented as work performed.
        "reference_only": reference_only,
        "_conclusion_kind": (
            "healthy_no_change"
            if (
                recursion.get("evaluated") is True
                and recommendations_authorized
                and not goal_error
                and no_action
            )
            else "conclusion"
        ),
    }


def adapt_daily_workspace_standups(
    rows: list[Mapping[str, Any]],
    *,
    cycle_id: str,
    cycle_date: date,
    observed_at: datetime,
    expected_workspaces: list[str],
) -> dict[str, dict[str, Any]]:
    """Adapt only standups produced for this exact cycle observation.

    PostgreSQL ``created_at`` is a persistence timestamp, not evidence freshness.
    Exact cycle identity plus the standup's own semantic observation prevents a
    later same-day cycle from inheriting an earlier row and prevents future
    observations from leaking into an earlier coordinator run.
    """

    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    expected = set(expected_workspaces)
    freshness_reference = _ai_clone_utc_observation(observed_at)
    for raw in rows:
        workspace = str(raw.get("workspace_key") or "").strip()
        if workspace not in expected or str(raw.get("status") or "").strip().lower() != "completed":
            continue
        payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else {}
        if str(payload.get("cycle_id") or "").strip() != cycle_id:
            continue
        if (
            payload.get("evaluation_only") is True
            or payload.get("meeting_held") is False
            or _is_synthetic_planning_record(raw, payload)
        ):
            continue
        standup_kind = str(payload.get("standup_kind") or "").strip()
        expected_participants: list[str]
        if workspace == _FEEZIE_WORKSPACE_KEY:
            relevance = payload.get("standup_relevance")
            if not isinstance(relevance, Mapping):
                continue
            try:
                canonical_relevance = validate_standup_relevance_plan(relevance)
            except ValueError:
                continue
            if str(canonical_relevance.get("disposition") or "") != "run":
                continue
            # Relevance selects independent lenses. It cannot transfer or
            # remove Jean-Claude's non-transferable terminal closure role.
            expected_participants = effective_feezie_meeting_participants(
                canonical_relevance
            )
        else:
            expected_participants = standup_participants_for(workspace, standup_kind)
        if not expected_participants or not is_verified_meeting_record(
            payload,
            source=str(raw.get("source") or "") or None,
            expected_participants=expected_participants,
            workspace_key=workspace,
            verify_current_identity_pack=True,
        ):
            continue
        source_observed_at = _standup_source_observed_at(payload)
        if (
            source_observed_at is None
            or not same_utc_observation_second(
                source_observed_at, freshness_reference
            )
            or source_observed_at.date() != cycle_date
        ):
            continue
        adapted = _adapt_workspace_coordination_record(
            raw,
            workspace=workspace,
            cycle_id=cycle_id,
            source_observed_at=source_observed_at,
            evidence_ref_prefix="standup",
        )
        if workspace not in latest or source_observed_at > latest[workspace][0]:
            latest[workspace] = (source_observed_at, adapted)
    return {workspace: payload for workspace, (_observed, payload) in latest.items()}


def _workspace_cycle_plan_resolutions_are_complete(payload: Mapping[str, Any]) -> bool:
    expected_count = payload.get("pm_recommendation_count")
    requests = payload.get("recommendation_requests")
    resolutions = payload.get("recommendation_resolutions")
    if type(expected_count) is not int or expected_count < 0:
        return False
    if not isinstance(requests, list) or len(requests) != expected_count:
        return False
    if not isinstance(resolutions, list) or len(resolutions) != expected_count:
        return False
    return all(
        isinstance(item, Mapping)
        and bool(str(item.get("request_sha256") or "").strip())
        and bool(str(item.get("card_id") or "").strip())
        and bool(str(item.get("state") or "").strip())
        for item in resolutions
    )


def adapt_daily_workspace_cycle_plans(
    rows: list[Mapping[str, Any]],
    *,
    cycle_id: str,
    cycle_date: date,
    observed_at: datetime,
    expected_workspaces: list[str],
    excluded_workspaces: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Adapt completed non-meeting cycle plans into workspace conclusions.

    The plan remains a deterministic workspace evaluation and PM handoff. It is
    never admitted as attendance, a transcript, or prior real-standup evidence.
    """

    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    expected = set(expected_workspaces) - set(excluded_workspaces or set())
    freshness_reference = _ai_clone_utc_observation(observed_at)
    for raw in rows:
        workspace = str(raw.get("workspace_key") or "").strip()
        if (
            workspace not in expected
            or str(raw.get("status") or "").strip().lower() != "completed"
            or str(raw.get("source") or "").strip().lower() != "standup_prep"
        ):
            continue
        payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else {}
        discussion = _discussion_rounds(payload)
        recursion = payload.get("recursion") if isinstance(payload.get("recursion"), Mapping) else {}
        async_contribution = (
            recursion.get("async_role_contribution")
            if isinstance(recursion.get("async_role_contribution"), Mapping)
            else {}
        )
        async_state = bool(
            str(payload.get("meeting_evidence_state") or "").strip()
            == "verified_signed_async_role_contribution"
        )
        synthetic_state = bool(
            str(payload.get("meeting_evidence_state") or "").strip()
            == "synthetic_planning_only"
        )
        canonical_async_shape = bool(
            async_state
            and str(payload.get("meeting_evidence_reason") or "").strip()
            == "signed_async_role_contribution_verified"
            and async_contribution.get("schema_version")
            == _ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION
            and async_contribution.get("meeting_held") is False
            and async_contribution.get("canonical_pm_execution_authority")
            == "Jean-Claude"
            and async_contribution.get("pm_execution_authority_transferred") is False
            and payload.get("planned_participants")
            == [str(async_contribution.get("display_name") or "").strip()]
            and not discussion
        )
        canonical_synthetic_shape = bool(
            synthetic_state
            and str(payload.get("meeting_evidence_reason") or "").strip()
            == "independent_agent_evidence_missing"
            and not async_contribution
            and all(
                str(item.get("provenance") or "").strip().lower()
                in _SYNTHETIC_ROLE_PROVENANCE
                for item in discussion
            )
        )
        if canonical_async_shape:
            relevance = payload.get("standup_relevance")
            try:
                canonical_relevance = (
                    validate_standup_relevance_plan(relevance)
                    if isinstance(relevance, Mapping)
                    else {}
                )
            except ValueError:
                canonical_relevance = {}
            canonical_async_shape = bool(
                canonical_relevance
                and str(canonical_relevance.get("disposition") or "").strip()
                == "decision_record"
            )
        if (
            str(payload.get("record_kind") or "").strip()
            != _WORKSPACE_CYCLE_PLAN_RECORD_KIND
            or payload.get("meeting_held") is not False
            or payload.get("evaluation_only") is not True
            or not (canonical_synthetic_shape or canonical_async_shape)
            or payload.get("meeting_evidence") not in (None, {})
            or payload.get("participants") != []
            or str(payload.get("cycle_id") or "").strip() != cycle_id
        ):
            continue
        if recursion.get("evaluated") is not True:
            continue
        if not _workspace_cycle_plan_resolutions_are_complete(payload):
            continue
        source_observed_at = _standup_source_observed_at(payload)
        if (
            source_observed_at is None
            or not same_utc_observation_second(
                source_observed_at, freshness_reference
            )
            or source_observed_at.date() != cycle_date
        ):
            continue
        adapted = _adapt_workspace_coordination_record(
            raw,
            workspace=workspace,
            cycle_id=cycle_id,
            source_observed_at=source_observed_at,
            evidence_ref_prefix="coordination-record",
            summary_prefix=(
                "Workspace async role contribution (no meeting held): "
                if canonical_async_shape
                else "Workspace cycle plan (no meeting held): "
            ),
        )
        if workspace not in latest or source_observed_at > latest[workspace][0]:
            latest[workspace] = (source_observed_at, adapted)
    return {workspace: payload for workspace, (_observed, payload) in latest.items()}


def adapt_daily_workspace_evaluations(
    evaluations: list[Mapping[str, Any]],
    *,
    cycle_id: str,
    cycle_date: date,
    observed_at: datetime,
    expected_workspaces: list[str],
    excluded_workspaces: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Adapt the one governed FEEZIE non-meeting result into PortfolioCycle.

    Zero selected roles may produce a governed no-change evaluation. Exactly
    one selected role has conclusion authority only after a signed contribution,
    non-meeting coordination record, canonical decision/event linkage, and a
    terminal PM disposition all exist. The historical decision-record JSONL is
    compatibility evidence only and can never produce a PortfolioCycle
    conclusion. Other workspace evaluation shapes have no authority here.
    """

    freshness_reference = _ai_clone_utc_observation(observed_at)
    if (
        _FEEZIE_WORKSPACE_KEY not in set(expected_workspaces)
        or _FEEZIE_WORKSPACE_KEY in set(excluded_workspaces or set())
    ):
        return {}
    candidates = [
        item
        for item in evaluations
        if isinstance(item, Mapping)
        and str(item.get("workspace_key") or "").strip() == _FEEZIE_WORKSPACE_KEY
    ]
    if len(candidates) != 1:
        return {}
    evaluation = candidates[0]
    status = str(evaluation.get("status") or "").strip()
    if status not in {
        "async_contribution",
        "collapse_freshness",
    }:
        return {}
    is_async_contribution = status == "async_contribution"
    if (
        str(evaluation.get("evaluation_schema_version") or "").strip()
        != _WORKSPACE_CYCLE_EVALUATION_SCHEMA_VERSION
        or str(evaluation.get("standup_kind") or "").strip() != "workspace_sync"
        or str(evaluation.get("cycle_id") or "").strip() != cycle_id
        or evaluation.get("promotion_suppressed")
        is not (False if is_async_contribution else True)
        or evaluation.get("cycle_evaluation_only") is not True
        or evaluation.get("meeting_held") is not False
        or type(evaluation.get("owner_decision_count")) is not int
        or int(evaluation.get("owner_decision_count") or 0) < 0
        or (
            not is_async_contribution
            and evaluation.get("owner_decision_count") != 0
        )
        or (
            is_async_contribution
            and not str(evaluation.get("created_standup_id") or "").strip()
        )
        or (
            not is_async_contribution
            and evaluation.get("created_standup_id") is not None
        )
        or (
            evaluation.get("owner_decision_bridge_replayed") is not None
            and evaluation.get("owner_decision_bridge_replayed") is not False
        )
    ):
        return {}
    if is_async_contribution:
        contribution_id = str(
            evaluation.get("async_role_contribution_id") or ""
        ).strip()
        report_run_id = str(
            evaluation.get("async_role_participant_report_run_id") or ""
        ).strip()
        participant = str(
            evaluation.get("async_role_display_name") or ""
        ).strip()
        canonical_decision_id = str(
            evaluation.get("canonical_decision_id") or ""
        ).strip()
        canonical_event_id = str(
            evaluation.get("canonical_event_id") or ""
        ).strip()
        dispositions = [
            dict(item)
            for item in evaluation.get(
                "async_recommendation_terminal_dispositions"
            )
            or []
            if isinstance(item, Mapping)
        ]
        if (
            _UUID_RE.fullmatch(contribution_id) is None
            or _UUID_RE.fullmatch(report_run_id) is None
            or not participant
            or _UUID_RE.fullmatch(canonical_decision_id) is None
            or _UUID_RE.fullmatch(canonical_event_id) is None
            or evaluation.get("canonical_pm_execution_authority")
            != "Jean-Claude"
            or evaluation.get("pm_execution_authority_transferred") is not False
            or not dispositions
            or any(
                str(item.get("state") or "").strip()
                not in _TERMINAL_RECOMMENDATION_STATES
                for item in dispositions
            )
        ):
            return {}
        observed = _parse_explicit_time(evaluation.get("observed_at"))
        if (
            observed is None
            or not same_utc_observation_second(observed, freshness_reference)
            or observed.date() != cycle_date
        ):
            return {}
        canonical_goal = _canonical_workspace_goal(_FEEZIE_WORKSPACE_KEY)
        if canonical_goal is None:
            return {}
        observed_text = observed.isoformat()
        return {
            _FEEZIE_WORKSPACE_KEY: {
                "cycle_id": cycle_id,
                "observed_at": observed_text,
                "goal": canonical_goal,
                **_non_meeting_conclusion_fields(),
                "summary": (
                    f"{participant} contributed one independently signed FEEZIE role lens; "
                    "no meeting was held and Jean-Claude's PM/execution authority did not transfer."
                ),
                "system_decisions": [
                    {
                        "kind": "admit_signed_async_role_input",
                        "canonical_decision_id": canonical_decision_id,
                    }
                ],
                "actions_taken": [
                    {
                        "kind": "verified_async_role_contribution",
                        "contribution_id": contribution_id,
                        "participant_report_run_id": report_run_id,
                        "participant": participant,
                    }
                ],
                "recommendation_resolutions": dispositions,
                "next_cycle_inputs": [
                    {
                        "summary": (
                            "Consume the signed async contribution and its terminal dispositions "
                            "in the next FEEZIE evaluation."
                        ),
                        "contribution_id": contribution_id,
                    }
                ],
                "evidence_links": [
                    {
                        "ref": f"automation-run:{report_run_id}",
                        "source_observed_at": observed_text,
                    },
                    {
                        "ref": f"coordination-record:{evaluation.get('created_standup_id')}",
                        "source_observed_at": observed_text,
                    },
                    {
                        "ref": f"canonical-decision:{canonical_decision_id}",
                        "source_observed_at": observed_text,
                    },
                    {
                        "ref": f"normalized-event:{canonical_event_id}",
                        "source_observed_at": observed_text,
                    },
                ],
                "_conclusion_kind": "conclusion",
            }
        }
    for forbidden_key in (
        "created_card_count",
        "existing_card_count",
        "created_card_ids",
        "existing_card_ids",
        "selected_roles",
        "participant_count",
        "participant_plan",
        "participants",
        "actions_taken",
        "owner_decisions",
        "recommendation_resolutions",
    ):
        if forbidden_key in evaluation:
            return {}

    source_observed_at = _parse_explicit_time(evaluation.get("observed_at"))
    if (
        source_observed_at is None
        or not same_utc_observation_second(
            source_observed_at, freshness_reference
        )
        or source_observed_at.date() != cycle_date
    ):
        return {}

    if any(
        key in evaluation
        for key in (
            "goal",
            "goal_contract",
            "progress_signals",
            "phase_gate",
            "no_action_trigger",
            "safe_internal_boundary",
            "owner_required_boundary",
            "authority_refs",
            "future_trigger",
        )
    ):
        return {}
    canonical_goal = _canonical_workspace_goal(_FEEZIE_WORKSPACE_KEY)
    if canonical_goal is None:
        return {}

    observed_text = source_observed_at.isoformat()
    common: dict[str, Any] = {
        "cycle_id": cycle_id,
        "observed_at": observed_text,
        "goal": canonical_goal,
        **_non_meeting_conclusion_fields(),
    }
    if any(str(evaluation.get(key) or "").strip() for key in (
        "decision_record_id",
        "decision_record_owner_role",
        "decision_record_schema_version",
        "decision_record_authority_state",
        "decision_record_compatibility_state",
    )):
        return {}
    trigger = str(canonical_goal["no_action_trigger"])
    return {
        _FEEZIE_WORKSPACE_KEY: {
            **common,
            "summary": (
                "FEEZIE relevance was evaluated with no changed eligible input; no meeting was held "
                "and no PM or action work was created."
            ),
            "no_action": [
                {
                    "summary": "No changed eligible FEEZIE input required a meeting or internal work.",
                    "trigger": trigger,
                    "selected": True,
                }
            ],
            "next_cycle_inputs": [
                {
                    "summary": "Reevaluate FEEZIE when the canonical no-action trigger occurs.",
                    "trigger": trigger,
                }
            ],
            "evidence_links": [
                {
                    "ref": f"workspace-cycle-evaluation:{cycle_id}:{_FEEZIE_WORKSPACE_KEY}",
                    "source_observed_at": observed_text,
                }
            ],
            "_conclusion_kind": "healthy_no_change",
        }
    }


def run_portfolio_coordination(
    *,
    service: PortfolioCycleService,
    portfolio_cycle_id: str,
    cycle_date: date,
    observed_at: datetime,
    expected_workspaces: list[str],
    readiness_id: str,
    standup_rows: list[Mapping[str, Any]],
    system_health: Mapping[str, Any],
    morning_brief_ref: str | None = None,
    owner_calls: list[Mapping[str, Any]] | None = None,
    recommended_next_actions: list[str] | None = None,
    workspace_cycle_evaluations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    cycle_observed_at = _ai_clone_utc_observation(observed_at)
    service.start_cycle(
        portfolio_cycle_id=portfolio_cycle_id,
        cycle_date=cycle_date,
        expected_workspaces=expected_workspaces,
        readiness_id=readiness_id,
        morning_brief_ref=morning_brief_ref,
        observed_at=cycle_observed_at,
    )
    adapted = adapt_daily_workspace_standups(
        standup_rows,
        cycle_id=portfolio_cycle_id,
        cycle_date=cycle_date,
        observed_at=cycle_observed_at,
        expected_workspaces=expected_workspaces,
    )
    for workspace, payload in adapted.items():
        normalized_payload = dict(payload)
        conclusion_kind = str(normalized_payload.pop("_conclusion_kind", "conclusion"))
        service.record_workspace_conclusion(
            portfolio_cycle_id=portfolio_cycle_id,
            workspace_key=workspace,
            conclusion_kind=conclusion_kind,
            provenance_kind="deterministic_policy",
            payload=normalized_payload,
            idempotency_key=f"daily-standup-adapter:{portfolio_cycle_id}:{workspace}",
        )
    plan_conclusions = adapt_daily_workspace_cycle_plans(
        standup_rows,
        cycle_id=portfolio_cycle_id,
        cycle_date=cycle_date,
        observed_at=cycle_observed_at,
        expected_workspaces=expected_workspaces,
        excluded_workspaces=set(adapted),
    )
    for workspace, payload in plan_conclusions.items():
        normalized_payload = dict(payload)
        conclusion_kind = str(normalized_payload.pop("_conclusion_kind", "conclusion"))
        service.record_workspace_conclusion(
            portfolio_cycle_id=portfolio_cycle_id,
            workspace_key=workspace,
            conclusion_kind=conclusion_kind,
            provenance_kind="deterministic_policy",
            payload=normalized_payload,
            idempotency_key=(
                f"daily-workspace-cycle-plan-adapter:{portfolio_cycle_id}:{workspace}"
            ),
        )
    evaluation_conclusions = adapt_daily_workspace_evaluations(
        list(workspace_cycle_evaluations or []),
        cycle_id=portfolio_cycle_id,
        cycle_date=cycle_date,
        observed_at=cycle_observed_at,
        expected_workspaces=expected_workspaces,
        excluded_workspaces=set(adapted) | set(plan_conclusions),
    )
    for workspace, payload in evaluation_conclusions.items():
        normalized_payload = dict(payload)
        conclusion_kind = str(normalized_payload.pop("_conclusion_kind", "conclusion"))
        service.record_workspace_conclusion(
            portfolio_cycle_id=portfolio_cycle_id,
            workspace_key=workspace,
            conclusion_kind=conclusion_kind,
            provenance_kind="deterministic_policy",
            payload=normalized_payload,
            idempotency_key=(
                f"daily-workspace-evaluation-adapter:{portfolio_cycle_id}:{workspace}"
            ),
        )
    return service.conclude_ops(
        portfolio_cycle_id=portfolio_cycle_id,
        system_health=system_health,
        owner_calls=list(owner_calls or []),
        recommended_next_actions=recommended_next_actions,
        observed_at=cycle_observed_at,
        workspace_cycle_evaluations=workspace_cycle_evaluations,
    )
