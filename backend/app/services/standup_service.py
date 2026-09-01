from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional
from uuid import NAMESPACE_URL, uuid4, uuid5

from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.models import PMCard, PMCardCreate, PMCardUpdate, StandupCreate, StandupEntry, StandupPromotionRequest, StandupPromotionResult, StandupUpdate
from app.security.execution_authorization import verify_execution_payload
from app.services import pm_card_service
from app.services.brain_response_privacy_service import sanitize_brain_payload
from app.services.execution_gate_service import (
    AUTO_EXECUTE,
    BOUNDED_PROJECT_CAPABILITY,
    NON_OVERRIDABLE_RISK_FACTORS,
    REQUIRE_APPROVAL,
    execution_gate_matches_current,
)
from app.services.open_brain_db import get_pool
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.standup_relevance_service import (
    effective_feezie_meeting_participants,
    validate_standup_relevance_plan,
)
from app.services.standup_truth_service import (
    ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION,
    CANONICAL_MEETING_CLOSER,
    MEETING_RECORD_KIND,
    WORKSPACE_CYCLE_PLAN_RECORD_KIND,
    async_role_contribution_truth,
    canonical_promotion_claims,
    meeting_record_truth,
    remote_standup_pm_update,
    remote_standup_promotion_payload,
)
from app.services.workspace_registry_service import canonicalize_workspace_key, workspace_storage_aliases
from app.services.workspace_runtime_contract_service import (
    canonical_standup_kind_for_workspace,
    standup_participants_for,
)
from app.utils.ai_clone_clock import validate_clocked_cycle_observation


def list_standups(limit: int = 50, owner: Optional[str] = None, workspace_key: Optional[str] = None) -> List[StandupEntry]:
    pool = get_pool()
    clauses = []
    params = []
    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    if workspace_key:
        clauses.append("LOWER(workspace_key) = ANY(%s)")
        params.append(list(workspace_storage_aliases(workspace_key)))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    query = f"""
        SELECT id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
        FROM standups
        {where}
        ORDER BY created_at DESC
        LIMIT %s
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall() or []
    return [_row_to_entry(row) for row in rows]


def public_standup_entry(entry: StandupEntry) -> StandupEntry:
    """Return a presentation-safe copy without rewriting stored history.

    Historical standups legitimately contain machine-local artifact paths from
    earlier runtimes. Those paths remain useful audit evidence in Postgres, but
    the web control plane should receive stable repository references rather
    than usernames, private runtime roots, or credentials.
    """

    return StandupEntry.model_validate(sanitize_brain_payload(entry))


def public_standup_entries(entries: List[StandupEntry]) -> List[StandupEntry]:
    return [public_standup_entry(entry) for entry in entries]


def public_standup_promotion(result: StandupPromotionResult) -> StandupPromotionResult:
    return StandupPromotionResult.model_validate(sanitize_brain_payload(result))


def _require_current_standup_kind(
    *,
    workspace_key: str | None,
    standup_kind: object,
) -> str:
    """Reject new writes that try to borrow another workspace's standup lane."""

    supplied_kind = str(standup_kind or "").strip()
    if not supplied_kind:
        return supplied_kind
    canonical_kind = canonical_standup_kind_for_workspace(
        workspace_key,
        supplied_kind,
    )
    if supplied_kind != canonical_kind:
        raise ValueError(
            "standup_kind does not match the canonical workspace standup contract"
        )
    return canonical_kind


def _completed_cycle_standup_id(payload: StandupCreate) -> str | None:
    payload_body = dict(payload.payload or {})
    cycle_id = str(payload_body.get("cycle_id") or "").strip()
    standup_kind = str(payload_body.get("standup_kind") or "").strip()
    if not (
        cycle_id
        and standup_kind
        and str(payload.status or "").strip().lower() == "completed"
    ):
        return None
    # Preserve the established completed-meeting identity while giving the
    # non-meeting plan its own append-only replay lane.  A failed due meeting
    # can therefore retain its exact plan evidence and later append the real
    # independently receipted meeting for the same observation without a
    # semantic-ID conflict.
    record_discriminator = (
        f":{WORKSPACE_CYCLE_PLAN_RECORD_KIND}"
        if str(payload_body.get("record_kind") or "").strip()
        == WORKSPACE_CYCLE_PLAN_RECORD_KIND
        else ""
    )
    return str(
        uuid5(
            NAMESPACE_URL,
            f"ai-clone:standup:{payload.workspace_key}:{standup_kind}:{cycle_id}"
            f"{record_discriminator}",
        )
    )


def _exact_admitted_meeting_replay(
    payload: StandupPromotionRequest,
    *,
    canonical_workspace_key: str,
) -> StandupEntry | None:
    """Recognize an immutable admitted meeting without re-verifying its pack.

    Participant identity digests are verified when the meeting is admitted.
    A later legitimate identity-pack edit must not strand an independently
    committed PM handoff.  Recovery is allowed only when every remotely
    supplied claim, discussion round, evidence receipt, and recommendation
    request exactly matches the still-valid stored semantic row.  PM creation
    remains idempotent by coordination/request digest, and the terminal merge
    revalidates these stored requests and the semantic hash under ``FOR
    UPDATE`` in ``_merge_promotion_recommendation_resolutions``.
    """

    if (
        not payload.meeting_evidence
        or not str(payload.cycle_id or "").strip()
        or not str(payload.meeting_id or "").strip()
    ):
        return None
    deterministic_id = _completed_cycle_standup_id(
        StandupCreate(
            owner=payload.owner,
            workspace_key=canonical_workspace_key,
            status="completed",
            payload={
                "standup_kind": payload.standup_kind,
                "cycle_id": payload.cycle_id,
                "record_kind": MEETING_RECORD_KIND,
            },
        )
    )
    if deterministic_id is None:
        return None
    existing = get_standup(deterministic_id)
    if existing is None or str(existing.status or "").strip().lower() != "completed":
        return None
    body = dict(existing.payload or {})
    if (
        body.get("record_kind") != MEETING_RECORD_KIND
        or body.get("meeting_held") is not True
        or body.get("evaluation_only") is not False
    ):
        return None
    stored_claim = str(body.get("semantic_payload_sha256") or "").strip()
    if not stored_claim or stored_claim != _standup_semantic_payload_sha256(existing):
        return None
    stored_requests = _canonical_stored_recommendation_requests(
        body.get("recommendation_requests")
    )
    incoming_requests = [
        _canonical_recommendation_request(update)
        for update in payload.pm_updates or []
    ]
    if incoming_requests != stored_requests:
        return None
    stored_claims = body.get("promotion_claims")
    if (
        not isinstance(stored_claims, Mapping)
        or dict(stored_claims) != canonical_promotion_claims(payload)
    ):
        return None
    stored_evidence = body.get("meeting_evidence")
    if (
        not isinstance(stored_evidence, Mapping)
        or _semantic_json(stored_evidence)
        != _semantic_json(payload.meeting_evidence)
    ):
        return None
    stored_discussion = body.get("discussion")
    if (
        not isinstance(stored_discussion, list)
        or _semantic_json(stored_discussion)
        != _semantic_json(payload.discussion_rounds)
    ):
        return None
    return existing


def _canonical_recommendation_request(update: object) -> dict[str, Any]:
    try:
        return remote_standup_pm_update(update)
    except ValueError as exc:
        raise TypeError("standup recommendation must be a mapping or model") from exc


def _semantic_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _recommendation_request_sha256(request: Mapping[str, Any]) -> str:
    return hashlib.sha256(_semantic_json(dict(request)).encode("utf-8")).hexdigest()


def _standup_semantic_payload(payload: StandupCreate | StandupEntry) -> dict[str, Any]:
    body = dict(payload.payload or {})
    body.pop("semantic_payload_sha256", None)
    body.pop("recommendation_resolutions", None)
    body.pop("pm_updates", None)
    recursion = body.get("recursion")
    if isinstance(recursion, Mapping):
        recursion_body = dict(recursion)
        recursion_body.pop("recommendation_resolutions", None)
        # The terminal async handoff is written by this service only after the
        # existing PM authority has resolved every recommendation.  Normalize
        # that derived receipt back to its pre-resolution form so the immutable
        # coordination input keeps the same semantic identity across replay.
        # The authoritative terminal truth remains the independently checked
        # recommendation_resolutions/card bindings, which are deliberately
        # excluded above for the same reason.
        async_handoff = recursion_body.get("async_role_recommendation_handoff")
        if (
            isinstance(async_handoff, Mapping)
            and str(async_handoff.get("state") or "").strip()
            == "resolved_through_existing_pm_authority"
        ):
            recursion_body["async_role_recommendation_handoff"] = {
                "state": "pending_existing_pm_resolution",
                "recommendation_count": int(
                    async_handoff.get("recommendation_count") or 0
                ),
                "dependency": "existing_pm_recommendation_authority",
            }
            next_cycle_inputs = recursion_body.get("next_cycle_inputs")
            if isinstance(next_cycle_inputs, list):
                recursion_body["next_cycle_inputs"] = [
                    item
                    for item in next_cycle_inputs
                    if not (
                        isinstance(item, Mapping)
                        and str(item.get("kind") or "").strip()
                        == "async_role_recommendation_outcomes"
                    )
                ]
        body["recursion"] = recursion_body
    if not _claims_real_meeting(body) and body.get("recommendations_authorized") is not False:
        # These affirmative plan-authority fields are now derived by the
        # backend.  Excluding only the affirmative/default case preserves the
        # established semantic identity of legacy authorized cycle plans while
        # keeping a withheld plan's terminal authority in its semantic hash.
        for field in (
            "recommendation_authority_state",
            "recommendations_authorized",
            "automatic_dispatch_authorized",
            "owner_decision_routing_required",
        ):
            body.pop(field, None)
    # Meeting classification was added after deterministic cycle replay. Keep
    # legacy and current *non-meeting* planning rows semantically equivalent
    # without erasing any field from a verified real meeting.
    if not _claims_real_meeting(body):
        planned_participants = list(
            body.get("planned_participants") or body.get("participants") or []
        )
        for field in (
            "workspace_key",
            "record_kind",
            "meeting_held",
            "evaluation_only",
            "meeting_evidence_state",
            "meeting_evidence_reason",
            "meeting_evidence",
            "promotion_claims",
            "meeting_id",
            "participants",
            "planned_participants",
        ):
            body.pop(field, None)
        body["planned_participants"] = planned_participants
    return {
        "owner": payload.owner,
        "workspace_key": payload.workspace_key,
        "status": payload.status,
        "blockers": list(payload.blockers or []),
        "commitments": list(payload.commitments or []),
        "needs": list(payload.needs or []),
        "source": payload.source,
        "conversation_path": payload.conversation_path,
        "payload": body,
    }


def _standup_semantic_payload_sha256(payload: StandupCreate | StandupEntry) -> str:
    return hashlib.sha256(_semantic_json(_standup_semantic_payload(payload)).encode("utf-8")).hexdigest()


def _persisted_standup_from_row(row: Mapping[str, Any]) -> StandupEntry:
    return StandupEntry(
        id=str(row["id"]),
        owner=str(row["owner"]),
        workspace_key=str(row["workspace_key"]),
        status=row.get("status"),
        blockers=list(row.get("blockers") or []),
        commitments=list(row.get("commitments") or []),
        needs=list(row.get("needs") or []),
        source=row.get("source"),
        conversation_path=row.get("conversation_path"),
        payload=dict(row.get("payload") or {}),
        created_at=row["created_at"],
    )


def _matching_persisted_resolutions(
    requests: list[dict[str, Any]],
    resolutions: object,
) -> dict[int, dict[str, Any]]:
    """Match persisted terminal receipts to exact recommendation semantics."""

    available = [dict(item) for item in resolutions if isinstance(item, Mapping)] if isinstance(resolutions, list) else []
    matched: dict[int, dict[str, Any]] = {}
    used: set[int] = set()
    for request_index, request in enumerate(requests):
        request_sha = _recommendation_request_sha256(request)
        for resolution_index, resolution in enumerate(available):
            if resolution_index in used:
                continue
            # This state was previously emitted from a shape-only PM payload.
            # No canonical scheduler writer ever existed for that payload, so
            # replay must re-evaluate it against current PM truth rather than
            # preserve an unproved terminal classification.
            if (
                str(resolution.get("state") or "").strip()
                == "scheduled_in_existing_canonical_scheduler"
            ):
                continue
            persisted_sha = str(resolution.get("request_sha256") or "").strip()
            exact_legacy_identity = (
                not persisted_sha
                and str(resolution.get("title") or "") == request["title"]
                and str(resolution.get("workspace_key") or "") == request["workspace_key"]
            )
            if persisted_sha == request_sha or exact_legacy_identity:
                if not str(resolution.get("card_id") or "").strip() or not str(resolution.get("state") or "").strip():
                    continue
                used.add(resolution_index)
                matched[request_index] = resolution
                break
    return matched


def _claims_real_meeting(payload: Mapping[str, Any] | None) -> bool:
    body = dict(payload or {})
    evidence = body.get("meeting_evidence")
    return bool(
        body.get("meeting_held") is True
        or str(body.get("record_kind") or "").strip() == MEETING_RECORD_KIND
        or isinstance(evidence, Mapping) and bool(evidence)
        or str(body.get("meeting_evidence_state") or "").strip()
        == "verified_independent_agent_meeting"
    )


def _has_recommendation_resolution_authority(payload: Mapping[str, Any] | None) -> bool:
    body = dict(payload or {})
    recursion = body.get("recursion")
    return bool(
        "recommendation_resolutions" in body
        or isinstance(recursion, Mapping) and "recommendation_resolutions" in recursion
    )


def _claims_workspace_cycle_plan(payload: Mapping[str, Any] | None) -> bool:
    body = dict(payload or {})
    return bool(
        str(body.get("record_kind") or "").strip()
        == WORKSPACE_CYCLE_PLAN_RECORD_KIND
        or body.get("evaluation_only") is True
        or body.get("meeting_held") is False
    )


def _require_canonical_workspace_cycle_plan(
    payload: Mapping[str, Any],
    *,
    allow_recommendation_resolutions: bool = False,
) -> None:
    body = dict(payload)
    validate_clocked_cycle_observation(body)
    participants = list(body.get("participants") or [])
    planned_participants = [
        str(item).strip()
        for item in body.get("planned_participants") or []
        if str(item).strip()
    ]
    discussion = [
        dict(item)
        for item in body.get("discussion") or []
        if isinstance(item, Mapping)
    ]
    recursion = (
        dict(body.get("recursion") or {})
        if isinstance(body.get("recursion"), Mapping)
        else {}
    )
    async_contribution = (
        dict(recursion.get("async_role_contribution") or {})
        if isinstance(recursion.get("async_role_contribution"), Mapping)
        else {}
    )
    async_evidence_state = (
        body.get("meeting_evidence_state")
        == "verified_signed_async_role_contribution"
    )
    canonical_async_shape = bool(
        async_evidence_state
        and body.get("meeting_evidence_reason")
        == "signed_async_role_contribution_verified"
        and async_contribution.get("schema_version")
        == ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION
        and async_contribution.get("meeting_held") is False
        and async_contribution.get("canonical_pm_execution_authority")
        == CANONICAL_MEETING_CLOSER
        and async_contribution.get("pm_execution_authority_transferred") is False
        and len(planned_participants) == 1
        and planned_participants
        == [str(async_contribution.get("display_name") or "").strip()]
    )
    canonical_planning_shape = bool(
        body.get("meeting_evidence_state") == "synthetic_planning_only"
        and body.get("meeting_evidence_reason")
        == "independent_agent_evidence_missing"
        and not async_contribution
    )
    if (
        body.get("record_kind") != WORKSPACE_CYCLE_PLAN_RECORD_KIND
        or body.get("meeting_held") is not False
        or body.get("evaluation_only") is not True
        or not (canonical_planning_shape or canonical_async_shape)
        or body.get("meeting_evidence") not in ({}, None)
        or body.get("promotion_claims") not in ({}, None)
        or participants
        or not planned_participants
        or len(set(planned_participants)) != len(planned_participants)
        or any(
            str(item.get("provenance") or "").strip()
            == "independent_codex_agent_run"
            for item in discussion
        )
        or (
            _has_recommendation_resolution_authority(body)
            and not allow_recommendation_resolutions
        )
    ):
        raise ValueError("workspace_cycle_plan payload is not a canonical non-meeting plan")


_TERMINAL_RECOMMENDATION_RESOLUTION_STATES = frozenset(
    {
        "executed_automatically",
        "placed_in_execution_queue",
        "bounded_owner_decision",
        "blocked",
        "rejected_by_policy",
        "intentionally_retained",
    }
)


def _canonical_stored_recommendation_requests(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(
            "The coordination record has no canonical recommendation request list."
        )
    try:
        return [_canonical_recommendation_request(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "The coordination record recommendation request list is invalid."
        ) from exc


def _require_resolution_card_bindings(
    cur: Any,
    *,
    standup_id: str,
    recommendation_requests: list[dict[str, Any]],
    resolutions: list[dict[str, Any]],
) -> None:
    """Verify every terminal resolution against the canonical PM row it cites."""

    card_ids = [str(item.get("card_id") or "").strip() for item in resolutions]
    if any(not card_id for card_id in card_ids) or len(set(card_ids)) != len(card_ids):
        raise pm_card_service.PMRecommendationIdentityConflict(
            "Every coordination recommendation must cite one distinct canonical PM card."
        )
    cur.execute(
        """
        SELECT id, title, link_type, link_id, payload,
               recommendation_coordination_record_id,
               recommendation_request_sha256
        FROM pm_cards
        WHERE id = ANY(%s)
        """,
        (card_ids,),
    )
    rows = cur.fetchall() or []
    cards_by_id = {str(row["id"]): row for row in rows}
    if set(cards_by_id) != set(card_ids):
        raise pm_card_service.PMRecommendationIdentityConflict(
            "A coordination recommendation cites a missing canonical PM card."
        )

    for request, resolution in zip(recommendation_requests, resolutions, strict=True):
        state = str(resolution.get("state") or "").strip()
        if state not in _TERMINAL_RECOMMENDATION_RESOLUTION_STATES:
            raise pm_card_service.PMRecommendationIdentityConflict(
                "A coordination recommendation has no permitted terminal resolution state."
            )
        card_id = str(resolution.get("card_id") or "").strip()
        card = cards_by_id[card_id]
        card_payload = (
            dict(card.get("payload") or {})
            if isinstance(card.get("payload"), Mapping)
            else {}
        )
        request_sha256 = _recommendation_request_sha256(request)
        stored_coordination_id = str(
            card.get("recommendation_coordination_record_id")
            or card_payload.get("created_from_coordination_record_id")
            or ""
        ).strip()
        stored_request_sha256 = str(
            card.get("recommendation_request_sha256")
            or card_payload.get("recommendation_request_sha256")
            or ""
        ).strip()
        exact_identity = bool(
            stored_coordination_id == standup_id
            and stored_request_sha256 == request_sha256
        )
        direct_link = bool(
            str(card.get("link_id") or "").strip() == standup_id
            and str(card.get("link_type") or "").strip()
            in {"standup", WORKSPACE_CYCLE_PLAN_RECORD_KIND}
        )
        carried_ids = {
            str(value).strip()
            for value in card_payload.get("carry_forward_standup_ids") or []
            if str(value).strip()
        }
        carried_forward = bool(
            str(card_payload.get("latest_carry_forward_standup_id") or "").strip()
            == standup_id
            or standup_id in carried_ids
        )
        request_workspace = canonicalize_workspace_key(
            str(request.get("workspace_key") or "shared_ops"),
            default="shared_ops",
        )
        card_workspace = canonicalize_workspace_key(
            str(
                card_payload.get("workspace_key")
                or card_payload.get("workspace")
                or card_payload.get("belongs_to_workspace")
                or "shared_ops"
            ),
            default="shared_ops",
        )
        exact_existing_lane = bool(
            str(card.get("title") or "") == str(request.get("title") or "")
            and card_workspace == request_workspace
        )
        if card_workspace != request_workspace or not (
            exact_identity or direct_link or carried_forward or exact_existing_lane
        ):
            raise pm_card_service.PMRecommendationIdentityConflict(
                "A coordination recommendation PM reference is not bound to its exact request."
            )


def _canonical_governed_meeting_payload(
    payload_body: Mapping[str, Any],
    *,
    workspace_key: str,
    source: str | None,
) -> dict[str, Any]:
    body = dict(payload_body)
    participants = [
        str(item).strip()
        for item in body.get("participants") or []
        if str(item).strip()
    ]
    truth = meeting_record_truth(
        body,
        source=source,
        expected_participants=participants,
        workspace_key=workspace_key,
        verify_current_identity_pack=True,
    )
    if not truth["is_meeting"]:
        raise ValueError(
            "Standup meeting evidence is invalid: "
            + str(truth.get("reason") or "unknown")
        )
    body.update(
        {
            "workspace_key": canonicalize_workspace_key(
                workspace_key,
                default="shared_ops",
            ),
            "record_kind": MEETING_RECORD_KIND,
            "meeting_held": True,
            "evaluation_only": False,
            "meeting_evidence_state": truth["state"],
            "meeting_evidence_reason": truth["reason"],
            "meeting_evidence": dict(truth["canonical_meeting_evidence"]),
            "discussion": list(truth["canonical_discussion"]),
            "promotion_claims": dict(truth["canonical_promotion_claims"]),
        }
    )
    return body


def create_standup(
    payload: StandupCreate,
    *,
    _governed_meeting_write: bool = False,
    _governed_plan_write: bool = False,
) -> StandupEntry:
    payload_body = dict(payload.payload or {})
    _require_current_standup_kind(
        workspace_key=payload.workspace_key,
        standup_kind=payload_body.get("standup_kind"),
    )
    claimed_meeting = _claims_real_meeting(payload_body)
    claimed_plan = _claims_workspace_cycle_plan(payload_body)
    authority_shaped_receipts = _has_recommendation_resolution_authority(payload_body)
    authority_shaped_promotion = bool(payload_body.get("promotion_claims"))
    deterministic_id = _completed_cycle_standup_id(payload)
    if deterministic_id is not None and not (
        _governed_meeting_write or _governed_plan_write
    ):
        raise ValueError(
            "Completed cycle records can only be created through governed standup promotion."
        )
    if claimed_meeting and not _governed_meeting_write:
        raise ValueError(
            "Completed meeting records can only be created through governed standup promotion."
        )
    if claimed_plan and not _governed_plan_write:
        raise ValueError(
            "Workspace cycle plans can only be created through governed standup promotion."
        )
    if (
        authority_shaped_receipts
        or authority_shaped_promotion
    ) and not (_governed_meeting_write or _governed_plan_write):
        raise ValueError(
            "Coordination authority receipts can only be written through governed standup promotion."
        )
    if claimed_meeting:
        if str(payload.status or "").strip().lower() != "completed":
            raise ValueError("A governed meeting record must be completed when it is written.")
        validate_clocked_cycle_observation(payload_body)
        payload_body = _canonical_governed_meeting_payload(
            payload_body,
            workspace_key=payload.workspace_key,
            source=payload.source,
        )
        payload = payload.model_copy(update={"payload": payload_body})
    if claimed_plan:
        if str(payload.status or "").strip().lower() != "completed":
            raise ValueError("A governed workspace cycle plan must be completed when written.")
        _require_canonical_workspace_cycle_plan(payload_body)
    pool = get_pool()
    cycle_id = str(payload_body.get("cycle_id") or "").strip()
    standup_kind = str(payload_body.get("standup_kind") or "").strip()
    deterministic_cycle_entry = deterministic_id is not None
    entry_id = deterministic_id or str(uuid4())
    semantic_sha256 = _standup_semantic_payload_sha256(payload)
    claimed_sha256 = str(payload_body.get("semantic_payload_sha256") or "").strip()
    if claimed_sha256 and claimed_sha256 != semantic_sha256:
        raise ValueError("standup cycle semantic payload hash is invalid")
    if deterministic_cycle_entry:
        payload_body["semantic_payload_sha256"] = semantic_sha256
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO standups (id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                RETURNING id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
                """,
                (
                    entry_id,
                    payload.owner,
                    payload.workspace_key,
                    payload.status,
                    payload.blockers,
                    payload.commitments,
                    payload.needs,
                    payload.source,
                    payload.conversation_path,
                    Json(payload_body),
                ),
            )
            row = cur.fetchone()
            if row is None and deterministic_cycle_entry:
                cur.execute(
                    """
                    SELECT id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
                    FROM standups
                    WHERE id = %s
                    """,
                    (entry_id,),
                )
                row = cur.fetchone()
                existing_entry = _persisted_standup_from_row(row) if row is not None else None
                existing_payload = dict(existing_entry.payload or {}) if existing_entry is not None else {}
                existing_semantic_sha256 = (
                    _standup_semantic_payload_sha256(existing_entry)
                    if existing_entry is not None
                    else None
                )
                stored_claim = str(existing_payload.get("semantic_payload_sha256") or "").strip()
                if (
                    existing_entry is None
                    or stored_claim and stored_claim != existing_semantic_sha256
                    or existing_semantic_sha256 != semantic_sha256
                ):
                    raise ValueError("standup cycle semantic conflict")
        conn.commit()
    return _row_to_entry(row)


def update_standup(
    entry_id: str,
    payload: StandupUpdate,
    *,
    _governed_meeting_write: bool = False,
    _governed_plan_write: bool = False,
) -> Optional[StandupEntry]:
    if payload.payload is not None:
        if _claims_real_meeting(payload.payload) and not _governed_meeting_write:
            raise ValueError(
                "Completed meeting records can only be changed through governed standup promotion."
            )
        if _claims_workspace_cycle_plan(payload.payload) and not _governed_plan_write:
            raise ValueError(
                "Workspace cycle plans can only be changed through governed standup promotion."
            )
        if (
            _has_recommendation_resolution_authority(payload.payload)
            or bool(payload.payload.get("promotion_claims"))
        ) and not (_governed_meeting_write or _governed_plan_write):
            raise ValueError(
                "Coordination authority receipts can only be changed through governed standup promotion."
            )
    fields = []
    values = []
    if payload.workspace_key is not None:
        fields.append("workspace_key = %s")
        values.append(payload.workspace_key)
    if payload.status is not None:
        fields.append("status = %s")
        values.append(payload.status)
    if payload.blockers is not None:
        fields.append("blockers = %s")
        values.append(payload.blockers)
    if payload.commitments is not None:
        fields.append("commitments = %s")
        values.append(payload.commitments)
    if payload.needs is not None:
        fields.append("needs = %s")
        values.append(payload.needs)
    if payload.source is not None:
        fields.append("source = %s")
        values.append(payload.source)
    if payload.conversation_path is not None:
        fields.append("conversation_path = %s")
        values.append(payload.conversation_path)
    if payload.payload is not None:
        fields.append("payload = %s")
        values.append(Json(payload.payload))

    if not fields:
        return get_standup(entry_id)

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
                FROM standups
                WHERE id = %s
                """,
                (entry_id,),
            )
            current_row = cur.fetchone()
            if current_row is None:
                return None
            current = _persisted_standup_from_row(current_row)
            if payload.payload is not None:
                _require_current_standup_kind(
                    workspace_key=payload.workspace_key or current.workspace_key,
                    standup_kind=payload.payload.get("standup_kind"),
                )
            current_claims_meeting = _claims_real_meeting(current.payload)
            current_claims_plan = _claims_workspace_cycle_plan(current.payload)
            if current_claims_meeting and not _governed_meeting_write:
                raise ValueError(
                    "Completed meeting records are immutable outside governed standup promotion."
                )
            if current_claims_plan and not _governed_plan_write:
                raise ValueError(
                    "Workspace cycle plans are immutable outside governed standup promotion."
                )
            if current_claims_meeting:
                proposed_workspace = payload.workspace_key or current.workspace_key
                proposed_source = payload.source if payload.source is not None else current.source
                proposed_status = payload.status if payload.status is not None else current.status
                if str(proposed_status or "").strip().lower() != "completed":
                    raise ValueError("A governed completed meeting cannot change lifecycle state.")
                proposed_body = (
                    dict(payload.payload)
                    if payload.payload is not None
                    else dict(current.payload or {})
                )
                canonical_body = _canonical_governed_meeting_payload(
                    proposed_body,
                    workspace_key=proposed_workspace,
                    source=proposed_source,
                )
                if payload.payload is not None:
                    payload = payload.model_copy(update={"payload": canonical_body})
                    fields = [field for field in fields if field != "payload = %s"]
                    # Payload is always the last JSON field added above, but
                    # rebuild values to avoid coupling the authority check to
                    # field ordering.
                    values = []
                    fields = []
                    if payload.workspace_key is not None:
                        fields.append("workspace_key = %s")
                        values.append(payload.workspace_key)
                    if payload.status is not None:
                        fields.append("status = %s")
                        values.append(payload.status)
                    if payload.blockers is not None:
                        fields.append("blockers = %s")
                        values.append(payload.blockers)
                    if payload.commitments is not None:
                        fields.append("commitments = %s")
                        values.append(payload.commitments)
                    if payload.needs is not None:
                        fields.append("needs = %s")
                        values.append(payload.needs)
                    if payload.source is not None:
                        fields.append("source = %s")
                        values.append(payload.source)
                    if payload.conversation_path is not None:
                        fields.append("conversation_path = %s")
                        values.append(payload.conversation_path)
                    fields.append("payload = %s")
                    values.append(Json(canonical_body))
            values.append(entry_id)
            query = f"""
                UPDATE standups
                SET {', '.join(fields)}, updated_at = NOW(), retention_contract_version = NULL,
                    retention_resolved_at = NULL, retention_local_receipt_sha256 = NULL
                WHERE id = %s
                  AND retention_contract_version IS DISTINCT FROM 'railway_retained_standup_receipt/v1'
                RETURNING id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
            """
            cur.execute(query, values)
            row = cur.fetchone()
        conn.commit()
    return _row_to_entry(row) if row else None


def get_standup(entry_id: str) -> Optional[StandupEntry]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, owner, workspace_key, status, blockers, commitments, needs, source, conversation_path, payload, created_at
                FROM standups
                WHERE id = %s
                """,
                (entry_id,),
            )
            row = cur.fetchone()
    return _row_to_entry(row) if row else None


def promote_standup(payload: StandupPromotionRequest) -> StandupPromotionResult:
    # Defense in depth: callers are expected to project locally before the
    # request crosses the network, but Railway's writer independently enforces
    # the same closed contract before verification or persistence.
    payload = StandupPromotionRequest.model_validate(
        remote_standup_promotion_payload(payload)
    )
    validate_clocked_cycle_observation(
        {
            "cycle_id": payload.cycle_id,
            "recursion": dict(payload.recursion or {}),
        },
        cycle_id=payload.cycle_id,
    )
    relevance = dict(payload.standup_relevance or {})
    async_role_truth: dict[str, Any] | None = None
    canonical_workspace_key = canonicalize_workspace_key(payload.workspace_key, default="shared_ops")
    _require_current_standup_kind(
        workspace_key=canonical_workspace_key,
        standup_kind=payload.standup_kind,
    )
    admitted_meeting_replay = _exact_admitted_meeting_replay(
        payload,
        canonical_workspace_key=canonical_workspace_key,
    )
    if canonical_workspace_key == "feezie-os" and not relevance:
        raise ValueError("FEEZIE standup promotion requires the canonical relevance plan.")
    if canonical_workspace_key != "feezie-os" and relevance:
        raise ValueError(
            "Only FEEZIE may replace the canonical workspace participant contract with a relevance plan."
        )
    if relevance:
        relevance = validate_standup_relevance_plan(relevance)
        disposition = str(relevance.get("disposition") or "").strip()
        if disposition not in {"run", "decision_record"}:
            raise ValueError(f"A `{disposition or 'missing'}` relevance result cannot be promoted as a standup.")
        expected_participants = (
            effective_feezie_meeting_participants(relevance)
            if disposition == "run"
            else [
                str(item.get("display_name") or "").strip()
                for item in relevance.get("participant_plan") or []
                if isinstance(item, Mapping)
                and str(item.get("display_name") or "").strip()
            ]
        )
        if payload.participants != expected_participants:
            raise ValueError(
                "The coordination participants do not match the exact relevance-selected role contract."
            )
        if disposition == "run" and CANONICAL_MEETING_CLOSER not in expected_participants:
            raise ValueError(
                "A relevance-gated standup requires Jean-Claude as its non-transferable terminal closer."
            )
        if disposition == "decision_record" and len(expected_participants) != 1:
            raise ValueError(
                "A FEEZIE async contribution requires exactly one relevance-selected role."
            )
        allowed_speakers = set(expected_participants)
        unexpected_speakers = sorted(
            {
                str(item.get("speaker") or "").strip()
                for item in payload.discussion_rounds
                if isinstance(item, dict)
                and str(item.get("speaker") or "").strip()
                and str(item.get("speaker") or "").strip() not in allowed_speakers
            }
        )
        if unexpected_speakers:
            raise ValueError("Discussion includes a speaker outside the relevance-gated participant plan.")
        excluded_notes = [
            name
            for name, note in (
                ("Jean-Claude", payload.jean_claude_note),
                ("Neo", payload.neo_note),
                ("Yoda", payload.yoda_note),
            )
            if name not in allowed_speakers and str(note or "").strip()
        ]
        if excluded_notes:
            raise ValueError("Excluded standup participants cannot receive synthesized notes.")
    else:
        expected_participants = standup_participants_for(
            canonical_workspace_key,
            payload.standup_kind,
        )
        if not payload.participants:
            payload = payload.model_copy(update={"participants": expected_participants})
        elif payload.participants != expected_participants:
            raise ValueError("Standup participants do not match the canonical workspace meeting contract.")
        if CANONICAL_MEETING_CLOSER not in expected_participants:
            raise ValueError(
                "A real standup requires Jean-Claude as its non-transferable terminal closer."
            )
        allowed_speakers = set(expected_participants)
        unexpected_speakers = sorted(
            {
                str(item.get("speaker") or "").strip()
                for item in payload.discussion_rounds
                if isinstance(item, dict)
                and str(item.get("speaker") or "").strip()
                and str(item.get("speaker") or "").strip() not in allowed_speakers
            }
        )
        if unexpected_speakers:
            raise ValueError("Discussion includes a speaker outside the canonical workspace meeting contract.")
        excluded_notes = [
            name
            for name, note in (
                ("Jean-Claude", payload.jean_claude_note),
                ("Neo", payload.neo_note),
                ("Yoda", payload.yoda_note),
            )
            if name not in allowed_speakers and str(note or "").strip()
        ]
        if excluded_notes:
            raise ValueError("Roles outside the canonical workspace meeting contract cannot receive synthesized notes.")
    proposed_decisions = list(payload.decisions or [])
    proposed_owners = list(payload.owners or [])
    proposed_pm_updates = list(payload.pm_updates or [])
    discussion = list(payload.discussion_rounds or [])
    if (
        canonical_workspace_key == "feezie-os"
        and str(relevance.get("disposition") or "").strip()
        == "decision_record"
        and discussion
    ):
        raise ValueError(
            "A one-role async contribution cannot supply meeting discussion rounds."
        )
    if not discussion:
        fallback_notes = (
            ("Jean-Claude", "workspace-president", payload.jean_claude_note),
            ("Neo", "system-operator", payload.neo_note),
            ("Yoda", "strategic-overlay", payload.yoda_note),
        )
        for speaker, role, note in fallback_notes:
            if speaker not in allowed_speakers or not str(note or "").strip():
                continue
            discussion.append(
                {
                    "round": len(discussion) + 1,
                    "speaker": speaker,
                    "role": role,
                    "note": note,
                    "provenance": "synthesized_role_lens",
                }
            )

    planned_participants = list(payload.participants)
    meeting_evidence = dict(payload.meeting_evidence or {})
    async_relevance_disposition = bool(
        canonical_workspace_key == "feezie-os"
        and str(relevance.get("disposition") or "").strip()
        == "decision_record"
    )
    if async_relevance_disposition and meeting_evidence:
        raise ValueError(
            "A one-role async contribution cannot claim meeting evidence."
        )
    if meeting_evidence:
        if not str(payload.meeting_id or "").strip():
            raise ValueError("Standup meeting evidence requires an explicit meeting_id.")
        if not str(payload.cycle_id or "").strip():
            raise ValueError("Standup meeting evidence requires an explicit cycle_id.")
        if admitted_meeting_replay is not None:
            admitted_body = dict(admitted_meeting_replay.payload or {})
            meeting_truth = {
                "is_meeting": True,
                "state": str(
                    admitted_body.get("meeting_evidence_state")
                    or "verified_independent_agent_meeting"
                ),
                "reason": str(
                    admitted_body.get("meeting_evidence_reason")
                    or "admitted_immutable_meeting_replay"
                ),
                "canonical_meeting_evidence": dict(
                    admitted_body.get("meeting_evidence") or {}
                ),
                "canonical_discussion": list(
                    admitted_body.get("discussion") or []
                ),
                "canonical_promotion_claims": dict(
                    admitted_body.get("promotion_claims") or {}
                ),
                "canonical_ratification": dict(
                    admitted_body.get("meeting_ratification") or {}
                ),
            }
        else:
            meeting_candidate = {
                "workspace_key": canonical_workspace_key,
                "standup_kind": payload.standup_kind,
                "cycle_id": payload.cycle_id,
                "meeting_id": payload.meeting_id,
                "record_kind": MEETING_RECORD_KIND,
                "meeting_held": True,
                "evaluation_only": False,
                "participants": planned_participants,
                "discussion": discussion,
                "meeting_evidence": meeting_evidence,
            }
            meeting_truth = meeting_record_truth(
                meeting_candidate,
                source=payload.source,
                expected_participants=planned_participants,
                workspace_key=canonical_workspace_key,
                verify_current_identity_pack=True,
                promotion_payload=payload,
            )
            if not meeting_truth["is_meeting"]:
                raise ValueError(
                    "Standup meeting evidence is invalid: "
                    + str(meeting_truth.get("reason") or "unknown")
                )
        record_kind = MEETING_RECORD_KIND
        meeting_held = True
        stored_participants = planned_participants
        role_lens_participants: list[str] = []
        meeting_evidence = dict(meeting_truth["canonical_meeting_evidence"])
        discussion = list(meeting_truth["canonical_discussion"])
        promotion_claims = dict(meeting_truth["canonical_promotion_claims"])
        meeting_ratification = dict(meeting_truth["canonical_ratification"])
        if admitted_meeting_replay is not None:
            admitted_body = dict(admitted_meeting_replay.payload or {})
            recommendations_authorized = bool(
                admitted_body.get("recommendations_authorized")
            )
            owner_decision_routing_required = bool(
                admitted_body.get("owner_decision_routing_required")
            )
        else:
            recommendations_authorized = bool(
                meeting_ratification.get("recommendations_authorized")
            )
            owner_decision_routing_required = bool(
                recommendations_authorized
                and (
                    meeting_ratification.get("owner_decision_routing_required") is True
                    or any(
                        str(item).strip()
                        for item in meeting_ratification.get(
                            "owner_decision_required_by"
                        )
                        or []
                    )
                )
            )
        if owner_decision_routing_required and not proposed_pm_updates:
            # The existing owner-decision bridge binds to one exact signed PM
            # intent.  A prose-only proposal cannot be silently treated as an
            # automatic system decision or transformed into a different card.
            recommendations_authorized = False
            recommendation_authority_state = (
                "withheld_missing_owner_decision_pm_handoff"
            )
        elif admitted_meeting_replay is not None:
            recommendation_authority_state = str(
                admitted_body.get("recommendation_authority_state")
                or "ratified_by_canonical_closer"
            )
        elif not recommendations_authorized:
            recommendation_authority_state = "withheld_by_canonical_closer"
        elif owner_decision_routing_required:
            recommendation_authority_state = "ratified_for_canonical_owner_decision"
        else:
            recommendation_authority_state = "ratified_by_canonical_closer"
    else:
        # Prep-generated dialogue is deterministic planning evidence.  It may
        # still route recommendations through the existing PM authority, but it
        # is not attendance, a transcript, or a completed standup.
        record_kind = WORKSPACE_CYCLE_PLAN_RECORD_KIND
        meeting_held = False
        stored_participants = []
        role_lens_participants = planned_participants
        if async_relevance_disposition:
            raw_async_evidence = (
                payload.recursion.get("async_role_contribution")
                if isinstance(payload.recursion, Mapping)
                else None
            )
            async_role_truth = async_role_contribution_truth(
                raw_async_evidence
                if isinstance(raw_async_evidence, Mapping)
                else None,
                promotion_payload=payload,
                verify_current_identity_pack=True,
            )
            if not async_role_truth.get("valid"):
                raise ValueError(
                    "FEEZIE async role evidence is invalid: "
                    + str(async_role_truth.get("reason") or "unknown")
                )
            if discussion:
                raise ValueError(
                    "A verified async contribution remains evidence, not a meeting transcript."
                )
            canonical_async_evidence = dict(
                async_role_truth.get("canonical_evidence") or {}
            )
            role_lens_participants = [
                str(canonical_async_evidence.get("display_name") or "").strip()
            ]
            meeting_truth = {
                "is_meeting": False,
                "state": str(async_role_truth.get("state") or ""),
                "reason": str(async_role_truth.get("reason") or ""),
            }
        else:
            meeting_truth = {
                "is_meeting": False,
                "state": "synthetic_planning_only",
                "reason": "independent_agent_evidence_missing",
            }
        promotion_claims = {}
        meeting_ratification = {}
        owner_decision_routing_required = False
        meeting_attempt = (
            dict(payload.recursion.get("meeting_attempt") or {})
            if isinstance(payload.recursion, Mapping)
            else {}
        )
        attempted_due_meeting_failed = bool(
            meeting_attempt.get("attempted") is True
            and str(meeting_attempt.get("status") or "").strip()
            != "verified_receipts_submitted"
        )
        # A FEEZIE `run` relevance result means two or more independent role
        # lenses made a real meeting necessary.  The plan is useful evidence,
        # but it cannot acquire Jean-Claude's PM/execution authority merely
        # because no caller recorded a failed meeting attempt.  Only verified
        # signed meeting evidence and the canonical closer may authorize the
        # recommendation handoff.
        verified_meeting_required_by_relevance = bool(
            canonical_workspace_key == "feezie-os"
            and str(relevance.get("disposition") or "").strip() == "run"
        )
        async_report = (
            dict(
                dict(async_role_truth or {}).get("canonical_evidence") or {}
            ).get("report_content")
            if async_role_truth
            else None
        )
        async_report = dict(async_report) if isinstance(async_report, Mapping) else {}
        async_has_pm_handoff = bool(proposed_pm_updates)
        async_no_eligible_change = bool(
            async_relevance_disposition
            and str(async_report.get("position") or "").strip()
            == "no_eligible_change"
        )
        async_recommendation_blocked = bool(
            async_relevance_disposition
            and not async_has_pm_handoff
            and not async_no_eligible_change
        )
        recommendations_authorized = not (
            verified_meeting_required_by_relevance
            or attempted_due_meeting_failed
            or async_recommendation_blocked
        )
        if async_recommendation_blocked:
            recommendation_authority_state = (
                "withheld_missing_async_recommendation_pm_handoff"
            )
        elif async_relevance_disposition:
            recommendation_authority_state = (
                "existing_system_evaluation_authority_after_signed_async_role_input"
            )
        else:
            recommendation_authority_state = (
                "existing_system_evaluation_authority"
                if recommendations_authorized
                else "withheld_pending_verified_due_meeting"
            )

    effective_decisions = proposed_decisions if recommendations_authorized else []
    effective_owners = proposed_owners if recommendations_authorized else []
    effective_pm_updates = proposed_pm_updates if recommendations_authorized else []
    automatic_dispatch_authorized = bool(
        recommendations_authorized and not owner_decision_routing_required
    )
    proposal_audit = {
        "recommendation_authority_state": recommendation_authority_state,
        "recommendations_authorized": recommendations_authorized,
        "automatic_dispatch_authorized": automatic_dispatch_authorized,
        "owner_decision_routing_required": owner_decision_routing_required,
        **(
            {
                "proposed_decisions": proposed_decisions,
                "proposed_owners": proposed_owners,
                "meeting_ratification": meeting_ratification,
            }
            if meeting_held or not recommendations_authorized
            else {}
        ),
    }
    canonical_recursion = dict(payload.recursion or {})
    if async_role_truth:
        canonical_async_evidence = dict(
            async_role_truth.get("canonical_evidence") or {}
        )
        async_report_content = dict(
            canonical_async_evidence.get("report_content") or {}
        )
        canonical_recursion["async_role_contribution"] = canonical_async_evidence
        canonical_recursion["evaluated"] = True
        async_actions = [
            item
            for item in canonical_recursion.get("actions_taken") or []
            if isinstance(item, Mapping)
        ]
        async_actions.append(
            {
                "kind": "verified_async_role_contribution",
                "summary": (
                    f"{canonical_async_evidence.get('display_name')} contributed one independently "
                    "signed FEEZIE role lens; no meeting was held."
                ),
                "contribution_id": canonical_async_evidence.get("contribution_id"),
                "participant_report_run_id": canonical_async_evidence.get(
                    "participant_report_run_id"
                ),
                "canonical_pm_execution_authority": CANONICAL_MEETING_CLOSER,
                "pm_execution_authority_transferred": False,
            }
        )
        canonical_recursion["actions_taken"] = async_actions
        async_system_decisions = [
            item
            for item in canonical_recursion.get("system_decisions") or []
            if isinstance(item, Mapping)
        ]
        async_system_decisions.append(
            {
                "kind": "admit_signed_async_role_input",
                "summary": (
                    "Admit the signed role input to the existing system evaluation and PM gates "
                    "without transferring Jean-Claude's authority."
                ),
                "contribution_id": canonical_async_evidence.get("contribution_id"),
                "authority": "existing_system_evaluation_authority",
            }
        )
        canonical_recursion["system_decisions"] = async_system_decisions
        if proposed_pm_updates:
            async_handoff = {
                "state": "pending_existing_pm_resolution",
                "recommendation_count": len(proposed_pm_updates),
                "dependency": "existing_pm_recommendation_authority",
            }
        elif str(async_report_content.get("position") or "") == "no_eligible_change":
            async_handoff = {
                "state": "intentionally_retained",
                "future_trigger": str(
                    async_report_content.get("recommended_next_step") or ""
                )[:700],
            }
        else:
            async_handoff = {
                "state": "blocked",
                "dependency": (
                    "A bounded existing PM recommendation request is required before the role's "
                    "proposed next step can enter execution or owner-decision routing."
                ),
                "future_trigger": (
                    "A later FEEZIE evaluation supplies an authorized bounded PM handoff."
                ),
            }
        canonical_recursion["async_role_recommendation_handoff"] = async_handoff
        async_next_cycle_inputs = [
            item
            for item in canonical_recursion.get("next_cycle_inputs") or []
            if isinstance(item, Mapping)
        ]
        async_next_cycle_inputs.append(
            {
                "kind": "verified_async_role_contribution",
                "summary": (
                    "Consume the signed FEEZIE async role contribution and its terminal "
                    "recommendation disposition in the next Dream/standup cycle."
                ),
                "contribution_id": canonical_async_evidence.get("contribution_id"),
                "participant_report_run_id": canonical_async_evidence.get(
                    "participant_report_run_id"
                ),
            }
        )
        canonical_recursion["next_cycle_inputs"] = async_next_cycle_inputs
        if async_handoff["state"] == "blocked":
            async_blocked = [
                item
                for item in canonical_recursion.get("blocked") or []
                if isinstance(item, Mapping)
            ]
            async_blocked.append(
                {
                    "kind": "async_role_recommendation_handoff_blocked",
                    "summary": async_handoff["dependency"],
                    "future_trigger": async_handoff["future_trigger"],
                    "contribution_id": canonical_async_evidence.get(
                        "contribution_id"
                    ),
                }
            )
            canonical_recursion["blocked"] = async_blocked
        elif async_handoff["state"] == "intentionally_retained":
            async_no_action = [
                item
                for item in canonical_recursion.get("no_action") or []
                if isinstance(item, Mapping)
            ]
            async_no_action.append(
                {
                    "reason": (
                        "The independently selected role found no eligible changed action."
                    ),
                    "future_trigger": async_handoff["future_trigger"],
                    "selected": True,
                }
            )
            canonical_recursion["no_action"] = async_no_action
    raw_meeting_attempt = canonical_recursion.get("meeting_attempt")
    if isinstance(raw_meeting_attempt, Mapping):
        canonical_recursion["meeting_attempt"] = {
            **dict(raw_meeting_attempt),
            # This is derived from the canonical closer/server handoff above.
            # A caller-supplied nested value cannot contradict the terminal
            # authority that governs decision and PM dispatch.
            "recommendations_authorized": recommendations_authorized,
            "recommendation_authority_state": recommendation_authority_state,
            "automatic_dispatch_authorized": automatic_dispatch_authorized,
            "owner_decision_routing_required": owner_decision_routing_required,
        }

    proposed_recommendation_requests = [
        _canonical_recommendation_request(update) for update in proposed_pm_updates
    ]
    recommendation_requests = [
        _canonical_recommendation_request(update) for update in effective_pm_updates
    ]
    standup_create = StandupCreate(
        owner=payload.owner,
        workspace_key=payload.workspace_key,
        status="completed",
        blockers=payload.blockers,
        commitments=payload.commitments,
        needs=payload.needs,
        source=payload.source,
        conversation_path=payload.conversation_path,
        payload={
            "standup_kind": payload.standup_kind,
            "summary": payload.summary,
            "agenda": payload.agenda,
            "decisions": effective_decisions,
            "owners": effective_owners,
            **proposal_audit,
            "artifact_deltas": payload.artifact_deltas,
            "audience_response": payload.audience_response,
            "standup_sections": payload.standup_sections,
            "pm_snapshot": payload.pm_snapshot,
            "strategy_context": dict(payload.strategy_context or {}),
            "workspace_key": canonical_workspace_key,
            "record_kind": record_kind,
            "meeting_held": meeting_held,
            "evaluation_only": not meeting_held,
            "meeting_evidence_state": meeting_truth["state"],
            "meeting_evidence_reason": meeting_truth["reason"],
            "meeting_evidence": meeting_evidence if meeting_held else {},
            "promotion_claims": promotion_claims if meeting_held else {},
            "participants": stored_participants,
            "planned_participants": role_lens_participants,
            "standup_relevance": relevance,
            "source_paths": payload.source_paths,
            "memory_promotions": payload.memory_promotions,
            "discussion": discussion,
            "prep_id": payload.prep_id,
            "cycle_id": payload.cycle_id,
            "meeting_id": payload.meeting_id,
            "prior_standup": dict(payload.prior_standup or {}),
            "continuity": dict(payload.continuity or {}),
            "recursion": canonical_recursion,
            "recommendation_path": payload.recommendation_path,
            "pm_recommendation_count": len(effective_pm_updates),
            "recommendation_requests": recommendation_requests,
            **(
                {
                    "proposed_pm_recommendation_count": len(proposed_pm_updates),
                    "proposed_recommendation_requests": proposed_recommendation_requests,
                }
                if meeting_held or not recommendations_authorized
                else {}
            ),
        },
    )
    semantic_payload_sha256 = _standup_semantic_payload_sha256(standup_create)
    standup_create = standup_create.model_copy(
        update={
            "payload": {
                **standup_create.payload,
                "semantic_payload_sha256": semantic_payload_sha256,
            }
        }
    )
    deterministic_id = _completed_cycle_standup_id(standup_create)
    persisted_resolutions: dict[int, dict[str, Any]] = {}
    if deterministic_id:
        existing_cycle_standup = get_standup(deterministic_id)
        existing_payload = (
            dict(existing_cycle_standup.payload or {})
            if existing_cycle_standup is not None
            else {}
        )
        if existing_cycle_standup is not None:
            existing_semantic_sha256 = _standup_semantic_payload_sha256(existing_cycle_standup)
            stored_claim = str(existing_payload.get("semantic_payload_sha256") or "").strip()
            if (
                stored_claim and stored_claim != existing_semantic_sha256
            ) or existing_semantic_sha256 != semantic_payload_sha256:
                raise ValueError("standup cycle semantic conflict")
            persisted_resolutions = _matching_persisted_resolutions(
                recommendation_requests,
                existing_payload.get("recommendation_resolutions"),
            )
        if existing_cycle_standup is not None and len(persisted_resolutions) == len(recommendation_requests):
            return StandupPromotionResult(
                standup=existing_cycle_standup,
                created_cards=[],
                existing_cards=[],
            )
    standup = (
        create_standup(standup_create, _governed_meeting_write=True)
        if meeting_held
        else create_standup(standup_create, _governed_plan_write=True)
    )

    created_cards: List[PMCard] = []
    existing_cards: List[PMCard] = []
    resolved_updates: list[tuple[int, object, PMCard, bool]] = []
    source_signature = f"standup-prep:{payload.prep_id}" if payload.prep_id else f"standup:{standup.id}"
    coordination_link_type = "standup" if meeting_held else WORKSPACE_CYCLE_PLAN_RECORD_KIND

    for update_index, update in enumerate(effective_pm_updates):
        if update_index in persisted_resolutions:
            continue
        execution_defaults = pm_card_service.execution_defaults_for_workspace(update.workspace_key or payload.workspace_key)
        card_payload = dict(update.payload or {})
        # No existing scheduler authority writes this PM field. Treat it as an
        # untrusted logical reference and keep it out of newly promoted cards.
        card_payload.pop("scheduler_receipt", None)
        contract = build_execution_contract(
            title=update.title,
            workspace_key=update.workspace_key or payload.workspace_key,
            source="standup_promotion",
            reason=update.reason,
            instructions=card_payload.get("instructions") if isinstance(card_payload.get("instructions"), list) else None,
            acceptance_criteria=(
                card_payload.get("acceptance_criteria") if isinstance(card_payload.get("acceptance_criteria"), list) else None
            ),
            artifacts_expected=(
                card_payload.get("artifacts_expected") if isinstance(card_payload.get("artifacts_expected"), list) else None
            ),
        )
        transition_at = datetime.now(timezone.utc).isoformat()
        card_payload.update(
            {
                "workspace_key": update.workspace_key or payload.workspace_key,
                "scope": update.scope,
                "source_agent": update.owner_agent,
                "created_from_coordination_record_id": standup.id,
                "created_from_coordination_record_kind": record_kind,
                "created_from_coordination_kind": payload.standup_kind,
                "created_from_coordination_workspace": payload.workspace_key,
                "participants": stored_participants,
                "planned_role_lenses": role_lens_participants,
                "reason": update.reason,
                "execution": {
                    "lane": "codex",
                    "state": "queued",
                    "manager_agent": execution_defaults["manager_agent"],
                    "target_agent": execution_defaults["target_agent"],
                    "workspace_agent": execution_defaults.get("workspace_agent"),
                    "execution_mode": execution_defaults["execution_mode"],
                    "requested_by": payload.owner,
                    "assigned_runner": "codex",
                    "reason": update.reason,
                    "queued_at": transition_at,
                    "last_transition_at": transition_at,
                    "source": "standup_promotion",
                },
                **contract,
            }
        )
        if meeting_held and owner_decision_routing_required:
            request_sha256 = _recommendation_request_sha256(
                recommendation_requests[update_index]
            )
            required_by = [
                str(item).strip()
                for item in meeting_ratification.get(
                    "owner_decision_required_by"
                )
                or []
                if str(item).strip()
            ]
            # This is an input to the existing execution gate, not a second
            # decision authority.  Its deterministic identity makes replay
            # converge on the same PM intent and canonical owner decision.
            card_payload["owner_review"] = {
                "queue_id": (
                    f"standup-resolution:{standup.id}:"
                    f"{request_sha256[:24]}"
                ),
                "sync_state": "pending_owner_review",
                "source": "signed_standup_resolution",
                "standup_id": standup.id,
                "meeting_id": str(payload.meeting_id or ""),
                "closing_report_run_id": str(
                    meeting_ratification.get("closing_report_run_id") or ""
                ),
                "required_by": required_by,
            }
        if meeting_held:
            card_payload.update(
                {
                    "created_from_standup_id": standup.id,
                    "created_from_standup_kind": payload.standup_kind,
                    "created_from_standup_workspace": payload.workspace_key,
                }
            )
        existing = _resolve_existing_card_for_update(update, source_signature=source_signature, default_workspace_key=payload.workspace_key)
        if existing:
            existing_payload = dict(existing.payload or {})
            should_carry_forward = bool(
                owner_decision_routing_required
                or card_payload.get("pm_card_id")
                or card_payload.get("carry_forward_required")
                or existing.link_type in {"standup", WORKSPACE_CYCLE_PLAN_RECORD_KIND}
                or existing_payload.get("created_from_standup_id")
                or existing_payload.get("created_from_coordination_record_id")
            )
            if should_carry_forward:
                existing = _apply_standup_carry_forward(
                    existing,
                    standup=standup,
                    update=update,
                    card_payload=card_payload,
                )
            existing_cards.append(existing)
            resolved_updates.append((update_index, update, existing, False))
            continue
        request_sha256 = _recommendation_request_sha256(
            recommendation_requests[update_index]
        )
        card, created_now = pm_card_service.get_or_create_recommendation_card(
            PMCardCreate(
                title=update.title,
                owner=_display_agent_name(update.owner_agent),
                status=update.status or "todo",
                source=source_signature,
                link_type=coordination_link_type,
                link_id=standup.id,
                payload=card_payload,
            ),
            coordination_record_id=standup.id,
            request_sha256=request_sha256,
        )
        if created_now:
            created_cards.append(card)
        else:
            existing_cards.append(card)
        resolved_updates.append((update_index, update, card, created_now))

    recommendation_resolutions_by_index = dict(persisted_resolutions)
    for update_index, update, card, created_now in resolved_updates:
        recommendation_resolutions_by_index[update_index] = {
            **_recommendation_resolution(update, card, created=created_now),
            "request_sha256": _recommendation_request_sha256(recommendation_requests[update_index]),
        }
    recommendation_resolutions = [
        recommendation_resolutions_by_index[index]
        for index in range(len(recommendation_requests))
        if index in recommendation_resolutions_by_index
    ]
    standup = _merge_promotion_recommendation_resolutions(
        standup.id,
        recommendation_requests=recommendation_requests,
        proposed_resolutions=recommendation_resolutions,
    )

    return StandupPromotionResult(standup=standup, created_cards=created_cards, existing_cards=existing_cards)


def _merge_promotion_recommendation_resolutions(
    standup_id: str,
    *,
    recommendation_requests: list[dict[str, Any]],
    proposed_resolutions: list[dict[str, Any]],
) -> StandupEntry:
    """Serialize exact recommendation receipts onto their coordination record.

    PM-card creation is independently atomic. This row lock closes the other
    half of the handoff: concurrent promotions merge the same request digests
    against current persisted truth instead of replacing one another's payload.
    """

    proposed_by_index = _matching_persisted_resolutions(
        recommendation_requests,
        proposed_resolutions,
    )
    pool = get_pool()
    with pool.connection() as conn:
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, owner, workspace_key, status, blockers, commitments,
                           needs, source, conversation_path, payload, created_at
                    FROM standups
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (standup_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        "The coordination record disappeared before recommendation resolution."
                    )
                current = _persisted_standup_from_row(row)
                current_payload = dict(current.payload or {})
                if str(current.status or "").strip().lower() != "completed":
                    raise ValueError(
                        "Recommendation resolutions require a completed coordination record."
                    )
                if _claims_real_meeting(current_payload):
                    if (
                        current_payload.get("record_kind") != MEETING_RECORD_KIND
                        or current_payload.get("meeting_held") is not True
                        or current_payload.get("evaluation_only") is not False
                        or not isinstance(current_payload.get("meeting_evidence"), Mapping)
                        or not current_payload.get("meeting_evidence")
                        or not isinstance(current_payload.get("promotion_claims"), Mapping)
                        or not current_payload.get("promotion_claims")
                    ):
                        raise ValueError(
                            "Recommendation resolutions require a canonical governed meeting."
                        )
                elif _claims_workspace_cycle_plan(current_payload):
                    _require_canonical_workspace_cycle_plan(
                        current_payload,
                        allow_recommendation_resolutions=True,
                    )
                else:
                    raise ValueError(
                        "Recommendation resolutions require a governed coordination record."
                    )
                stored_claim = str(
                    current_payload.get("semantic_payload_sha256") or ""
                ).strip()
                current_semantic_sha256 = _standup_semantic_payload_sha256(current)
                if not stored_claim or stored_claim != current_semantic_sha256:
                    raise ValueError(
                        "standup cycle semantic payload changed before recommendation resolution"
                    )
                stored_requests = _canonical_stored_recommendation_requests(
                    current_payload.get("recommendation_requests")
                )
                if stored_requests != recommendation_requests:
                    raise pm_card_service.PMRecommendationIdentityConflict(
                        "Recommendation resolution requests do not match the coordination record."
                    )
                persisted_by_index = _matching_persisted_resolutions(
                    recommendation_requests,
                    current_payload.get("recommendation_resolutions"),
                )
                merged_resolutions: list[dict[str, Any]] = []
                for index, _request in enumerate(recommendation_requests):
                    persisted = persisted_by_index.get(index)
                    proposed = proposed_by_index.get(index)
                    if persisted is not None and proposed is not None:
                        persisted_card_id = str(persisted.get("card_id") or "").strip()
                        proposed_card_id = str(proposed.get("card_id") or "").strip()
                        if persisted_card_id != proposed_card_id:
                            raise pm_card_service.PMRecommendationIdentityConflict(
                                "One coordination recommendation resolved to multiple PM cards."
                            )
                        selected = dict(persisted)
                        selected["created_this_cycle"] = bool(
                            persisted.get("created_this_cycle")
                            or proposed.get("created_this_cycle")
                        )
                    elif persisted is not None:
                        selected = dict(persisted)
                    elif proposed is not None:
                        selected = dict(proposed)
                    else:
                        continue
                    selected["title"] = str(_request.get("title") or "")[:300]
                    selected["workspace_key"] = str(
                        _request.get("workspace_key") or "shared_ops"
                    )[:64]
                    selected["request_sha256"] = _recommendation_request_sha256(
                        _request
                    )
                    merged_resolutions.append(selected)

                if len(merged_resolutions) != len(recommendation_requests):
                    raise pm_card_service.PMRecommendationIdentityConflict(
                        "Every coordination recommendation must have one canonical PM resolution."
                    )

                _require_resolution_card_bindings(
                    cur,
                    standup_id=standup_id,
                    recommendation_requests=recommendation_requests,
                    resolutions=merged_resolutions,
                )

                final_payload = dict(current_payload)
                final_payload["pm_updates"] = [
                    {
                        "title": item["title"],
                        "workspace_key": item["workspace_key"],
                        "card_id": item["card_id"],
                        "resolution_state": item["state"],
                    }
                    for item in merged_resolutions
                ]
                final_payload["recommendation_resolutions"] = merged_resolutions
                recursion = (
                    dict(final_payload.get("recursion") or {})
                    if isinstance(final_payload.get("recursion"), Mapping)
                    else {}
                )
                recursion["recommendation_resolutions"] = merged_resolutions
                async_handoff = (
                    dict(recursion.get("async_role_recommendation_handoff") or {})
                    if isinstance(
                        recursion.get("async_role_recommendation_handoff"),
                        Mapping,
                    )
                    else {}
                )
                if async_handoff.get("state") == "pending_existing_pm_resolution":
                    resolved_async_handoff = {
                        "state": "resolved_through_existing_pm_authority",
                        "recommendation_count": len(merged_resolutions),
                        "terminal_dispositions": [
                            {
                                "request_sha256": item["request_sha256"],
                                "card_id": item["card_id"],
                                "state": item["state"],
                            }
                            for item in merged_resolutions
                        ],
                    }
                    recursion["async_role_recommendation_handoff"] = (
                        resolved_async_handoff
                    )
                    next_cycle_inputs = [
                        item
                        for item in recursion.get("next_cycle_inputs") or []
                        if isinstance(item, Mapping)
                    ]
                    next_cycle_inputs.append(
                        {
                            "kind": "async_role_recommendation_outcomes",
                            "summary": (
                                "Consume the terminal PM dispositions produced from the signed "
                                "async role input."
                            ),
                            "terminal_dispositions": list(
                                resolved_async_handoff["terminal_dispositions"]
                            ),
                        }
                    )
                    recursion["next_cycle_inputs"] = next_cycle_inputs
                final_payload["recursion"] = recursion
                cur.execute(
                    """
                    UPDATE standups
                    SET payload = %s,
                        updated_at = NOW(),
                        retention_contract_version = NULL,
                        retention_resolved_at = NULL,
                        retention_local_receipt_sha256 = NULL
                    WHERE id = %s
                      AND retention_contract_version IS DISTINCT FROM
                          'railway_retained_standup_receipt/v1'
                    RETURNING id, owner, workspace_key, status, blockers,
                              commitments, needs, source, conversation_path,
                              payload, created_at
                    """,
                    (Json(final_payload), standup_id),
                )
                updated_row = cur.fetchone()
                if updated_row is None:
                    raise ValueError(
                        "A retained coordination receipt cannot be rewritten during recommendation resolution."
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return _row_to_entry(updated_row)


def _recommendation_resolution(update, card: PMCard, *, created: bool) -> dict[str, object]:
    """Resolve one promoted recommendation to exactly one existing lifecycle state."""

    payload = dict(card.payload or {})
    execution = dict(payload.get("execution") or {})
    gate = dict(payload.get("execution_gate") or {})
    result = dict(payload.get("latest_execution_result") or {})
    status = str(card.status or "").strip().lower()
    execution_state = str(execution.get("state") or execution.get("executor_status") or "").strip().lower()
    result_status = str(result.get("status") or "").strip().lower()
    gate_decision = str(gate.get("decision") or "").strip().upper()
    approval_state = str(gate.get("approval_state") or "").strip().lower()
    risk_factors = {
        str(item).strip().upper()
        for item in gate.get("risk_factors") or []
        if str(item).strip()
    }
    completed_states = {"done", "completed", "complete", "success", "succeeded", "closed"}
    verified_completion = bool(
        result_status in completed_states
        and pm_card_service.has_canonical_execution_result_commit(card)
    )
    workspace_key = str(
        getattr(update, "workspace_key", None)
        or payload.get("workspace_key")
        or "shared_ops"
    )
    try:
        gate_current = execution_gate_matches_current(
            card_id=card.id,
            title=card.title,
            source=card.source,
            workspace_key=workspace_key,
            payload=payload,
        )
    except Exception:
        gate_current = False
    try:
        signed_authorization_current = verify_execution_payload(card.id, payload)
    except Exception:
        signed_authorization_current = False
    safe_auto_gate = bool(
        gate_current
        and signed_authorization_current
        and gate_decision == AUTO_EXECUTE
        and approval_state == "not_required"
        and gate.get("risk_class") == "safe_internal_reversible"
        and gate.get("capability_id") == BOUNDED_PROJECT_CAPABILITY
        and gate.get("runner_profile") == "codex_workspace"
        and not risk_factors
    )
    scheduler_authority_state = "not_claimed"
    if execution_state == "scheduled":
        scheduler_authority_state = (
            "untrusted_pm_payload_reference"
            if isinstance(payload.get("scheduler_receipt"), Mapping)
            else "missing_future_dispatch_authority"
        )
    try:
        queue_entry = pm_card_service.build_execution_queue_entry(card)
    except Exception:
        queue_entry = None
    claimable_execution = bool(
        safe_auto_gate
        and queue_entry is not None
        and queue_entry.execution_gate_authorization_current
        and str(queue_entry.execution_gate_decision or "").strip().upper() == AUTO_EXECUTE
        and not queue_entry.manager_attention_required
        and str(queue_entry.execution_state or "").strip().lower()
        in {"queued", "pending", "claimed", "running", "in_progress"}
    )

    owner_decision_resolution = (
        dict(payload.get("owner_decision_resolution") or {})
        if isinstance(payload.get("owner_decision_resolution"), dict)
        else {}
    )
    owner_choice = str(owner_decision_resolution.get("choice") or "").strip()
    owner_receipt_current = bool(
        owner_decision_resolution.get("schema_version")
        == "pm_owner_decision_resolution/v1"
        and str(owner_decision_resolution.get("decision_id") or "").strip()
        and owner_choice
        in {
            "approve_bounded_internal_action",
            "reject_recommendation",
            "retain_until_trigger",
        }
        and str(owner_decision_resolution.get("bound_execution_gate_intent_hash") or "")
        == str(gate.get("intent_hash") or "")
        and gate_current
        and signed_authorization_current
    )
    owner_approved_claimable_execution = bool(
        owner_receipt_current
        and owner_choice == "approve_bounded_internal_action"
        and gate_decision == REQUIRE_APPROVAL
        and approval_state == "approved"
        and queue_entry is not None
        and queue_entry.execution_gate_authorization_current
        and str(queue_entry.execution_gate_decision or "").strip().upper()
        == REQUIRE_APPROVAL
        and str(queue_entry.execution_gate_approval_state or "").strip().lower()
        == "approved"
        and not queue_entry.manager_attention_required
        and str(queue_entry.execution_state or "").strip().lower()
        in {"queued", "pending", "claimed", "running", "in_progress"}
    )
    owner_decision_status: str | None = None

    if owner_choice == "retain_until_trigger" and owner_receipt_current:
        state = "intentionally_retained"
        owner_decision_status = "resolved_retained"
        explanation = (
            "The owner explicitly retained this recommendation until its durable future trigger occurs; "
            "the linked PM lane remains non-runnable."
        )
        future_trigger = str(
            owner_decision_resolution.get("future_trigger")
            or "New eligible evidence changes this recommendation or its authorization boundary."
        )[:1000]
    elif owner_approved_claimable_execution:
        state = "placed_in_execution_queue"
        owner_decision_status = "resolved_approved_and_queued"
        explanation = (
            "The exact bounded internal PM intent has a durable owner decision receipt and remains in the "
            "existing governed execution lifecycle."
        )
        future_trigger = "The current executor writes a completion, failure, or blocker receipt."
    elif owner_choice == "reject_recommendation" and owner_receipt_current:
        state = "bounded_owner_decision"
        owner_decision_status = "resolved_rejected"
        explanation = (
            "The canonical owner decision explicitly rejected this recommendation, and the linked PM lane "
            "is truthfully cancelled rather than represented as completed work or a system-policy outcome."
        )
        future_trigger = None
    elif owner_choice in {
        "approve_bounded_internal_action",
        "reject_recommendation",
        "retain_until_trigger",
    }:
        state = "bounded_owner_decision"
        owner_decision_status = "resolved_choice_not_reconciled"
        explanation = (
            "A canonical owner choice is present, but its linked PM receipt, signed execution gate, or exact "
            "queue proof is not current. The recommendation is not represented as executed, queued, rejected, "
            "or retained until reconciliation succeeds."
        )
        future_trigger = "The exact signed PM reconciliation succeeds without overwriting newer truth."
    elif (
        status in {"blocked", "failed", "error"}
        or execution_state in {"blocked", "failed", "error"}
        or result_status in {"blocked", "failed", "error"}
    ):
        state = "blocked"
        explanation = "The existing execution failed and remains visible for bounded retry or manager attention."
        future_trigger = "A governed retry or an evidenced blocker resolution."
    elif gate_decision == REQUIRE_APPROVAL and risk_factors.intersection(
        NON_OVERRIDABLE_RISK_FACTORS
    ):
        state = "rejected_by_policy"
        explanation = str(
            gate.get("reason")
            or "The existing execution policy rejects this malformed, unknown, or unsafe execution intent."
        )[:500]
        future_trigger = "The recommendation is replaced by a bounded intent that passes the existing execution policy."
    elif gate_decision == REQUIRE_APPROVAL:
        state = "bounded_owner_decision"
        if status in completed_states or verified_completion:
            explanation = (
                "A completion receipt is present, but this recommendation remains classified by its owner-only "
                "execution gate and is not represented as automatic system work."
            )
            future_trigger = None
        elif approval_state == "approved":
            explanation = "Explicit owner approval is recorded; the owner-governed lane still awaits its outcome receipt."
            future_trigger = "The approved lane records a completion, failure, or blocker receipt."
        else:
            explanation = str(
                gate.get("reason") or "The current execution gate requires explicit owner approval."
            )[:500]
            future_trigger = "The owner records an explicit canonical decision or approval."
    elif execution_state == "scheduled" and safe_auto_gate:
        state = "intentionally_retained"
        explanation = (
            "The PM card claims a scheduled state, but the existing registered-task and append-only run-ledger "
            "authorities do not prove an exact future dispatch bound to this card, workspace, and signed intent. "
            "It is retained without claiming scheduler progress."
        )
        future_trigger = (
            "The recommendation re-enters the existing governed PM execution queue, or an existing governed "
            "scheduler authority records an exact future card/workspace/signed-intent binding."
        )
    elif verified_completion and safe_auto_gate:
        state = "executed_automatically"
        explanation = (
            "A complete purpose-signed canonical PM result-commit receipt closes work governed by a current "
            "signed safe, internal, reversible AUTO_EXECUTE gate."
        )
        future_trigger = None
    elif claimable_execution:
        state = "placed_in_execution_queue"
        explanation = (
            "The recommendation is claimable in the existing governed PM execution lifecycle under a "
            "current signed safe-internal AUTO_EXECUTE gate."
        )
        future_trigger = "The current executor writes a completion, failure, or blocker receipt."
    elif status in completed_states or result_status in completed_states:
        state = "intentionally_retained"
        explanation = (
            "The PM record looks closed, but it lacks either a verified result identity or the current signed "
            "safe AUTO_EXECUTE gate required to call the work automatic."
        )
        future_trigger = "A verified outcome receipt and current execution authorization establish the completion truth."
    else:
        state = "intentionally_retained"
        explanation = "The existing PM lane remains the sole bounded follow-through path."
        future_trigger = "The PM lane changes state or receives new verified evidence."

    resolution = {
        "recommendation_id": f"pm:{card.id}",
        "title": str(update.title or card.title)[:300],
        "workspace_key": str(update.workspace_key or "shared_ops")[:64],
        "card_id": card.id,
        "state": state,
        "created_this_cycle": created,
        "explanation": explanation,
        "future_trigger": future_trigger,
    }
    if state == "bounded_owner_decision":
        resolution["pm_execution_gate_intent_hash"] = str(gate.get("intent_hash") or "")[:100]
        resolution["pm_card_updated_at"] = card.updated_at.astimezone(timezone.utc).isoformat()
    if owner_decision_status:
        resolution["owner_decision_status"] = owner_decision_status
    if execution_state == "scheduled":
        resolution["scheduler_authority_state"] = scheduler_authority_state
    return resolution


def _resolve_existing_card_for_update(
    update,
    *,
    source_signature: str,
    default_workspace_key: str,
) -> PMCard | None:
    update_payload = dict(update.payload or {})
    explicit_card_id = (
        str(update_payload.get("pm_card_id") or update_payload.get("carry_forward_card_id") or "").strip()
    )
    if explicit_card_id:
        existing = pm_card_service.get_card(explicit_card_id)
        if existing is not None and not _is_closed_pm_status(existing.status):
            return existing
    trigger_key = str(update_payload.get("trigger_key") or "").strip()
    if trigger_key:
        existing = pm_card_service.find_active_card_by_trigger_key(trigger_key)
        if existing is not None:
            return existing
    existing = pm_card_service.find_card_by_signature(update.title, source_signature)
    if existing is None:
        existing = pm_card_service.find_active_card_by_title(update.title, update.workspace_key or default_workspace_key)
    return existing


def _apply_standup_carry_forward(
    existing: PMCard,
    *,
    standup: StandupEntry,
    update,
    card_payload: dict[str, object],
) -> PMCard:
    update_payload = dict(update.payload or {})
    action = str(update_payload.get("carry_forward_action") or "").strip().lower()
    existing_payload = dict(existing.payload or {})
    carry_forward_ids = _dedupe_strings(
        [
            *(
                item
                for item in existing_payload.get("carry_forward_standup_ids") or []
                if isinstance(item, str) and item.strip()
            ),
            standup.id,
        ]
    )
    now = datetime.now(timezone.utc).isoformat()
    history = list(existing_payload.get("carry_forward_history") or [])
    history.append(
        {
            "standup_id": standup.id,
            "standup_kind": existing_payload.get("created_from_standup_kind") or standup.payload.get("standup_kind"),
            "workspace_key": standup.workspace_key,
            "at": now,
            "action": action or "reuse_existing_lane",
            "title": update.title,
            "previous_title": existing.title,
        }
    )

    updated_payload = dict(existing_payload)
    if action == "refresh_existing_lane":
        refreshed_payload = dict(card_payload)
        for key in ("created_from_standup_id", "created_from_standup_kind", "created_from_standup_workspace"):
            if existing_payload.get(key):
                refreshed_payload[key] = existing_payload.get(key)
        updated_payload = {
            **existing_payload,
            **refreshed_payload,
        }
        updated_payload["latest_carry_forward_replacement_title"] = update.title
    meeting_owner_review = card_payload.get("owner_review")
    if (
        isinstance(meeting_owner_review, Mapping)
        and str(meeting_owner_review.get("source") or "").strip()
        == "signed_standup_resolution"
    ):
        # A newly signed meeting owner gate supersedes any older card-local
        # review marker even when this cycle reuses the existing PM lane.
        updated_payload["owner_review"] = dict(meeting_owner_review)
    if update_payload.get("recommendation_path"):
        updated_payload["recommendation_path"] = update_payload.get("recommendation_path")
    if update_payload.get("created_from_prep_id"):
        updated_payload["latest_carry_forward_prep_id"] = update_payload.get("created_from_prep_id")
    if update_payload.get("carry_forward_required") is not None:
        updated_payload["carry_forward_required"] = bool(update_payload.get("carry_forward_required"))
    if update_payload.get("carry_forward_resolution_rule"):
        updated_payload["carry_forward_resolution_rule"] = update_payload.get("carry_forward_resolution_rule")
    if update_payload.get("carry_forward_summary"):
        updated_payload["carry_forward_summary"] = update_payload.get("carry_forward_summary")
    updated_payload.pop("scheduler_receipt", None)
    updated_payload["carry_forward_standup_ids"] = carry_forward_ids
    updated_payload["latest_carry_forward_standup_id"] = standup.id
    updated_payload["carry_forward_history"] = history[-8:]

    retained_trigger_evidence = (
        dict(updated_payload.get("retained_trigger_evidence") or {})
        if isinstance(updated_payload.get("retained_trigger_evidence"), dict)
        else {}
    )
    if (
        action == "refresh_existing_lane"
        and retained_trigger_evidence.get("schema_version")
        == "pm_retained_trigger_evidence/v1"
    ):
        refreshed, _disposition = (
            pm_card_service.refresh_retained_pm_owner_decision_lane(
                existing.id,
                expected_card_updated_at=existing.updated_at,
                expected_decision_id=str(
                    retained_trigger_evidence.get("prior_decision_id") or ""
                ),
                expected_execution_gate_intent_hash=str(
                    retained_trigger_evidence.get(
                        "prior_execution_gate_intent_hash"
                    )
                    or ""
                ),
                title=update.title,
                proposed_payload=updated_payload,
            )
        )
        return refreshed

    updated = pm_card_service.update_card(
        existing.id,
        PMCardUpdate(
            title=update.title if action == "refresh_existing_lane" else None,
            status="todo" if action == "refresh_existing_lane" else None,
            payload=updated_payload,
        ),
    )
    if updated is not None:
        return updated
    current = pm_card_service.get_card(existing.id)
    if current is None:
        raise ValueError(
            "The carried-forward PM lane disappeared during concurrent reconciliation."
        )
    return current


def _dedupe_strings(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _is_closed_pm_status(status: str | None) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {"done", "closed", "cancelled", "canceled"}


def _row_to_entry(row: dict) -> StandupEntry:
    if not row:
        raise ValueError("Standup row is empty")
    return StandupEntry(
        id=str(row["id"]),
        owner=row.get("owner") or "unknown",
        workspace_key=row.get("workspace_key") or "shared_ops",
        status=row.get("status"),
        blockers=row.get("blockers") or [],
        commitments=row.get("commitments") or [],
        needs=row.get("needs") or [],
        source=row.get("source"),
        conversation_path=row.get("conversation_path"),
        payload=row.get("payload") or {},
        created_at=row.get("created_at"),
    )


def _display_agent_name(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "jean-claude":
        return "Jean-Claude"
    if normalized == "neo":
        return "Neo"
    if normalized == "yoda":
        return "Yoda"
    return value
