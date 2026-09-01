from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any


SCHEMA_VERSION = "standup_relevance/v1"
POLICY_VERSION = "feezie_positioning_contract/2026-08-27"
DEFAULT_FRESHNESS_WINDOW_HOURS = 168

TAG_ORDER = (
    "execution_or_lifecycle",
    "content_quality",
    "pipeline_health",
    "cross_system",
    "owner_intent_or_approval",
    "privacy_or_public_claim",
    "strategy_or_positioning",
    "priority_tradeoff",
    "feedback_learning",
    "informational_only",
)
TAG_SET = set(TAG_ORDER)

ROLE_ORDER = ("jean_claude", "neo", "yoda")
ROLE_DISPLAY_NAMES = {
    "jean_claude": "Jean-Claude",
    "neo": "Neo",
    "yoda": "Yoda",
}
ROLE_LENSES = {
    "jean_claude": "routine portfolio execution, lifecycle, backlog, content quality, pipeline health, and feedback",
    "neo": "employer and privacy boundaries, public claims, owner gates, cross-system conflicts, and executive conflicts",
    "yoda": "audience, thesis, positioning, values, and long-term priority tradeoffs",
}
CANONICAL_MEETING_CLOSER_DISPLAY_NAME = "Jean-Claude"
ROLE_REASON_BY_TAG = {
    "jean_claude": {
        "execution_or_lifecycle": "routine_portfolio_execution",
        "content_quality": "content_quality_control",
        "pipeline_health": "pipeline_health_decision",
        "feedback_learning": "feedback_loop_decision",
    },
    "neo": {
        "cross_system": "cross_system_or_executive_conflict",
        "owner_intent_or_approval": "owner_gate",
        "privacy_or_public_claim": "employer_privacy_or_public_claim_boundary",
    },
    "yoda": {
        "strategy_or_positioning": "audience_thesis_positioning_or_values_change",
        "priority_tradeoff": "long_term_priority_tradeoff",
    },
}

TAG_ALIASES = {
    "execution": "execution_or_lifecycle",
    "lifecycle": "execution_or_lifecycle",
    "backlog": "execution_or_lifecycle",
    "content_quality_control": "content_quality",
    "quality": "content_quality",
    "health": "pipeline_health",
    "system_health": "pipeline_health",
    "cross_workspace": "cross_system",
    "cross_workspace_conflict": "cross_system",
    "owner_approval": "owner_intent_or_approval",
    "owner_gate": "owner_intent_or_approval",
    "privacy": "privacy_or_public_claim",
    "public_claim": "privacy_or_public_claim",
    "employer_boundary": "privacy_or_public_claim",
    "strategy": "strategy_or_positioning",
    "positioning": "strategy_or_positioning",
    "audience": "strategy_or_positioning",
    "tradeoff": "priority_tradeoff",
    "feedback": "feedback_learning",
    "learning": "feedback_learning",
    "informational": "informational_only",
    "fyi": "informational_only",
}

STRUCTURED_TAG_FIELDS = {
    "execution_or_lifecycle": (
        "action_required",
        "decision_required",
        "has_blocker",
        "unresolved_blocker",
        "lifecycle_change",
        "pm_state_change",
    ),
    "content_quality": ("content_quality_issue", "quality_review_required", "draft_quality_issue"),
    "pipeline_health": ("pipeline_health_issue", "health_action_required", "red_or_yellow_health"),
    "cross_system": ("cross_system_conflict", "cross_workspace_conflict", "executive_conflict"),
    "owner_intent_or_approval": (
        "owner_gate",
        "owner_approval_required",
        "owner_intent_change",
        "approval_required",
    ),
    "privacy_or_public_claim": (
        "privacy_boundary",
        "public_claim_review",
        "employer_boundary",
        "employer_specific",
    ),
    "strategy_or_positioning": (
        "audience_change",
        "thesis_change",
        "positioning_change",
        "values_change",
        "long_term_direction_change",
    ),
    "priority_tradeoff": ("priority_tradeoff", "long_term_tradeoff"),
    "feedback_learning": ("feedback_decision", "learning_review_required"),
    "informational_only": ("informational_only", "no_action_required"),
}

TEXT_PATTERNS = {
    "execution_or_lifecycle": re.compile(
        r"\b(?:pm card|backlog|lifecycle|handoff|next action|action required|unresolved blocker|"
        r"schedule|scheduling|publication board|publishing board|queue state|advance the queue)\b",
        flags=re.IGNORECASE,
    ),
    "content_quality": re.compile(
        r"\b(?:content quality|quality control|draft quality|hook lab|critic|duplicate concept|"
        r"weak draft|editorial quality|proof treatment)\b",
        flags=re.IGNORECASE,
    ),
    "pipeline_health": re.compile(
        r"\b(?:pipeline health|system health|health condition|red health|yellow health|"
        r"ingestion failure|pipeline failure|pipeline blocked|pipeline degraded)\b",
        flags=re.IGNORECASE,
    ),
    "cross_system": re.compile(
        r"\b(?:cross[- ]system|cross[- ]workspace|routing conflict|system conflict|"
        r"source of truth conflict|authority conflict|executive conflict|alias conflict)\b",
        flags=re.IGNORECASE,
    ),
    "owner_intent_or_approval": re.compile(
        r"\b(?:owner approval|owner review|owner gate|owner intent|approval required|"
        r"requires approval|permission required|item[- ]level approval)\b",
        flags=re.IGNORECASE,
    ),
    "privacy_or_public_claim": re.compile(
        r"\b(?:privacy|public claim|employer(?:[- ]specific| boundary| privacy| name| naming)?|"
        r"confidential|private metric|student detail|family detail|client detail|colleague detail|"
        r"job search|exit signaling|sponsorship|endorsement)\b",
        flags=re.IGNORECASE,
    ),
    "strategy_or_positioning": re.compile(
        r"\b(?:target audience|audience change|thesis|positioning|north star|values change|"
        r"editorial mix|topic mix|long[- ]term direction|career destination|strategy change)\b",
        flags=re.IGNORECASE,
    ),
    "priority_tradeoff": re.compile(
        r"\b(?:priority trade[- ]?off|long[- ]term trade[- ]?off|strategic trade[- ]?off|"
        r"competing priorities|choose between)\b",
        flags=re.IGNORECASE,
    ),
    "feedback_learning": re.compile(
        r"\b(?:feedback loop|feedback learning|performance learning|audience response|"
        r"24[- ]hour feedback|7[- ]day feedback|editorial lesson)\b",
        flags=re.IGNORECASE,
    ),
    "informational_only": re.compile(
        r"\b(?:informational only|for information only|for awareness|fyi|no action required|"
        r"no decision required|status only)\b",
        flags=re.IGNORECASE,
    ),
}

STALE_STATUSES = {"archived", "expired", "retired", "stale", "superseded"}
PATHISH_EVIDENCE_RE = re.compile(r"^(?:file:/{2,}|~[/\\]|/|[a-zA-Z]:[/\\])")
URL_RE = re.compile(r"\b(?:https?://|file://)\S+", flags=re.IGNORECASE)
WINDOWS_PATH_RE = re.compile(r"(?<!\w)[a-zA-Z]:\\[^\s,;)}\]]+")
HOME_PATH_RE = re.compile(r"(?<!\w)~[/\\][^\s,;)}\]]+")
ABSOLUTE_PATH_RE = re.compile(r"(?<![:\w])/(?:[^/\s]+/)*[^\s,;)}\]]+")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_free_text(value: Any) -> str:
    text = _clean_text(value)
    text = URL_RE.sub("[external-reference]", text)
    text = WINDOWS_PATH_RE.sub("[private-reference]", text)
    text = HOME_PATH_RE.sub("[private-reference]", text)
    text = ABSOLUTE_PATH_RE.sub("[private-reference]", text)
    return _clean_text(text)


def _path_free_identifier(value: Any) -> str:
    identifier = _clean_text(value)
    if not identifier:
        return ""
    if PATHISH_EVIDENCE_RE.search(identifier) or "/" in identifier or "\\" in identifier:
        return f"opaque-ref-{_stable_hash(identifier)[:12]}"
    return identifier[:160]


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = _slug(value)
    if normalized in {"true", "yes", "1", "on"}:
        return True
    if normalized in {"false", "no", "0", "off"}:
        return False
    return None


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _clean_text(value)
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _evaluation_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    parsed = _as_utc(value)
    if parsed is None:
        raise ValueError("now must be a timezone-aware ai_clone_utc timestamp.")
    return parsed


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _iter_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part for part in re.split(r"[,\n]", value) if _clean_text(part)]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return list(value)
    return [value]


def _explicit_tags(item: Mapping[str, Any]) -> set[str]:
    tags: set[str] = set()
    for raw_tag in _iter_values(item.get("tags")) + _iter_values(item.get("agenda_tags")):
        normalized = _slug(raw_tag)
        normalized = TAG_ALIASES.get(normalized, normalized)
        if normalized in TAG_SET:
            tags.add(normalized)
    return tags


def _structured_tags(item: Mapping[str, Any]) -> set[str]:
    tags: set[str] = set()
    for tag, fields in STRUCTURED_TAG_FIELDS.items():
        if any(_as_bool(item.get(field)) is True for field in fields):
            tags.add(tag)

    health = _slug(item.get("health") or item.get("health_status"))
    if health in {"red", "yellow", "degraded", "blocked"}:
        tags.add("pipeline_health")
    return tags


def _text_tags(item: Mapping[str, Any]) -> set[str]:
    text = " ".join(
        _clean_text(item.get(field))
        for field in ("title", "summary", "description", "decision", "request", "blocker")
    )
    return {tag for tag, pattern in TEXT_PATTERNS.items() if pattern.search(text)}


def _normalize_source_ids(item: Mapping[str, Any]) -> list[str]:
    raw_values: list[Any] = []
    for field in ("source_ids", "evidence_ids"):
        raw_values.extend(_iter_values(item.get(field)))
    for field in ("source_id", "card_id", "link_id"):
        if item.get(field) is not None:
            raw_values.append(item.get(field))
    return sorted({safe for value in raw_values if (safe := _path_free_identifier(value))})


def _agenda_item_id(item: Mapping[str, Any], identity_material: Mapping[str, Any]) -> str:
    for field in ("agenda_item_id", "item_id", "id", "card_id"):
        candidate = _path_free_identifier(item.get(field))
        if candidate:
            return candidate
    return f"agenda-{_stable_hash(identity_material)[:12]}"


def _freshness(
    item: Mapping[str, Any],
    *,
    observed_at: datetime | None,
    now: datetime,
    freshness_window_hours: int,
) -> str:
    status = _slug(item.get("status"))
    explicit_freshness = _slug(item.get("freshness"))
    is_stale = _as_bool(item.get("is_stale"))
    is_fresh = _as_bool(item.get("is_fresh"))
    active_exception = _as_bool(item.get("active_exception"))

    if status in STALE_STATUSES or explicit_freshness in STALE_STATUSES or is_stale is True or is_fresh is False:
        return "stale"
    if active_exception is True:
        return "current"
    if explicit_freshness in {"current", "fresh"} or is_fresh is True:
        return "current"
    if observed_at is None:
        return "unknown"
    if observed_at < now - timedelta(hours=freshness_window_hours):
        return "stale"
    return "current"


def normalize_agenda_item(
    item: Mapping[str, Any],
    *,
    now: datetime | None = None,
    freshness_window_hours: int = DEFAULT_FRESHNESS_WINDOW_HOURS,
) -> dict[str, Any]:
    """Return a bounded, path-free agenda item with deterministic relevance tags."""

    if not isinstance(item, Mapping):
        raise TypeError("Every agenda item must be a mapping.")
    if freshness_window_hours <= 0:
        raise ValueError("freshness_window_hours must be positive.")
    evaluated_at = _evaluation_time(now)
    observed_at = _as_utc(item.get("observed_at"))
    source_ids = _normalize_source_ids(item)
    workspace_key = _slug(item.get("workspace_key") or item.get("workspace") or "feezie-os").replace("_", "-")
    title = _path_free_text(item.get("title") or item.get("summary") or "Untitled agenda item")
    status = _slug(item.get("status")) or "open"
    tags = _explicit_tags(item) | _structured_tags(item) | _text_tags(item)

    action_is_explicitly_false = _as_bool(item.get("decision_required")) is False and _as_bool(
        item.get("action_required")
    ) is False
    if action_is_explicitly_false:
        tags.add("informational_only")
    role_tags = tags - {"informational_only"}
    if not role_tags:
        tags.add("informational_only")

    freshness = _freshness(
        item,
        observed_at=observed_at,
        now=evaluated_at,
        freshness_window_hours=freshness_window_hours,
    )
    explicit_freshness = _slug(item.get("freshness")) or None
    identity_material = {
        "workspace_key": workspace_key,
        "title": title,
        "source_ids": source_ids,
        "observed_at": _iso(observed_at),
        "status": status,
        "explicit_freshness": explicit_freshness,
        "tags": sorted(tags, key=TAG_ORDER.index),
    }
    agenda_item_id = _agenda_item_id(item, identity_material)
    input_fingerprint = _stable_hash({"agenda_item_id": agenda_item_id, **identity_material})

    exclusion_reasons: list[str] = []
    if observed_at is None:
        exclusion_reasons.append("semantic_observation_missing_or_invalid")
    if freshness == "stale":
        exclusion_reasons.append("stale")
    if "informational_only" in tags:
        exclusion_reasons.append("informational_only")
    if not role_tags:
        exclusion_reasons.append("no_role_relevant_tag")

    return {
        "agenda_item_id": agenda_item_id,
        "workspace_key": workspace_key,
        "title": title,
        "source_ids": source_ids,
        "observed_at": _iso(observed_at),
        "freshness": freshness,
        "status": status,
        "tags": sorted(tags, key=TAG_ORDER.index),
        "eligible_for_selection": not exclusion_reasons,
        "exclusion_reasons": exclusion_reasons,
        "input_fingerprint": input_fingerprint,
    }


def normalize_agenda_items(
    agenda_items: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    freshness_window_hours: int = DEFAULT_FRESHNESS_WINDOW_HOURS,
) -> list[dict[str, Any]]:
    evaluated_at = _evaluation_time(now)
    normalized = [
        normalize_agenda_item(
            item,
            now=evaluated_at,
            freshness_window_hours=freshness_window_hours,
        )
        for item in agenda_items
    ]
    normalized.sort(key=lambda item: (item["agenda_item_id"], item["input_fingerprint"]))

    seen: set[str] = set()
    for item in normalized:
        fingerprint = item["input_fingerprint"]
        if fingerprint in seen:
            item["eligible_for_selection"] = False
            item["exclusion_reasons"] = sorted(set(item["exclusion_reasons"] + ["duplicate"]))
        seen.add(fingerprint)
    return normalized


def _reason_evidence(normalized_agenda: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, set[str]]]] = {role: {} for role in ROLE_ORDER}
    for item in normalized_agenda:
        if not item["eligible_for_selection"]:
            continue
        for role in ROLE_ORDER:
            for tag, reason_code in ROLE_REASON_BY_TAG[role].items():
                if tag not in item["tags"]:
                    continue
                evidence = grouped[role].setdefault(
                    reason_code,
                    {"matching_tags": set(), "agenda_item_ids": set(), "source_ids": set()},
                )
                evidence["matching_tags"].add(tag)
                evidence["agenda_item_ids"].add(item["agenda_item_id"])
                evidence["source_ids"].update(item["source_ids"])

    output: dict[str, list[dict[str, Any]]] = {}
    for role in ROLE_ORDER:
        role_entries: list[dict[str, Any]] = []
        for reason_code in sorted(grouped[role]):
            evidence = grouped[role][reason_code]
            role_entries.append(
                {
                    "reason_code": reason_code,
                    "matching_tags": sorted(evidence["matching_tags"], key=TAG_ORDER.index),
                    "agenda_item_ids": sorted(evidence["agenda_item_ids"]),
                    "source_ids": sorted(evidence["source_ids"]),
                }
            )
        if role_entries:
            output[role] = role_entries
    return output


def build_standup_relevance_plan(
    agenda_items: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    freshness_window_hours: int = DEFAULT_FRESHNESS_WINDOW_HOURS,
    previous_input_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Select only roles whose approved lens can materially change the outcome.

    Role-lens records are deterministic policy synthesis. They are deliberately
    not represented as independent Jean-Claude, Neo, or Yoda agent runs.
    """

    evaluated_at = _evaluation_time(now)
    normalized_agenda = normalize_agenda_items(
        agenda_items,
        now=evaluated_at,
        freshness_window_hours=freshness_window_hours,
    )
    unique_item_fingerprints = sorted({item["input_fingerprint"] for item in normalized_agenda})
    input_fingerprint = _stable_hash(
        {
            "policy_version": POLICY_VERSION,
            "agenda_item_fingerprints": unique_item_fingerprints,
        }
    )
    unchanged = bool(previous_input_fingerprint) and previous_input_fingerprint == input_fingerprint
    # These are independently relevant role lenses only. Meeting closure is a
    # separate non-transferable authority and must never be manufactured as a
    # relevance result merely to make Jean-Claude the closer.
    reason_evidence = {} if unchanged else _reason_evidence(normalized_agenda)
    selected_roles = [role for role in ROLE_ORDER if role in reason_evidence]

    participant_plan: list[dict[str, Any]] = []
    for role in selected_roles:
        entries = reason_evidence[role]
        participant_plan.append(
            {
                "role": role,
                "display_name": ROLE_DISPLAY_NAMES[role],
                "provenance": "synthesized_role_lens",
                "lens": ROLE_LENSES[role],
                "reason_codes": [entry["reason_code"] for entry in entries],
                "agenda_item_ids": sorted(
                    {agenda_item_id for entry in entries for agenda_item_id in entry["agenda_item_ids"]}
                ),
                "source_ids": sorted({source_id for entry in entries for source_id in entry["source_ids"]}),
            }
        )

    if not selected_roles:
        disposition = "collapse_freshness"
        disposition_reason = "unchanged_input" if unchanged else "no_relevant_agenda"
    elif len(selected_roles) == 1:
        disposition = "decision_record"
        disposition_reason = "single_relevant_role"
    else:
        disposition = "run"
        disposition_reason = "multiple_relevant_roles"

    return {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "evaluated_at": _iso(evaluated_at),
        "input_fingerprint": input_fingerprint,
        "previous_input_fingerprint_matched": unchanged,
        "disposition": disposition,
        "disposition_reason": disposition_reason,
        "selected_roles": selected_roles,
        "participant_count": len(selected_roles),
        "participant_plan": participant_plan,
        "reason_evidence": reason_evidence,
        "normalized_agenda": normalized_agenda,
        "provenance": {
            "participant_selection": "deterministic_policy",
            "role_lenses": "synthesized_role_lens",
            "independent_agent_runs": [],
        },
    }


def evaluate_standup_relevance(
    agenda_items: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    freshness_window_hours: int = DEFAULT_FRESHNESS_WINDOW_HOURS,
    previous_input_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Compatibility name for callers that treat the plan as an evaluation."""

    return build_standup_relevance_plan(
        agenda_items,
        now=now,
        freshness_window_hours=freshness_window_hours,
        previous_input_fingerprint=previous_input_fingerprint,
    )


def validate_standup_relevance_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a persisted FEEZIE plan against the deterministic role policy.

    The promotion API must not trust caller-selected display names merely
    because a non-empty ``standup_relevance`` object was supplied.  This
    validator reconstructs the complete participant decision from the bounded
    normalized agenda already carried by the plan.
    """

    plan = dict(value or {})
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Standup relevance schema is not authoritative.")
    if plan.get("policy_version") != POLICY_VERSION:
        raise ValueError("Standup relevance policy version is not authoritative.")
    normalized_agenda = [
        dict(item)
        for item in (plan.get("normalized_agenda") or [])
        if isinstance(item, Mapping)
    ]
    if normalized_agenda != list(plan.get("normalized_agenda") or []):
        raise ValueError("Standup relevance normalized agenda is malformed.")
    if len(normalized_agenda) > 100:
        raise ValueError("Standup relevance normalized agenda exceeds its bound.")
    required_item_fields = {
        "agenda_item_id",
        "workspace_key",
        "title",
        "source_ids",
        "observed_at",
        "freshness",
        "status",
        "tags",
        "eligible_for_selection",
        "exclusion_reasons",
        "input_fingerprint",
    }
    for item in normalized_agenda:
        if set(item) != required_item_fields:
            raise ValueError("Standup relevance normalized agenda item has an invalid shape.")
        if not isinstance(item.get("eligible_for_selection"), bool):
            raise ValueError("Standup relevance eligibility must be boolean.")
        if not isinstance(item.get("tags"), list) or any(tag not in TAG_SET for tag in item["tags"]):
            raise ValueError("Standup relevance agenda tags are invalid.")
        if not isinstance(item.get("source_ids"), list) or not isinstance(item.get("exclusion_reasons"), list):
            raise ValueError("Standup relevance evidence lists are malformed.")
        fingerprint = str(item.get("input_fingerprint") or "").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Standup relevance agenda fingerprint is invalid.")

    input_fingerprint = _stable_hash(
        {
            "policy_version": POLICY_VERSION,
            "agenda_item_fingerprints": sorted(
                {str(item["input_fingerprint"]) for item in normalized_agenda}
            ),
        }
    )
    if str(plan.get("input_fingerprint") or "") != input_fingerprint:
        raise ValueError("Standup relevance input fingerprint is inconsistent.")

    unchanged = plan.get("previous_input_fingerprint_matched") is True
    reason_evidence = {} if unchanged else _reason_evidence(normalized_agenda)
    selected_roles = [role for role in ROLE_ORDER if role in reason_evidence]
    participant_plan: list[dict[str, Any]] = []
    for role in selected_roles:
        entries = reason_evidence[role]
        participant_plan.append(
            {
                "role": role,
                "display_name": ROLE_DISPLAY_NAMES[role],
                "provenance": "synthesized_role_lens",
                "lens": ROLE_LENSES[role],
                "reason_codes": [entry["reason_code"] for entry in entries],
                "agenda_item_ids": sorted(
                    {
                        agenda_item_id
                        for entry in entries
                        for agenda_item_id in entry["agenda_item_ids"]
                    }
                ),
                "source_ids": sorted(
                    {
                        source_id
                        for entry in entries
                        for source_id in entry["source_ids"]
                    }
                ),
            }
        )
    if not selected_roles:
        disposition = "collapse_freshness"
        disposition_reason = "unchanged_input" if unchanged else "no_relevant_agenda"
    elif len(selected_roles) == 1:
        disposition = "decision_record"
        disposition_reason = "single_relevant_role"
    else:
        disposition = "run"
        disposition_reason = "multiple_relevant_roles"

    expected = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "evaluated_at": plan.get("evaluated_at"),
        "input_fingerprint": input_fingerprint,
        "previous_input_fingerprint_matched": unchanged,
        "disposition": disposition,
        "disposition_reason": disposition_reason,
        "selected_roles": selected_roles,
        "participant_count": len(selected_roles),
        "participant_plan": participant_plan,
        "reason_evidence": reason_evidence,
        "normalized_agenda": normalized_agenda,
        "provenance": {
            "participant_selection": "deterministic_policy",
            "role_lenses": "synthesized_role_lens",
            "independent_agent_runs": [],
        },
    }
    if _semantic_plan(plan) != _semantic_plan(expected):
        raise ValueError("Standup relevance plan does not match the deterministic role policy.")
    if _as_utc(plan.get("evaluated_at")) is None:
        raise ValueError("Standup relevance plan requires an explicit evaluation timestamp.")
    return plan


def effective_feezie_meeting_participants(value: Mapping[str, Any]) -> list[str]:
    """Return the meeting roster without turning closure into relevance.

    The relevance plan contains only independently selected lenses. A held
    FEEZIE meeting additionally requires Jean-Claude's non-transferable PM and
    execution closure authority, whether or not his execution lens was itself
    selected by the agenda.
    """

    plan = validate_standup_relevance_plan(value)
    if str(plan.get("disposition") or "").strip() != "run":
        raise ValueError("Only a run relevance result has a FEEZIE meeting roster.")
    selected = [
        str(item.get("display_name") or "").strip()
        for item in (plan.get("participant_plan") or [])
        if isinstance(item, Mapping) and str(item.get("display_name") or "").strip()
    ]
    if len(selected) < 2 or len(set(selected)) != len(selected):
        raise ValueError(
            "A FEEZIE meeting requires at least two unique relevance-selected lenses."
        )
    return [
        CANONICAL_MEETING_CLOSER_DISPLAY_NAME,
        *[
            participant
            for participant in selected
            if participant != CANONICAL_MEETING_CLOSER_DISPLAY_NAME
        ],
    ]


def _semantic_plan(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
