from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

from app.services.feezie_positioning_contract_service import (
    load_feezie_strategy_contract,
    normalize_feezie_intent,
)
from app.services.workspace_snapshot_store import upsert_snapshot
from app.utils.runtime_workspace_root import resolve_runtime_workspace_root

import sys


REPO_ROOT = resolve_runtime_workspace_root(__file__)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_paths import workspace_state_path  # noqa: E402


EVENT_SCHEMA = "linkedin_publication_event/v1"
SUMMARY_SCHEMA = "linkedin_publication_summary/v1"
STATUS_SCHEMA = "linkedin_publication_status/v1"
LIFECYCLE_PROJECTION_SCHEMA = "linkedin_publication_lifecycle_projection/v1"
CANONICAL_WORKSPACE_KEY = "feezie-os"
LIFECYCLE_PROJECTION_WORKSPACE_KEY = "feezie-performance-lifecycle"
COMPATIBILITY_WORKSPACE_KEYS = ("linkedin-os", "linkedin-content-os")
EVENTS_RELATIVE_PATH = Path("analytics/linkedin_publication_events.jsonl")
SUMMARY_RELATIVE_PATH = Path("analytics/linkedin_publication_summary.json")
SNAPSHOT_TYPE = "publication_performance_summary"
STATUS_SNAPSHOT_TYPE = "publication_performance_status"
PERFORMANCE_PROJECTION_STALE_AFTER_HOURS = 48
EVENT_TYPES = {
    "owner_reviewed",
    "publication_confirmed",
    "metrics_24h_recorded",
    "metrics_7d_recorded",
    "owner_assessment_recorded",
}
LEARNING_PILLAR_IDS = ("ai_native", "leadership_operator", "trust_systems")
LEARNING_TREATMENTS = (
    "practical_ai_systems",
    "education_or_trust",
    "operator_story_personal_technology",
    "operator_story_education_community",
)
LEARNING_HOOK_FAMILIES = ("contrarian", "curiosity", "question", "stat", "story", "lesson", "unknown")
LEARNING_FORMATS = ("text", "image", "carousel", "video", "document", "poll", "unknown")
LEARNING_QUALITY_FLAGS = ("too_generic", "too_safe", "too_exposed", "wrong_audience")
LEARNING_VOICE_VALUES = ("yes", "mixed", "no")
LEARNING_FOLLOW_UP_VALUES = ("reuse", "iterate", "retire", "none")
CONTENT_HASH_RE = re.compile(r"^(?:sha256:)?([a-f0-9]{64})$", flags=re.IGNORECASE)
LINKEDIN_POST_PATH_RE = re.compile(r"^/(?:posts/|feed/update/)", flags=re.IGNORECASE)
LIFECYCLE_IDENTITY_TOKEN_RE = re.compile(r"^[a-f0-9]{64}$")


class LinkedinPerformanceLedgerError(RuntimeError):
    pass


class LinkedinPerformanceLedgerConflict(LinkedinPerformanceLedgerError):
    pass


class LinkedinPerformanceLedgerCorruption(LinkedinPerformanceLedgerError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LinkedinPerformanceLedgerError("Performance timestamps must include a timezone.")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise LinkedinPerformanceLedgerCorruption(f"Invalid {field} in publication ledger.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LinkedinPerformanceLedgerCorruption(f"{field} in publication ledger is not timezone-aware.")
    return parsed.astimezone(timezone.utc)


def _normalize_hash(value: Any) -> str:
    match = CONTENT_HASH_RE.fullmatch(_clean_text(value))
    if not match:
        raise LinkedinPerformanceLedgerError("content_version_sha256 must be a 64-character SHA-256 digest.")
    return match.group(1).lower()


def linkedin_performance_identity_token(content_id: Any, content_version_sha256: Any) -> str:
    """Return the opaque lookup token for one exact content identity."""

    normalized_content_id = _clean_text(content_id)
    if not normalized_content_id or len(normalized_content_id) > 160:
        raise LinkedinPerformanceLedgerError("content_id must contain 1 to 160 characters.")
    normalized_digest = _normalize_hash(content_version_sha256)
    return hashlib.sha256(
        f"{normalized_content_id}\x00{normalized_digest}".encode("utf-8")
    ).hexdigest()


def linkedin_performance_lifecycle_snapshot_type(identity_token: Any) -> str:
    normalized = _clean_text(identity_token).lower()
    if LIFECYCLE_IDENTITY_TOKEN_RE.fullmatch(normalized) is None:
        raise LinkedinPerformanceLedgerError("Lifecycle identity token is invalid.")
    return f"publication_performance_lifecycle:{normalized}"


def linkedin_content_version_sha256(copy_text: str) -> str:
    """Return the canonical exact-copy digest used by the private ledger.

    Keep this public helper as the single digest contract for owner review,
    publication confirmation, and exact-identity lifecycle lookups.  Only line
    ending normalization and outer whitespace trimming are applied; the post's
    internal spacing and wording remain version-significant.
    """

    normalized = str(copy_text).replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _hash_copy(copy_text: str) -> str:
    """Compatibility alias for existing ledger call sites."""

    return linkedin_content_version_sha256(copy_text)


def normalize_linkedin_publication_url(value: Any) -> str:
    raw = _clean_text(value)
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise LinkedinPerformanceLedgerError("publication_url is not a valid URL.") from exc
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or host not in {"linkedin.com", "www.linkedin.com"}:
        raise LinkedinPerformanceLedgerError("publication_url must be an HTTPS linkedin.com post URL.")
    if parsed.username or parsed.password or parsed.port is not None:
        raise LinkedinPerformanceLedgerError("publication_url must not contain credentials or a custom port.")
    if not LINKEDIN_POST_PATH_RE.match(parsed.path or ""):
        raise LinkedinPerformanceLedgerError("publication_url must use a LinkedIn /posts/ or /feed/update/ path.")
    normalized_path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/")
    return urlunsplit(("https", "www.linkedin.com", normalized_path, parsed.query, ""))


def _logical_ref(value: Any, *, field: str) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    path = Path(cleaned)
    if path.is_absolute() or ".." in path.parts or cleaned.startswith(("~", "file:")):
        raise LinkedinPerformanceLedgerError(f"{field} must be a logical relative reference, not a local path.")
    return path.as_posix()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _semantic_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _active_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {
        str(event.get("supersedes_event_id"))
        for event in events
        if event.get("supersedes_event_id")
    }
    return [event for event in events if str(event.get("event_id")) not in superseded]


def _event_slot(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type") or "")
    content_id = str(event.get("content_id") or "")
    content_hash = str(event.get("content_version_sha256") or "")
    publication_id = str(event.get("publication_id") or "")
    if event_type in {"owner_reviewed", "publication_confirmed"}:
        return f"{event_type}:{content_id}:{content_hash}"
    return f"{event_type}:{publication_id}"


def _json_object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Fail closed when a ledger row repeats a key at any JSON object depth."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LinkedinPerformanceLedgerCorruption("Publication ledger contains a duplicate JSON key.")
        result[key] = value
    return result


def _safe_count_mapping(value: Any) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int | None] = {}
    for key, item in value.items():
        if item is None:
            result[str(key)] = None
        elif isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise LinkedinPerformanceLedgerError(f"Metric {key} must be a nonnegative integer or null.")
        else:
            result[str(key)] = item
    return result


def _aggregate_count_projection(value: Any, *, allowed_keys: set[str]) -> dict[str, int | float | bool | None]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int | float | bool | None] = {}
    for key in allowed_keys:
        item = value.get(key)
        if item is None or (isinstance(item, (int, float, bool)) and not isinstance(item, str)):
            result[key] = item
    return result


def _safe_projection_text(value: Any, *, limit: int, allowed: set[str] | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    if not text or (allowed is not None and text not in allowed):
        return None
    return text[:limit]


def _safe_projection_iso(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return _parse_iso(value, field="projection timestamp").replace(microsecond=0).isoformat()
    except LinkedinPerformanceLedgerCorruption:
        return None


def _aggregate_named_counts(
    value: Any,
    *,
    limit: int = 24,
    allowed_names: set[str] | None = None,
) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for raw_key, item in list(value.items())[:limit]:
        key = str(raw_key or "").strip() if isinstance(raw_key, str) else ""
        if re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", key) is None:
            continue
        if allowed_names is not None and key not in allowed_names:
            continue
        if key and isinstance(item, int) and not isinstance(item, bool) and item >= 0:
            result[key] = item
    return result


def _mix_browser_projection(value: Any, *, allowed_names: set[str]) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    projected = _aggregate_count_projection(
        source,
        allowed_keys={"window", "sample_size"},
    )
    status = _safe_projection_text(
        source.get("status"),
        limit=80,
        allowed={"measured", "insufficient_sample", "in_progress", "complete"},
    )
    if status:
        projected["status"] = status
    projected["targets"] = _aggregate_named_counts(source.get("targets"), allowed_names=allowed_names)
    projected["counts"] = _aggregate_named_counts(source.get("counts"), allowed_names=allowed_names)
    projected["deficits"] = _aggregate_named_counts(source.get("deficits"), allowed_names=allowed_names)
    projected["quota_behavior"] = "warn_without_filler"
    return projected


def _empty_learning_group() -> dict[str, Any]:
    return {
        "confirmed_publications": 0,
        "assessed_posts": 0,
        "meaningful_target_conversations": 0,
        "meaningful_per_assessed_post": None,
        "sounded_like_me": {name: 0 for name in LEARNING_VOICE_VALUES},
        "quality_flags": {name: 0 for name in LEARNING_QUALITY_FLAGS},
        "follow_up": {name: 0 for name in LEARNING_FOLLOW_UP_VALUES},
    }


def _build_learning_aggregates(
    *,
    publications: list[dict[str, Any]],
    events_by_publication: dict[str, dict[str, dict[str, Any]]],
    owner_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    group_specs = {
        "by_pillar": LEARNING_PILLAR_IDS,
        "by_treatment": LEARNING_TREATMENTS,
        "by_hook_family": LEARNING_HOOK_FAMILIES,
        "by_format": LEARNING_FORMATS,
    }
    groups = {
        group_name: {name: _empty_learning_group() for name in names}
        for group_name, names in group_specs.items()
    }
    for publication in publications:
        publication_id = str(publication.get("publication_id") or "")
        classification = (publication.get("data") or {}).get("classification") or {}
        keys = {
            "by_pillar": _clean_text(classification.get("pillar_id")),
            "by_treatment": _clean_text(classification.get("treatment")),
            "by_hook_family": _clean_text(classification.get("hook_family")).lower() or "unknown",
            "by_format": _clean_text(classification.get("format")).lower() or "unknown",
        }
        if keys["by_hook_family"] not in LEARNING_HOOK_FAMILIES:
            keys["by_hook_family"] = "unknown"
        if keys["by_format"] not in LEARNING_FORMATS:
            keys["by_format"] = "unknown"
        assessment = (events_by_publication.get(publication_id) or {}).get("owner_assessment_recorded")
        assessment_data = assessment.get("data") if isinstance(assessment, dict) and isinstance(assessment.get("data"), dict) else {}
        for group_name, key in keys.items():
            group = groups[group_name].get(key)
            if group is None:
                continue
            group["confirmed_publications"] += 1
            if not assessment:
                continue
            group["assessed_posts"] += 1
            group["meaningful_target_conversations"] += _safe_nonnegative_int(
                assessment_data.get("meaningful_target_conversations")
            )
            voice = _clean_text(assessment_data.get("sounded_like_me")).lower()
            if voice in group["sounded_like_me"]:
                group["sounded_like_me"][voice] += 1
            for flag in assessment_data.get("quality_flags") or []:
                normalized_flag = _clean_text(flag).lower()
                if normalized_flag in group["quality_flags"]:
                    group["quality_flags"][normalized_flag] += 1
            follow_up = _clean_text(assessment_data.get("follow_up")).lower()
            if follow_up in group["follow_up"]:
                group["follow_up"][follow_up] += 1
    for group_map in groups.values():
        for group in group_map.values():
            assessed = int(group["assessed_posts"])
            group["meaningful_per_assessed_post"] = (
                round(int(group["meaningful_target_conversations"]) / assessed, 4)
                if assessed
                else None
            )

    decision_counts = {name: 0 for name in ("approve", "revise", "park", "reject")}
    edit_ratios: list[float] = []
    for event in owner_decisions:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        decision = _clean_text(data.get("decision")).lower()
        if decision in decision_counts:
            decision_counts[decision] += 1
        edit_ratio = data.get("owner_edit_ratio")
        if isinstance(edit_ratio, (int, float)) and not isinstance(edit_ratio, bool) and 0 <= float(edit_ratio) <= 1:
            edit_ratios.append(float(edit_ratio))
    return {
        "schema_version": "feezie_learning_aggregates/v1",
        "owner_decisions": {
            "counts": decision_counts,
            "edit_ratio_sample_size": len(edit_ratios),
            "mean_owner_edit_ratio": round(sum(edit_ratios) / len(edit_ratios), 4) if edit_ratios else None,
        },
        **groups,
    }


def _browser_learning_group(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        **_aggregate_count_projection(
            source,
            allowed_keys={
                "confirmed_publications",
                "assessed_posts",
                "meaningful_target_conversations",
                "meaningful_per_assessed_post",
            },
        ),
        "sounded_like_me": _aggregate_named_counts(
            source.get("sounded_like_me"),
            allowed_names=set(LEARNING_VOICE_VALUES),
        ),
        "quality_flags": _aggregate_named_counts(
            source.get("quality_flags"),
            allowed_names=set(LEARNING_QUALITY_FLAGS),
        ),
        "follow_up": _aggregate_named_counts(
            source.get("follow_up"),
            allowed_names=set(LEARNING_FOLLOW_UP_VALUES),
        ),
    }


def _browser_learning_groups(value: Any, *, allowed_names: tuple[str, ...]) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        name: _browser_learning_group(source.get(name))
        for name in allowed_names
        if isinstance(source.get(name), dict)
    }


def _browser_learning_aggregates(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    owner_source = source.get("owner_decisions") if isinstance(source.get("owner_decisions"), dict) else {}
    return {
        "schema_version": "feezie_learning_aggregates/v1",
        "owner_decisions": {
            **_aggregate_count_projection(
                owner_source,
                allowed_keys={"edit_ratio_sample_size", "mean_owner_edit_ratio"},
            ),
            "counts": _aggregate_named_counts(
                owner_source.get("counts"),
                allowed_names={"approve", "revise", "park", "reject"},
            ),
        },
        "by_pillar": _browser_learning_groups(source.get("by_pillar"), allowed_names=LEARNING_PILLAR_IDS),
        "by_treatment": _browser_learning_groups(source.get("by_treatment"), allowed_names=LEARNING_TREATMENTS),
        "by_hook_family": _browser_learning_groups(source.get("by_hook_family"), allowed_names=LEARNING_HOOK_FAMILIES),
        "by_format": _browser_learning_groups(source.get("by_format"), allowed_names=LEARNING_FORMATS),
    }


_BROWSER_GAP_COPY = {
    "feezie_metrics_24h_due": "Record the due 24-hour aggregate metrics in the private evidence recorder.",
    "feezie_metrics_7d_due": "Record the due 7-day aggregate metrics in the private evidence recorder.",
    "feezie_publication_evidence_empty": "Confirm a publication only after an owner-approved exact version is live.",
    "feezie_portfolio_mix_sourcing_warning": "Use mix deficits only to sequence qualified evidence; never create filler.",
}


def build_browser_performance_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Project private performance truth to aggregate counts and state only.

    This intentionally does not copy per-publication rows, URLs, content IDs,
    content digests, metric snapshots, notes, audience identities, or copy.
    """

    if not isinstance(summary, dict):
        return None
    counts = _aggregate_count_projection(
        summary.get("counts"),
        allowed_keys={
            "events",
            "owner_decisions",
            "confirmed_publications",
            "approved_unpublished",
            "owner_assessments",
            "complete_feedback_posts",
        },
    )
    completeness: dict[str, dict[str, Any]] = {}
    feedback_source = (
        summary.get("feedback_completeness")
        if isinstance(summary.get("feedback_completeness"), dict)
        else {}
    )
    for event_type in ("metrics_24h_recorded", "metrics_7d_recorded"):
        source = feedback_source.get(event_type)
        completeness[event_type] = _aggregate_count_projection(
            source,
            allowed_keys={"due", "complete", "missing", "not_due", "invalid_early", "completion_rate"},
        )

    pilot_source = summary.get("initial_pilot") if isinstance(summary.get("initial_pilot"), dict) else {}
    pilot = {
        **_aggregate_count_projection(
            pilot_source,
            allowed_keys={"target_count", "confirmed_count", "target_count_reached", "treatment_mix_complete"},
        ),
        "id": _safe_projection_text(
            pilot_source.get("id"),
            limit=120,
            allowed={"initial_six_post_pilot"},
        ),
        "status": _safe_projection_text(
            pilot_source.get("status"),
            limit=80,
            allowed={"in_progress", "complete", "insufficient_sample"},
        ),
        "targets": _aggregate_named_counts(
            pilot_source.get("targets"),
            allowed_names={
                "practical_ai_systems",
                "education_or_trust",
                "operator_story_personal_technology",
                "operator_story_education_community",
            },
        ),
        "counts": _aggregate_named_counts(
            pilot_source.get("counts"),
            allowed_names={
                "practical_ai_systems",
                "education_or_trust",
                "operator_story_personal_technology",
                "operator_story_education_community",
            },
        ),
        "deficits": _aggregate_named_counts(
            pilot_source.get("deficits"),
            allowed_names={
                "practical_ai_systems",
                "education_or_trust",
                "operator_story_personal_technology",
                "operator_story_education_community",
            },
        ),
        "quota_behavior": "warn_without_filler",
    }
    primary_source = summary.get("primary_kpi") if isinstance(summary.get("primary_kpi"), dict) else {}
    primary_kpi = {
        **_aggregate_count_projection(
            primary_source,
            allowed_keys={
                "assessed_posts",
                "meaningful_target_audience_conversations",
                "value_per_10_assessed_posts",
            },
        ),
        "id": _safe_projection_text(
            primary_source.get("id"),
            limit=120,
            allowed={"meaningful_target_audience_conversations_per_10_assessed_posts"},
        ),
        "status": _safe_projection_text(
            primary_source.get("status"),
            limit=80,
            allowed={"measured", "insufficient_sample"},
        ),
    }
    learning_source = summary.get("learning_gate") if isinstance(summary.get("learning_gate"), dict) else {}
    learning_gate = {
        **_aggregate_count_projection(
            learning_source,
            allowed_keys={
                "minimum_owner_decisions",
                "minimum_confirmed_publications",
                "minimum_complete_feedback_posts",
                "advisory_learning_enabled",
                "contract_change_evidence_ready",
            },
        ),
        "state": _safe_projection_text(
            learning_source.get("state"),
            limit=80,
            allowed={"advisory_ready", "insufficient_sample"},
        ) or "insufficient_sample",
    }
    gaps: list[dict[str, Any]] = []
    raw_gaps = summary.get("actionable_gaps") if isinstance(summary.get("actionable_gaps"), list) else []
    for raw_gap in raw_gaps[:12]:
        if not isinstance(raw_gap, dict):
            continue
        code = _safe_projection_text(raw_gap.get("code"), limit=120)
        if code not in _BROWSER_GAP_COPY:
            continue
        gaps.append(
            {
                "code": code,
                "severity": _safe_projection_text(
                    raw_gap.get("severity"),
                    limit=40,
                    allowed={"info", "yellow", "red"},
                ) or "info",
                "actionable": bool(raw_gap.get("actionable")),
                "next_action": _BROWSER_GAP_COPY[code],
            }
        )
    strategy_source = summary.get("strategy_contract") if isinstance(summary.get("strategy_contract"), dict) else {}
    return {
        "schema_version": SUMMARY_SCHEMA,
        "generated_at": _safe_projection_iso(summary.get("generated_at")),
        "workspace_key": CANONICAL_WORKSPACE_KEY,
        "strategy_contract": {
            "schema_version": _safe_projection_text(
                strategy_source.get("schema_version"),
                limit=120,
                allowed={"feezie_strategy_contract/v1"},
            ),
            "contract_hash": (
                str(strategy_source.get("contract_hash")).lower()
                if re.fullmatch(r"[a-fA-F0-9]{64}", str(strategy_source.get("contract_hash") or ""))
                else None
            ),
        },
        "counts": counts,
        "feedback_completeness": completeness,
        "rolling_topic_mix": _mix_browser_projection(
            summary.get("rolling_topic_mix"),
            allowed_names={"ai_native", "leadership_operator", "trust_systems"},
        ),
        "rolling_intent_mix": _mix_browser_projection(
            summary.get("rolling_intent_mix"),
            allowed_names={"value", "invitation", "personal"},
        ),
        "initial_pilot": pilot,
        "primary_kpi": primary_kpi,
        "learning_gate": learning_gate,
        "learning_aggregates": _browser_learning_aggregates(summary.get("learning_aggregates")),
        "actionable_gaps": gaps,
        "data_policy": {
            "aggregate_only": True,
            "per_publication_rows_included": False,
            "external_post_links_included": False,
            "raw_metric_snapshots_included": False,
            "private_notes_included": False,
            "audience_identities_included": False,
            "raw_copy_included": False,
        },
    }


class LinkedinPerformanceLedgerService:
    def __init__(
        self,
        *,
        state_root: Path | None = None,
        repo_root: Path | None = None,
        snapshot_writer: Any = upsert_snapshot,
    ) -> None:
        self.state_root = (
            state_root
            or Path(os.getenv("AI_CLONE_STATE_ROOT") or (Path.home() / ".codex" / "ai-clone" / "state"))
        ).expanduser().resolve()
        self.repo_root = (repo_root or REPO_ROOT).expanduser().resolve()
        self.snapshot_writer = snapshot_writer

    @property
    def events_path(self) -> Path:
        return workspace_state_path(
            CANONICAL_WORKSPACE_KEY,
            EVENTS_RELATIVE_PATH,
            state_root=self.state_root,
        )

    @property
    def summary_path(self) -> Path:
        return workspace_state_path(
            CANONICAL_WORKSPACE_KEY,
            SUMMARY_RELATIVE_PATH,
            state_root=self.state_root,
        )

    def _read_paths(self) -> tuple[Path, ...]:
        paths = [self.events_path]
        paths.extend(
            workspace_state_path(key, EVENTS_RELATIVE_PATH, state_root=self.state_root)
            for key in COMPATIBILITY_WORKSPACE_KEYS
        )
        paths.append(self.repo_root / "workspaces" / "linkedin-content-os" / EVENTS_RELATIVE_PATH)
        return tuple(dict.fromkeys(path.resolve(strict=False) for path in paths))

    def _validate_regular_file(self, path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise LinkedinPerformanceLedgerError(f"Unable to inspect ledger path: {path.name}") from exc
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise LinkedinPerformanceLedgerError("Publication ledger target must be a regular, non-symlink file.")

    def _read_path_strict(self, path: Path) -> list[dict[str, Any]]:
        self._validate_regular_file(path)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line, object_pairs_hook=_json_object_without_duplicate_keys)
            except json.JSONDecodeError as exc:
                raise LinkedinPerformanceLedgerCorruption(
                    f"Publication ledger contains invalid JSON at {path.name}:{line_number}."
                ) from exc
            if not isinstance(event, dict) or event.get("schema_version") != EVENT_SCHEMA:
                raise LinkedinPerformanceLedgerCorruption(
                    f"Publication ledger contains an unsupported row at {path.name}:{line_number}."
                )
            required = {
                "event_id",
                "idempotency_key",
                "payload_sha256",
                "event_type",
                "workspace_key",
                "content_id",
                "content_version_sha256",
                "occurred_at",
                "recorded_at",
                "strategy_contract",
                "data",
            }
            if not required.issubset(event) or event.get("workspace_key") != CANONICAL_WORKSPACE_KEY:
                raise LinkedinPerformanceLedgerCorruption(
                    f"Publication ledger row is incomplete at {path.name}:{line_number}."
                )
            if event.get("event_type") not in EVENT_TYPES:
                raise LinkedinPerformanceLedgerCorruption(
                    f"Publication ledger row has an unsupported event type at {path.name}:{line_number}."
                )
            _parse_iso(event.get("occurred_at"), field="occurred_at")
            _parse_iso(event.get("recorded_at"), field="recorded_at")
            events.append(event)
        return events

    def load_events(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for path in self._read_paths():
            for event in self._read_path_strict(path):
                event_id = str(event.get("event_id") or "")
                current = by_id.get(event_id)
                if current is not None and current != event:
                    raise LinkedinPerformanceLedgerCorruption(
                        f"Publication event {event_id} differs across compatibility roots."
                    )
                by_id[event_id] = event
        return sorted(
            by_id.values(),
            key=lambda event: (str(event.get("recorded_at") or ""), str(event.get("event_id") or "")),
        )

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        parent = self.events_path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = parent / ".linkedin_publication_events.lock"
        self._validate_regular_file(lock_path)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            os.chmod(lock_path, 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise LinkedinPerformanceLedgerError("Publication ledger lock is not a regular file.")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _append_line(self, event: dict[str, Any]) -> None:
        self._validate_regular_file(self.events_path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.events_path, flags, 0o600)
        try:
            os.chmod(self.events_path, 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise LinkedinPerformanceLedgerError("Publication ledger is not a regular file.")
            payload = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _atomic_write_summary(self, summary: dict[str, Any]) -> None:
        parent = self.summary_path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = parent / f".{self.summary_path.name}.{os.getpid()}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        try:
            rendered = (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            view = memoryview(rendered)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, self.summary_path)
        os.chmod(self.summary_path, 0o600)

    def build_projection_status(
        self,
        summary: dict[str, Any] | None,
        *,
        now: datetime | None = None,
        state_override: str | None = None,
        error_type: str | None = None,
        source: str = "local_ledger",
    ) -> dict[str, Any]:
        """Build a content-minimized health contract for the secondary projection."""

        checked_at = (now or _now_utc()).astimezone(timezone.utc).replace(microsecond=0)
        allowed_overrides = {"missing", "degraded", "corrupt"}
        if state_override is not None and state_override not in allowed_overrides:
            raise LinkedinPerformanceLedgerError("Unsupported publication projection status override.")

        generated_at: str | None = None
        age_hours: float | None = None
        counts = summary.get("counts") if isinstance(summary, dict) and isinstance(summary.get("counts"), dict) else {}
        if state_override:
            state = state_override
        elif not isinstance(summary, dict):
            state = "missing"
        else:
            try:
                generated = _parse_iso(summary.get("generated_at"), field="generated_at")
            except LinkedinPerformanceLedgerCorruption:
                state = "corrupt"
            else:
                generated_at = generated.replace(microsecond=0).isoformat()
                future_skew_hours = (generated - checked_at).total_seconds() / 3600
                if future_skew_hours > 1:
                    state = "corrupt"
                else:
                    age_hours = round(max(0.0, (checked_at - generated).total_seconds() / 3600), 2)
                    state = "stale" if age_hours > PERFORMANCE_PROJECTION_STALE_AFTER_HOURS else "fresh"

        recent = summary.get("recent_publications") if isinstance(summary, dict) else None
        latest_publication_at = None
        if isinstance(recent, list):
            latest = next((item for item in recent if isinstance(item, dict) and item.get("published_at")), None)
            if latest is not None:
                latest_publication_at = str(latest.get("published_at") or "")[:80] or None

        return {
            "schema_version": STATUS_SCHEMA,
            "checked_at": checked_at.isoformat(),
            "workspace_key": CANONICAL_WORKSPACE_KEY,
            "state": state,
            "availability": "available" if isinstance(summary, dict) else "unavailable",
            "projection_generated_at": generated_at,
            "projection_age_hours": age_hours,
            "stale_after_hours": PERFORMANCE_PROJECTION_STALE_AFTER_HOURS,
            "evidence": {
                "event_count": int(counts.get("events") or 0),
                "confirmed_publications": int(counts.get("confirmed_publications") or 0),
                "latest_publication_at": latest_publication_at,
                "state": "present" if int(counts.get("events") or 0) > 0 else "empty",
            },
            "source": _clean_text(source)[:80] or "local_ledger",
            "error_type": _clean_text(error_type)[:120] or None,
            "data_policy": {
                "aggregate_only": True,
                "raw_event_content_included": False,
                "private_notes_included": False,
            },
        }

    def build_lifecycle_projection(
        self,
        content_id: Any,
        content_version_sha256: Any,
        *,
        events: list[dict[str, Any]] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Build the non-listable Railway receipt for one exact identity."""

        normalized_content_id = _clean_text(content_id)
        normalized_digest = _normalize_hash(content_version_sha256)
        identity_token = linkedin_performance_identity_token(normalized_content_id, normalized_digest)
        active = _active_events(list(events if events is not None else self.load_events()))
        exact = [
            event
            for event in active
            if event.get("content_id") == normalized_content_id
            and event.get("content_version_sha256") == normalized_digest
        ]
        approved = any(
            event.get("event_type") == "owner_reviewed"
            and (event.get("data") or {}).get("decision") == "approve"
            for event in exact
        )
        publications = sorted(
            (event for event in exact if event.get("event_type") == "publication_confirmed"),
            key=lambda event: (str(event.get("occurred_at") or ""), str(event.get("event_id") or "")),
        )
        publication = publications[-1] if publications else None
        publication_data = (publication or {}).get("data")
        if not isinstance(publication_data, dict):
            publication_data = {}
        published_at = _clean_text(publication_data.get("published_at")) or None
        return {
            "schema_version": LIFECYCLE_PROJECTION_SCHEMA,
            "generated_at": (now or _now_utc()).astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            "workspace_key": CANONICAL_WORKSPACE_KEY,
            "identity_token": identity_token,
            "approval_completed": approved or publication is not None,
            "publication_confirmed": publication is not None,
            "published_at": published_at,
            "data_policy": {
                "exact_identity_only": True,
                "identity_token_is_one_way": True,
                "content_id_included": False,
                "content_version_sha256_included": False,
                "external_post_link_included": False,
                "raw_metrics_included": False,
                "private_notes_included": False,
                "audience_identities_included": False,
                "raw_copy_included": False,
            },
        }

    def _persist_projection(
        self,
        summary: dict[str, Any],
        lifecycle_projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Best-effort secondary mirror; canonical local append never depends on it."""

        if self.snapshot_writer is None:
            return {"status": "disabled"}
        try:
            browser_summary = build_browser_performance_summary(summary)
            if browser_summary is None:
                raise LinkedinPerformanceLedgerError("Publication summary could not be minimized for projection.")
            stored_summary = self.snapshot_writer(
                CANONICAL_WORKSPACE_KEY,
                SNAPSHOT_TYPE,
                browser_summary,
                metadata={"source": "linkedin_performance_ledger_service"},
            )
            stored_status = self.snapshot_writer(
                CANONICAL_WORKSPACE_KEY,
                STATUS_SNAPSHOT_TYPE,
                self.build_projection_status(summary),
                metadata={"source": "linkedin_performance_ledger_service"},
            )
            stored_lifecycle = None
            if lifecycle_projection is not None:
                stored_lifecycle = self.snapshot_writer(
                    LIFECYCLE_PROJECTION_WORKSPACE_KEY,
                    linkedin_performance_lifecycle_snapshot_type(lifecycle_projection.get("identity_token")),
                    lifecycle_projection,
                    metadata={"source": "linkedin_performance_ledger_service"},
                )
        except Exception as exc:
            return {"status": "degraded", "error_type": type(exc).__name__}
        all_stored = stored_summary is not None and stored_status is not None and (
            lifecycle_projection is None or stored_lifecycle is not None
        )
        return {
            "status": "stored" if all_stored else "unavailable",
            "summary_snapshot": "stored" if stored_summary is not None else "unavailable",
            "status_snapshot": "stored" if stored_status is not None else "unavailable",
            "lifecycle_snapshot": (
                "stored" if stored_lifecycle is not None else "unavailable"
            ) if lifecycle_projection is not None else "not_requested",
        }

    def _contract(self) -> dict[str, Any]:
        return load_feezie_strategy_contract(self.repo_root)

    def _prepare_event(self, raw_payload: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        payload = _jsonable(raw_payload)
        event_type = _clean_text(payload.get("event_type"))
        if event_type not in EVENT_TYPES:
            raise LinkedinPerformanceLedgerError(f"Unsupported publication event type: {event_type!r}")
        idempotency_key = _clean_text(payload.get("idempotency_key"))
        content_id = _clean_text(payload.get("content_id"))
        if not idempotency_key or not content_id:
            raise LinkedinPerformanceLedgerError("idempotency_key and content_id are required.")

        occurred_at = _parse_iso(payload.get("occurred_at"), field="occurred_at")
        copy_text = payload.pop("copy_text", None)
        supplied_hash = payload.get("content_version_sha256")
        if copy_text:
            computed_hash = _hash_copy(str(copy_text))
            if supplied_hash and _normalize_hash(supplied_hash) != computed_hash:
                raise LinkedinPerformanceLedgerConflict("copy_text does not match content_version_sha256.")
            content_hash = computed_hash
        elif supplied_hash:
            content_hash = _normalize_hash(supplied_hash)
        else:
            raise LinkedinPerformanceLedgerError(
                "copy_text or content_version_sha256 is required so approval and publication can be matched exactly."
            )

        contract = self._contract()
        positioning = contract["positioning"]
        editorial = contract["editorial_mix"]
        pillar_ids = {str(item["id"]) for item in editorial["pillars"]}
        active = _active_events(events)
        active_publications = [event for event in active if event.get("event_type") == "publication_confirmed"]
        matching_publication = next(
            (
                event
                for event in reversed(active_publications)
                if event.get("content_id") == content_id and event.get("content_version_sha256") == content_hash
            ),
            None,
        )

        data: dict[str, Any]
        publication_id: str | None = None
        if event_type == "owner_reviewed":
            decision = _clean_text(payload.get("owner_decision"))
            if decision not in {"approve", "revise", "park", "reject"}:
                raise LinkedinPerformanceLedgerError("owner_reviewed requires an owner_decision.")
            data = {
                "decision": decision,
                "approval_ref": _logical_ref(payload.get("approval_ref"), field="approval_ref"),
                "owner_edit_minutes": payload.get("owner_edit_minutes"),
                "owner_edit_ratio": payload.get("owner_edit_ratio"),
                "notes": _clean_text(payload.get("notes")) or None,
            }
        elif event_type == "publication_confirmed":
            if payload.get("confirmed") is not True:
                raise LinkedinPerformanceLedgerError("publication_confirmed requires confirmed=true.")
            approved = next(
                (
                    event
                    for event in reversed(active)
                    if event.get("event_type") == "owner_reviewed"
                    and event.get("content_id") == content_id
                    and event.get("content_version_sha256") == content_hash
                    and (event.get("data") or {}).get("decision") == "approve"
                ),
                None,
            )
            if approved is None:
                raise LinkedinPerformanceLedgerError(
                    "Exact approved-copy evidence is required before publication can be confirmed."
                )
            publication_url = normalize_linkedin_publication_url(payload.get("publication_url"))
            published_at = _parse_iso(payload.get("published_at"), field="published_at")
            if published_at > occurred_at:
                raise LinkedinPerformanceLedgerError("published_at cannot be later than occurred_at.")
            approved_at = _parse_iso(approved.get("occurred_at"), field="approval occurred_at")
            if approved_at > published_at:
                raise LinkedinPerformanceLedgerError(
                    "Exact approved-copy evidence must occur on or before published_at."
                )
            confirmation_method = _clean_text(payload.get("confirmation_method"))
            if confirmation_method not in {"manual_url", "opened_post", "screenshot", "authorized_export"}:
                raise LinkedinPerformanceLedgerError("publication_confirmed requires a supported confirmation_method.")
            pillar_id = _clean_text(payload.get("pillar_id"))
            if pillar_id not in pillar_ids:
                raise LinkedinPerformanceLedgerError("publication_confirmed requires a canonical pillar_id.")
            intent = normalize_feezie_intent(payload.get("intent"))
            career_signal = _clean_text(payload.get("career_signal"))
            employer_safety = _clean_text(payload.get("employer_safety"))
            proof_posture = _clean_text(payload.get("proof_posture"))
            if career_signal not in set(positioning["career_signal_values"]):
                raise LinkedinPerformanceLedgerError("publication_confirmed requires a canonical career_signal.")
            if employer_safety not in set(positioning["employer_safety_values"]) or employer_safety == "blocked":
                raise LinkedinPerformanceLedgerError("Blocked or unknown employer safety cannot be confirmed as published.")
            if proof_posture not in set(positioning["proof_posture_values"]) or proof_posture == "missing":
                raise LinkedinPerformanceLedgerError("Missing or unknown proof posture cannot be confirmed as published.")
            treatment = _clean_text(payload.get("treatment"))
            experiment_id = _clean_text(payload.get("experiment_id")) or None
            pilot = editorial["measurement"]["initial_pilot"]
            if experiment_id == pilot["id"] and treatment not in set(pilot["treatments"]):
                raise LinkedinPerformanceLedgerError("Initial-pilot publication has an unsupported treatment.")
            audience = [_clean_text(item) for item in payload.get("audience") or [] if _clean_text(item)]
            if not treatment or not audience:
                raise LinkedinPerformanceLedgerError("publication_confirmed requires treatment and intended audience.")
            publication_id = "linkedin_" + hashlib.sha256(publication_url.encode("utf-8")).hexdigest()[:24]
            data = {
                "publication_url": publication_url,
                "published_at": published_at.isoformat(),
                "confirmation_method": confirmation_method,
                "evidence_ref": _logical_ref(payload.get("evidence_ref"), field="evidence_ref"),
                "approval_event_id": approved["event_id"],
                "classification": {
                    "pillar_id": pillar_id,
                    "intent": intent,
                    "treatment": treatment,
                    "career_signal": career_signal,
                    "employer_safety": employer_safety,
                    "proof_posture": proof_posture,
                    "hook_family": _clean_text(payload.get("hook_family")) or "unknown",
                    "format": _clean_text(payload.get("format")) or "text",
                    "audience": audience,
                },
                "experiment_id": experiment_id,
            }
        elif event_type in {"metrics_24h_recorded", "metrics_7d_recorded"}:
            if matching_publication is None:
                raise LinkedinPerformanceLedgerError("Metrics require a confirmed publication for the exact content version.")
            published_at = _parse_iso(
                (matching_publication.get("data") or {}).get("published_at"),
                field="published_at",
            )
            observation_hours = int(editorial["measurement"]["observation_windows_hours"][event_type])
            earliest_observation_at = published_at + timedelta(hours=observation_hours)
            if occurred_at < earliest_observation_at:
                raise LinkedinPerformanceLedgerError(
                    f"{event_type} cannot be recorded before its {observation_hours}-hour observation window."
                )
            metrics = _safe_count_mapping(_jsonable(payload.get("metrics")))
            unavailable = sorted({_clean_text(item) for item in payload.get("unavailable_metrics") or [] if _clean_text(item)})
            if not any(value is not None for value in metrics.values()) and not unavailable:
                raise LinkedinPerformanceLedgerError("Metrics require at least one value or an explicit unavailable_metrics list.")
            source = _clean_text(payload.get("metric_source"))
            if source not in {"manual_linkedin_analytics", "authorized_export"}:
                raise LinkedinPerformanceLedgerError("Metrics require a supported metric_source.")
            publication_id = str(matching_publication.get("publication_id") or "")
            data = {
                "observed_at": occurred_at.isoformat(),
                "metrics": metrics,
                "unavailable_metrics": unavailable,
                "source": source,
                "notes": _clean_text(payload.get("notes")) or None,
            }
            contract = matching_publication["strategy_contract"]
        else:
            if matching_publication is None:
                raise LinkedinPerformanceLedgerError("Owner assessment requires a confirmed publication for the exact content version.")
            published_at = _parse_iso(
                (matching_publication.get("data") or {}).get("published_at"),
                field="published_at",
            )
            if occurred_at < published_at:
                raise LinkedinPerformanceLedgerError("Owner assessment cannot occur before published_at.")
            meaningful = payload.get("meaningful_target_conversations")
            outcome_counts = _safe_count_mapping(_jsonable(payload.get("outcome_counts")))
            sounded_like_me = _clean_text(payload.get("sounded_like_me")) or None
            quality_flags = sorted({_clean_text(item) for item in payload.get("quality_flags") or [] if _clean_text(item)})
            follow_up = _clean_text(payload.get("follow_up")) or None
            if meaningful is None and not outcome_counts and sounded_like_me is None and not quality_flags and not follow_up:
                raise LinkedinPerformanceLedgerError("Owner assessment requires at least one qualitative or outcome field.")
            publication_id = str(matching_publication.get("publication_id") or "")
            data = {
                "observed_at": occurred_at.isoformat(),
                "meaningful_target_conversations": meaningful,
                "outcome_counts": outcome_counts,
                "sounded_like_me": sounded_like_me,
                "quality_flags": quality_flags,
                "follow_up": follow_up,
                "notes": _clean_text(payload.get("notes")) or None,
            }
            contract = matching_publication["strategy_contract"]

        semantic_payload = {
            "schema_version": EVENT_SCHEMA,
            "event_type": event_type,
            "workspace_key": CANONICAL_WORKSPACE_KEY,
            "content_id": content_id,
            "content_version_sha256": content_hash,
            "publication_id": publication_id,
            "occurred_at": occurred_at.isoformat(),
            "actor": "owner",
            "supersedes_event_id": _clean_text(payload.get("supersedes_event_id")) or None,
            "strategy_contract": {
                "schema_version": contract["schema_version"],
                "contract_hash": contract["contract_hash"],
            },
            "data": data,
        }
        payload_hash = _semantic_hash(semantic_payload)
        return {
            **semantic_payload,
            "event_id": "lpe_" + hashlib.sha256(
                f"{CANONICAL_WORKSPACE_KEY}:{idempotency_key}".encode("utf-8")
            ).hexdigest()[:32],
            "idempotency_key": idempotency_key,
            "payload_sha256": payload_hash,
            "recorded_at": _now_utc().replace(microsecond=0).isoformat(),
        }

    def append_event(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        with self._exclusive_lock():
            events = self.load_events()
            candidate = self._prepare_event(raw_payload, events)
            replay = next(
                (event for event in events if event.get("idempotency_key") == candidate["idempotency_key"]),
                None,
            )
            if replay is not None:
                if replay.get("payload_sha256") != candidate["payload_sha256"]:
                    raise LinkedinPerformanceLedgerConflict(
                        "The idempotency key already exists with different publication evidence."
                    )
                summary = self.build_summary(events)
                self._atomic_write_summary(summary)
                lifecycle_projection = self.build_lifecycle_projection(
                    replay.get("content_id"),
                    replay.get("content_version_sha256"),
                    events=events,
                )
                return {
                    "created": False,
                    "event": replay,
                    "summary": summary,
                    "lifecycle_projection": lifecycle_projection,
                    "projection_mirror": self._persist_projection(summary, lifecycle_projection),
                }

            supersedes_id = candidate.get("supersedes_event_id")
            active = _active_events(events)
            active_same_slot = [event for event in active if _event_slot(event) == _event_slot(candidate)]
            if supersedes_id:
                target = next((event for event in active if event.get("event_id") == supersedes_id), None)
                if target is None:
                    raise LinkedinPerformanceLedgerConflict("supersedes_event_id is missing or already superseded.")
                if target.get("event_type") != candidate.get("event_type") or _event_slot(target) != _event_slot(candidate):
                    raise LinkedinPerformanceLedgerConflict("A correction may supersede only the active event in the same lifecycle slot.")
            elif active_same_slot:
                raise LinkedinPerformanceLedgerConflict(
                    "This lifecycle slot already has active evidence; submit an explicit superseding correction."
                )

            self._append_line(candidate)
            updated_events = [*events, candidate]
            summary = self.build_summary(updated_events)
            self._atomic_write_summary(summary)
            lifecycle_projection = self.build_lifecycle_projection(
                candidate.get("content_id"),
                candidate.get("content_version_sha256"),
                events=updated_events,
            )
            return {
                "created": True,
                "event": candidate,
                "summary": summary,
                "lifecycle_projection": lifecycle_projection,
                "projection_mirror": self._persist_projection(summary, lifecycle_projection),
            }

    def _mix_summary(
        self,
        publications: list[dict[str, Any]],
        *,
        field: str,
        window: int,
        targets: dict[str, int],
    ) -> dict[str, Any]:
        sample = publications[-window:]
        counts = {key: 0 for key in targets}
        for publication in sample:
            classification = (publication.get("data") or {}).get("classification") or {}
            value = _clean_text(classification.get(field))
            if value in counts:
                counts[value] += 1
        return {
            "window": window,
            "sample_size": len(sample),
            "status": "measured" if len(sample) == window else "insufficient_sample",
            "targets": targets,
            "counts": counts,
            "deficits": {key: max(0, target - counts.get(key, 0)) for key, target in targets.items()},
            "quota_behavior": "warn_without_filler",
        }

    def build_summary(self, events: list[dict[str, Any]] | None = None, *, now: datetime | None = None) -> dict[str, Any]:
        all_events = list(events if events is not None else self.load_events())
        active = _active_events(all_events)
        now_utc = (now or _now_utc()).astimezone(timezone.utc)
        contract = self._contract()
        editorial = contract["editorial_mix"]
        measurement = editorial["measurement"]
        active_publications = sorted(
            [event for event in active if event.get("event_type") == "publication_confirmed"],
            key=lambda event: (
                _parse_iso((event.get("data") or {}).get("published_at"), field="published_at"),
                str(event.get("event_id") or ""),
            ),
        )
        publication_by_id = {str(event.get("publication_id")): event for event in active_publications}
        events_by_publication: dict[str, dict[str, dict[str, Any]]] = {}
        for event in active:
            publication_id = _clean_text(event.get("publication_id"))
            if not publication_id or publication_id not in publication_by_id:
                continue
            events_by_publication.setdefault(publication_id, {})[str(event.get("event_type"))] = event

        windows = measurement["observation_windows_hours"]
        metric_window_validity: dict[str, dict[str, dict[str, bool]]] = {}
        for publication in active_publications:
            publication_id = str(publication.get("publication_id") or "")
            published_at = _parse_iso((publication.get("data") or {}).get("published_at"), field="published_at")
            attached = events_by_publication.get(publication_id, {})
            publication_validity: dict[str, dict[str, bool]] = {}
            for event_type in ("metrics_24h_recorded", "metrics_7d_recorded"):
                metric_event = attached.get(event_type)
                if metric_event is None:
                    publication_validity[event_type] = {"present": False, "valid": False}
                    continue
                observed_at = _parse_iso(
                    (metric_event.get("data") or {}).get("observed_at") or metric_event.get("occurred_at"),
                    field="observed_at",
                )
                publication_validity[event_type] = {
                    "present": True,
                    "valid": observed_at >= published_at + timedelta(hours=int(windows[event_type])),
                }
            metric_window_validity[publication_id] = publication_validity

        completeness: dict[str, dict[str, int | float | None]] = {}
        recent: list[dict[str, Any]] = []
        complete_feedback_posts = 0
        for event_type in ("metrics_24h_recorded", "metrics_7d_recorded"):
            due = complete = not_due = invalid_early = 0
            hours = int(windows[event_type])
            for publication in active_publications:
                publication_id = str(publication.get("publication_id") or "")
                published_at = _parse_iso((publication.get("data") or {}).get("published_at"), field="published_at")
                is_due = now_utc >= published_at + timedelta(hours=hours)
                event_state = metric_window_validity.get(publication_id, {}).get(event_type, {})
                has_event = event_state.get("valid") is True
                invalid_early += int(event_state.get("present") is True and not has_event)
                if is_due:
                    due += 1
                    complete += int(has_event)
                else:
                    not_due += 1
            completeness[event_type] = {
                "due": due,
                "complete": complete,
                "missing": due - complete,
                "not_due": not_due,
                "invalid_early": invalid_early,
                "completion_rate": round(complete / due, 3) if due else None,
            }

        assessment_events: list[dict[str, Any]] = []
        for publication in active_publications:
            publication_id = str(publication.get("publication_id") or "")
            attached = events_by_publication.get(publication_id, {})
            validity = metric_window_validity.get(publication_id, {})
            has_24h = (validity.get("metrics_24h_recorded") or {}).get("valid") is True
            has_7d = (validity.get("metrics_7d_recorded") or {}).get("valid") is True
            if has_24h and has_7d:
                complete_feedback_posts += 1
            assessment = attached.get("owner_assessment_recorded")
            if assessment:
                assessment_events.append(assessment)
            data = publication.get("data") or {}
            classification = data.get("classification") or {}
            published_at = _parse_iso(data.get("published_at"), field="published_at")
            due_actions: list[str] = []
            if now_utc >= published_at + timedelta(hours=int(windows["metrics_24h_recorded"])) and not has_24h:
                due_actions.append("record_24h_metrics")
            if now_utc >= published_at + timedelta(hours=int(windows["metrics_7d_recorded"])) and not has_7d:
                due_actions.append("record_7d_metrics")
            if not assessment:
                due_actions.append("record_owner_assessment")
            recent.append(
                {
                    "publication_id": publication_id,
                    "content_id": publication.get("content_id"),
                    "publication_url": data.get("publication_url"),
                    "published_at": data.get("published_at"),
                    "pillar_id": classification.get("pillar_id"),
                    "intent": classification.get("intent"),
                    "treatment": classification.get("treatment"),
                    "career_signal": classification.get("career_signal"),
                    "proof_posture": classification.get("proof_posture"),
                    "hook_family": classification.get("hook_family"),
                    "format": classification.get("format"),
                    "feedback_status": {
                        "metrics_24h_recorded": has_24h,
                        "metrics_7d_recorded": has_7d,
                        "owner_assessment_recorded": bool(assessment),
                    },
                    "due_actions": due_actions,
                }
            )

        owner_decisions = [event for event in active if event.get("event_type") == "owner_reviewed"]
        approved_versions = {
            (str(event.get("content_id")), str(event.get("content_version_sha256")))
            for event in owner_decisions
            if (event.get("data") or {}).get("decision") == "approve"
        }
        published_versions = {
            (str(event.get("content_id")), str(event.get("content_version_sha256")))
            for event in active_publications
        }
        topic_mix = self._mix_summary(
            active_publications,
            field="pillar_id",
            window=int(editorial["rolling_topic_mix"]["window"]),
            targets={str(key): int(value) for key, value in editorial["rolling_topic_mix"]["counts"].items()},
        )
        intent_mix = self._mix_summary(
            active_publications,
            field="intent",
            window=int(editorial["intent_mix"]["window"]),
            targets={str(key): int(value) for key, value in editorial["intent_mix"]["counts"].items()},
        )

        pilot = measurement["initial_pilot"]
        pilot_publications = [
            event
            for event in active_publications
            if (event.get("data") or {}).get("experiment_id") == pilot["id"]
        ]
        pilot_counts = {str(key): 0 for key in pilot["treatments"]}
        for publication in pilot_publications:
            treatment = _clean_text(((publication.get("data") or {}).get("classification") or {}).get("treatment"))
            if treatment in pilot_counts:
                pilot_counts[treatment] += 1
        pilot_deficits = {
            str(key): max(0, int(value) - pilot_counts.get(str(key), 0))
            for key, value in pilot["treatments"].items()
        }
        pilot_target_reached = len(pilot_publications) >= int(pilot["target_count"])
        pilot_treatment_mix_complete = not any(pilot_deficits.values())
        pilot_summary = {
            "id": pilot["id"],
            "target_count": int(pilot["target_count"]),
            "confirmed_count": len(pilot_publications),
            "status": "complete" if pilot_target_reached and pilot_treatment_mix_complete else "in_progress",
            "target_count_reached": pilot_target_reached,
            "treatment_mix_complete": pilot_treatment_mix_complete,
            "targets": {str(key): int(value) for key, value in pilot["treatments"].items()},
            "counts": pilot_counts,
            "deficits": pilot_deficits,
            "completion_rule": "target_count_reached_and_all_treatment_deficits_zero",
            "quota_behavior": "warn_without_filler",
        }

        assessed_count = len(assessment_events)
        meaningful_conversations = sum(
            int((event.get("data") or {}).get("meaningful_target_conversations") or 0)
            for event in assessment_events
        )
        primary_kpi = {
            "id": measurement["primary_kpi"],
            "assessed_posts": assessed_count,
            "meaningful_target_audience_conversations": meaningful_conversations,
            "value_per_10_assessed_posts": (
                round(meaningful_conversations * 10 / assessed_count, 2) if assessed_count else None
            ),
            "status": "measured" if assessed_count >= 10 else "insufficient_sample",
        }
        learning_gate = measurement["learning_gate"]
        advisory_ready = (
            len(owner_decisions) >= int(learning_gate["minimum_owner_decisions"])
            and len(active_publications) >= int(learning_gate["minimum_confirmed_publications"])
        )
        contract_change_ready = (
            advisory_ready
            and complete_feedback_posts >= int(learning_gate["minimum_complete_feedback_posts"])
        )
        learning_aggregates = _build_learning_aggregates(
            publications=active_publications,
            events_by_publication=events_by_publication,
            owner_decisions=owner_decisions,
        )

        gaps: list[dict[str, Any]] = []
        missing_24h = int(completeness["metrics_24h_recorded"]["missing"] or 0)
        missing_7d = int(completeness["metrics_7d_recorded"]["missing"] or 0)
        if missing_24h:
            gaps.append(
                {
                    "code": "feezie_metrics_24h_due",
                    "severity": "yellow",
                    "actionable": True,
                    "next_action": f"Record 24-hour metrics for {missing_24h} confirmed publication(s).",
                    "agenda_tags": ["feedback_learning", "execution_or_lifecycle"],
                    "relevant_roles": ["Jean-Claude"],
                }
            )
        if missing_7d:
            gaps.append(
                {
                    "code": "feezie_metrics_7d_due",
                    "severity": "yellow",
                    "actionable": True,
                    "next_action": f"Record 7-day metrics for {missing_7d} confirmed publication(s).",
                    "agenda_tags": ["feedback_learning", "execution_or_lifecycle"],
                    "relevant_roles": ["Jean-Claude"],
                }
            )
        if not active_publications:
            gaps.append(
                {
                    "code": "feezie_publication_evidence_empty",
                    "severity": "yellow",
                    "actionable": True,
                    "next_action": "After an owner-approved post is live, record its exact LinkedIn URL, timestamp, and copy digest.",
                    "agenda_tags": ["execution_or_lifecycle"],
                    "relevant_roles": ["Jean-Claude"],
                }
            )
        if any(topic_mix["deficits"].values()) or any(intent_mix["deficits"].values()):
            gaps.append(
                {
                    "code": "feezie_portfolio_mix_sourcing_warning",
                    "severity": "info",
                    "actionable": False,
                    "next_action": "Use deficits only to sequence qualified evidence; never create filler or bypass admission gates.",
                    "agenda_tags": ["informational_only"],
                    "relevant_roles": [],
                }
            )

        summary = {
            "schema_version": SUMMARY_SCHEMA,
            "generated_at": now_utc.replace(microsecond=0).isoformat(),
            "workspace_key": CANONICAL_WORKSPACE_KEY,
            "strategy_contract": {
                "schema_version": contract["schema_version"],
                "contract_hash": contract["contract_hash"],
            },
            "counts": {
                "events": len(active),
                "owner_decisions": len(owner_decisions),
                "confirmed_publications": len(active_publications),
                "approved_unpublished": len(approved_versions - published_versions),
                "owner_assessments": assessed_count,
                "complete_feedback_posts": complete_feedback_posts,
            },
            "feedback_completeness": completeness,
            "rolling_topic_mix": topic_mix,
            "rolling_intent_mix": intent_mix,
            "initial_pilot": pilot_summary,
            "primary_kpi": primary_kpi,
            "learning_gate": {
                **{str(key): int(value) for key, value in learning_gate.items()},
                "advisory_learning_enabled": advisory_ready,
                "contract_change_evidence_ready": contract_change_ready,
                "state": "advisory_ready" if advisory_ready else "insufficient_sample",
            },
            "learning_aggregates": learning_aggregates,
            "actionable_gaps": gaps,
            "recent_publications": recent[-10:][::-1],
            "publication_lifecycle_index": [
                {
                    "publication_id": item["publication_id"],
                    "content_id": item["content_id"],
                    "publication_url": item["publication_url"],
                    "published_at": item["published_at"],
                }
                for item in recent[-200:]
            ],
            "data_policy": {
                "canonical_writer": "private feezie-os append-only ledger",
                "excluded_from_projection": [
                    "raw_post_copy",
                    "private_notes",
                    "comment_or_dm_text",
                    "audience_identities",
                    "absolute_local_paths",
                ],
                "publication_truth_rule": "Only active publication_confirmed events count as published.",
            },
        }
        return summary

    def load_summary(self) -> dict[str, Any]:
        return self.build_summary()

    def latest_confirmed_publications(self) -> list[dict[str, Any]]:
        return list(self.load_summary().get("publication_lifecycle_index") or [])


linkedin_performance_ledger_service = LinkedinPerformanceLedgerService()
