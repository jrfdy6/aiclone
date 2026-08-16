from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.feezie_positioning_contract_service import load_feezie_strategy_contract


PORTFOLIO_LEARNING_SCHEMA = "feezie_portfolio_learning_receipt/v1"
PERFORMANCE_SUMMARY_SCHEMA = "linkedin_publication_summary/v1"
CANONICAL_WORKSPACE_KEY = "feezie-os"

PILLAR_IDS = ("ai_native", "leadership_operator", "trust_systems")
INTENT_IDS = ("value", "invitation", "personal")
PILOT_TREATMENTS = (
    "practical_ai_systems",
    "education_or_trust",
    "operator_story_personal_technology",
    "operator_story_education_community",
)
QUALITY_FLAGS = ("too_generic", "too_safe", "too_exposed", "wrong_audience")
VOICE_VALUES = ("yes", "mixed", "no")
FOLLOW_UP_VALUES = ("reuse", "iterate", "retire", "none")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _safe_number(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    return round(float(value), 4)


def _named_counts(value: Any, *, allowed: tuple[str, ...]) -> dict[str, int]:
    source = value if isinstance(value, Mapping) else {}
    return {name: _safe_nonnegative_int(source.get(name)) for name in allowed}


def _mix_receipt(value: Any, *, allowed: tuple[str, ...]) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "window": _safe_nonnegative_int(source.get("window")),
        "sample_size": _safe_nonnegative_int(source.get("sample_size")),
        "status": _clean_text(source.get("status")) or "insufficient_sample",
        "targets": _named_counts(source.get("targets"), allowed=allowed),
        "counts": _named_counts(source.get("counts"), allowed=allowed),
        "deficits": _named_counts(source.get("deficits"), allowed=allowed),
        "quota_behavior": "warn_without_filler",
    }


def _aggregate_group(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    assessed_posts = _safe_nonnegative_int(source.get("assessed_posts"))
    meaningful = _safe_nonnegative_int(source.get("meaningful_target_conversations"))
    per_assessed = _safe_number(source.get("meaningful_per_assessed_post"))
    if per_assessed is None and assessed_posts:
        per_assessed = round(meaningful / assessed_posts, 4)
    return {
        "confirmed_publications": _safe_nonnegative_int(source.get("confirmed_publications")),
        "assessed_posts": assessed_posts,
        "meaningful_target_conversations": meaningful,
        "meaningful_per_assessed_post": per_assessed,
        "sounded_like_me": _named_counts(source.get("sounded_like_me"), allowed=VOICE_VALUES),
        "quality_flags": _named_counts(source.get("quality_flags"), allowed=QUALITY_FLAGS),
        "follow_up": _named_counts(source.get("follow_up"), allowed=FOLLOW_UP_VALUES),
    }


def _aggregate_groups(value: Any, *, allowed: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    source = value if isinstance(value, Mapping) else {}
    return {
        name: _aggregate_group(source.get(name))
        for name in allowed
        if isinstance(source.get(name), Mapping)
    }


def _learning_aggregates(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "owner_decisions": {
            "counts": _named_counts(
                (source.get("owner_decisions") or {}).get("counts")
                if isinstance(source.get("owner_decisions"), Mapping)
                else {},
                allowed=("approve", "revise", "park", "reject"),
            ),
            "edit_ratio_sample_size": _safe_nonnegative_int(
                (source.get("owner_decisions") or {}).get("edit_ratio_sample_size")
                if isinstance(source.get("owner_decisions"), Mapping)
                else 0
            ),
            "mean_owner_edit_ratio": _safe_number(
                (source.get("owner_decisions") or {}).get("mean_owner_edit_ratio")
                if isinstance(source.get("owner_decisions"), Mapping)
                else None
            ),
        },
        "by_pillar": _aggregate_groups(source.get("by_pillar"), allowed=PILLAR_IDS),
        "by_treatment": _aggregate_groups(source.get("by_treatment"), allowed=PILOT_TREATMENTS),
        "by_hook_family": _aggregate_groups(
            source.get("by_hook_family"),
            allowed=("contrarian", "curiosity", "question", "stat", "story", "lesson", "unknown"),
        ),
        "by_format": _aggregate_groups(
            source.get("by_format"),
            allowed=("text", "image", "carousel", "video", "document", "poll", "unknown"),
        ),
    }


def _receipt_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_feezie_portfolio_learning_receipt(
    summary: Mapping[str, Any] | None,
    *,
    strategy_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the bounded learning contract shared by planner, writer, and critic.

    Results cannot influence sequencing until the owner-approved sample gates
    are met. Contract mix and pilot deficits may still sequence already
    qualified evidence, but can never admit a weak idea or create filler.
    """

    contract = dict(strategy_contract or load_feezie_strategy_contract())
    contract_hash = _clean_text(contract.get("contract_hash"))
    editorial = contract["editorial_mix"]
    thresholds = {
        key: _safe_nonnegative_int(value)
        for key, value in editorial["measurement"]["learning_gate"].items()
    }
    source = dict(summary or {}) if isinstance(summary, Mapping) else {}
    source_contract = source.get("strategy_contract") if isinstance(source.get("strategy_contract"), Mapping) else {}
    compatible = bool(
        source.get("schema_version") == PERFORMANCE_SUMMARY_SCHEMA
        and source.get("workspace_key") == CANONICAL_WORKSPACE_KEY
        and _clean_text(source_contract.get("contract_hash")) == contract_hash
    )
    counts_source = source.get("counts") if compatible and isinstance(source.get("counts"), Mapping) else {}
    counts = {
        "owner_decisions": _safe_nonnegative_int(counts_source.get("owner_decisions")),
        "confirmed_publications": _safe_nonnegative_int(counts_source.get("confirmed_publications")),
        "complete_feedback_posts": _safe_nonnegative_int(counts_source.get("complete_feedback_posts")),
        "owner_assessments": _safe_nonnegative_int(counts_source.get("owner_assessments")),
    }
    advisory_ready = bool(
        compatible
        and counts["owner_decisions"] >= thresholds["minimum_owner_decisions"]
        and counts["confirmed_publications"] >= thresholds["minimum_confirmed_publications"]
    )
    strategy_review_ready = bool(
        advisory_ready
        and counts["complete_feedback_posts"] >= thresholds["minimum_complete_feedback_posts"]
    )
    if strategy_review_ready:
        learning_mode = "strategy_review_eligible"
        confidence = "review_eligible"
    elif advisory_ready:
        learning_mode = "advisory_sequencing"
        confidence = "early_directional"
    else:
        learning_mode = "collect_only"
        confidence = "insufficient_sample"

    topic_mix_source = source.get("rolling_topic_mix") if compatible else None
    intent_mix_source = source.get("rolling_intent_mix") if compatible else None
    pilot_source = source.get("initial_pilot") if compatible and isinstance(source.get("initial_pilot"), Mapping) else {}
    pilot_contract = editorial["measurement"]["initial_pilot"]
    topic_mix = _mix_receipt(topic_mix_source, allowed=PILLAR_IDS)
    intent_mix = _mix_receipt(intent_mix_source, allowed=INTENT_IDS)
    if not compatible:
        topic_mix = {
            **topic_mix,
            "window": int(editorial["rolling_topic_mix"]["window"]),
            "targets": {str(key): int(value) for key, value in editorial["rolling_topic_mix"]["counts"].items()},
            "deficits": {str(key): int(value) for key, value in editorial["rolling_topic_mix"]["counts"].items()},
        }
        intent_mix = {
            **intent_mix,
            "window": int(editorial["intent_mix"]["window"]),
            "targets": {str(key): int(value) for key, value in editorial["intent_mix"]["counts"].items()},
            "deficits": {str(key): int(value) for key, value in editorial["intent_mix"]["counts"].items()},
        }
    pilot_targets = {str(key): int(value) for key, value in pilot_contract["treatments"].items()}
    pilot_counts = _named_counts(pilot_source.get("counts"), allowed=PILOT_TREATMENTS)
    pilot_deficits = (
        _named_counts(pilot_source.get("deficits"), allowed=PILOT_TREATMENTS)
        if compatible
        else dict(pilot_targets)
    )

    receipt: dict[str, Any] = {
        "schema_version": PORTFOLIO_LEARNING_SCHEMA,
        "strategy_contract_hash": contract_hash,
        "source_state": "available" if compatible else ("incompatible" if source else "missing"),
        "summary_generated_at": _clean_text(source.get("generated_at")) if compatible else None,
        "learning_mode": learning_mode,
        "confidence": confidence,
        "counts": counts,
        "thresholds": thresholds,
        "remaining_to_advisory": {
            "owner_decisions": max(0, thresholds["minimum_owner_decisions"] - counts["owner_decisions"]),
            "confirmed_publications": max(
                0,
                thresholds["minimum_confirmed_publications"] - counts["confirmed_publications"],
            ),
        },
        "remaining_to_strategy_review": {
            "complete_feedback_posts": max(
                0,
                thresholds["minimum_complete_feedback_posts"] - counts["complete_feedback_posts"],
            ),
        },
        "contract_sequence": {
            "rolling_topic_mix": topic_mix,
            "rolling_intent_mix": intent_mix,
            "initial_pilot": {
                "id": str(pilot_contract["id"]),
                "target_count": int(pilot_contract["target_count"]),
                "confirmed_count": _safe_nonnegative_int(pilot_source.get("confirmed_count")),
                "status": _clean_text(pilot_source.get("status")) or "in_progress",
                "targets": pilot_targets,
                "counts": pilot_counts,
                "deficits": pilot_deficits,
                "quota_behavior": "warn_without_filler",
            },
        },
        "advisory_aggregates": (
            _learning_aggregates(source.get("learning_aggregates"))
            if advisory_ready
            else {}
        ),
        "decision_policy": {
            "qualified_evidence_only": True,
            "employer_safety_gate_unchanged": True,
            "proof_gate_unchanged": True,
            "outcome_reordering_allowed": advisory_ready,
            "strategy_contract_mutation_allowed": False,
            "owner_approval_required_for_contract_change": True,
            "filler_forbidden": True,
        },
    }
    receipt["receipt_sha256"] = _receipt_hash(receipt)
    return receipt


def feezie_candidate_sequence_adjustment(
    receipt: Mapping[str, Any] | None,
    *,
    pillar_id: str,
    intent: str,
    treatment: str,
) -> dict[str, Any]:
    """Return a bounded, explainable score adjustment for an eligible idea."""

    source = receipt if isinstance(receipt, Mapping) else {}
    contract_sequence = source.get("contract_sequence") if isinstance(source.get("contract_sequence"), Mapping) else {}
    topic_mix = contract_sequence.get("rolling_topic_mix") if isinstance(contract_sequence.get("rolling_topic_mix"), Mapping) else {}
    intent_mix = contract_sequence.get("rolling_intent_mix") if isinstance(contract_sequence.get("rolling_intent_mix"), Mapping) else {}
    pilot = contract_sequence.get("initial_pilot") if isinstance(contract_sequence.get("initial_pilot"), Mapping) else {}
    topic_deficit = _safe_nonnegative_int((topic_mix.get("deficits") or {}).get(pillar_id))
    intent_deficit = _safe_nonnegative_int((intent_mix.get("deficits") or {}).get(intent))
    treatment_deficit = _safe_nonnegative_int((pilot.get("deficits") or {}).get(treatment))
    contract_adjustment = min(2.0, topic_deficit * 0.5) + min(1.0, intent_deficit * 0.25) + min(
        1.5,
        treatment_deficit * 0.5,
    )
    reasons: list[str] = []
    if topic_deficit:
        reasons.append(f"topic_mix_deficit:{pillar_id}:{topic_deficit}")
    if intent_deficit:
        reasons.append(f"intent_mix_deficit:{intent}:{intent_deficit}")
    if treatment_deficit:
        reasons.append(f"pilot_treatment_deficit:{treatment}:{treatment_deficit}")

    learning_mode = _clean_text(source.get("learning_mode")) or "collect_only"
    outcome_adjustment = 0.0
    outcome_samples = 0
    if learning_mode in {"advisory_sequencing", "strategy_review_eligible"}:
        aggregates = source.get("advisory_aggregates") if isinstance(source.get("advisory_aggregates"), Mapping) else {}
        group_specs = (("by_pillar", pillar_id), ("by_treatment", treatment))
        group_adjustments: list[float] = []
        for group_name, group_key in group_specs:
            groups = aggregates.get(group_name) if isinstance(aggregates.get(group_name), Mapping) else {}
            group = groups.get(group_key) if isinstance(groups.get(group_key), Mapping) else None
            if not group:
                continue
            assessed = _safe_nonnegative_int(group.get("assessed_posts"))
            if assessed < 2:
                continue
            meaningful_rate = _safe_number(group.get("meaningful_per_assessed_post")) or 0.0
            voice = group.get("sounded_like_me") if isinstance(group.get("sounded_like_me"), Mapping) else {}
            flags = group.get("quality_flags") if isinstance(group.get("quality_flags"), Mapping) else {}
            follow_up = group.get("follow_up") if isinstance(group.get("follow_up"), Mapping) else {}
            voice_delta = (
                _safe_nonnegative_int(voice.get("yes")) - _safe_nonnegative_int(voice.get("no"))
            ) / assessed
            quality_penalty = sum(_safe_nonnegative_int(flags.get(flag)) for flag in QUALITY_FLAGS) / assessed
            follow_up_delta = (
                _safe_nonnegative_int(follow_up.get("reuse")) - _safe_nonnegative_int(follow_up.get("retire"))
            ) / assessed
            group_adjustments.append(
                min(1.5, float(meaningful_rate) * 0.5)
                + max(-1.0, min(1.0, voice_delta))
                + max(-1.5, -quality_penalty)
                + max(-0.5, min(0.5, follow_up_delta * 0.5))
            )
            outcome_samples += assessed
        if group_adjustments:
            outcome_adjustment = max(-3.0, min(3.0, sum(group_adjustments) / len(group_adjustments)))
            reasons.append(f"advisory_aggregate_signal:{outcome_samples}")

    total = round(contract_adjustment + outcome_adjustment, 3)
    return {
        "schema_version": "feezie_candidate_sequence_adjustment/v1",
        "learning_mode": learning_mode,
        "contract_adjustment": round(contract_adjustment, 3),
        "outcome_adjustment": round(outcome_adjustment, 3),
        "total_adjustment": total,
        "outcome_sample_size": outcome_samples,
        "outcome_learning_applied": bool(outcome_samples),
        "reasons": reasons,
        "admission_changed": False,
        "filler_allowed": False,
    }
