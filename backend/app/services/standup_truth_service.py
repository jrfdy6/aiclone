from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid5

from app.models.automations import AutomationRun
from app.models.standups import StandupEntry
from app.security.execution_authorization import verify_execution_payload
from app.services.automation_run_service import list_runs
from app.services.brain_response_privacy_service import sanitize_brain_text
from app.services.execution_artifact_reference_service import (
    contains_private_filesystem_reference,
)
from app.services.workspace_registry_service import (
    REPO_ROOT,
    WORKSPACES_ROOT,
    canonicalize_workspace_key,
    workspace_registry_entry,
)
from app.utils.ai_clone_clock import resolve_payload_observation, utc_iso


STANDUP_FRESHNESS_HOURS = {
    "shared_ops": 12,
    "feezie-os": 36,
}
DEFAULT_STANDUP_FRESHNESS_HOURS = 72

MEETING_EVIDENCE_SCHEMA_VERSION = "standup_meeting_evidence/v1"
PARTICIPANT_REPORT_SCHEMA_VERSION = "standup_participant_report/v1"
ASYNC_ROLE_CONTRIBUTION_SCHEMA_VERSION = "standup_async_role_contribution/v1"
ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION = "standup_async_role_evidence/v1"
MEETING_RECORD_KIND = "standup"
WORKSPACE_CYCLE_PLAN_RECORD_KIND = "workspace_cycle_plan"
PARTICIPANT_REPORT_AUTOMATION_ID = "standup_participant_report"
PARTICIPANT_REPORT_PROVENANCE = "independent_codex_agent_run"
CANONICAL_MEETING_CLOSER = "Jean-Claude"
ROLE_CONTEXT_SCHEMA_VERSION = "standup_role_context/v1"
RATIFICATION_SCHEMA_VERSION = "standup_proposal_ratification/v1"
RATIFICATION_DISPOSITIONS = frozenset({"ratify_exact", "withhold"})
MEETING_PHASES = (
    (1, "status"),
    (2, "analysis"),
    (3, "commitments_resolution"),
)
IDENTITY_PACK_FILES = ("AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md", "CHARTER.md")
IDENTITY_PACK_DIGEST_PROJECTION_SCHEMA_VERSION = (
    "standup_identity_pack_digest_projection/v1"
)
IDENTITY_PACK_DIGEST_PROJECTION_PATH = (
    Path(__file__).resolve().parents[2]
    / "deployed_docs"
    / "standup_identity_pack_digests.json"
)
IDENTITY_PACK_DIGEST_PROJECTION_MAX_BYTES = 64 * 1024
MAX_REPORT_CONTENT_BYTES = 64 * 1024
MAX_PROMOTION_CLAIMS_BYTES = 256 * 1024
SYNTHETIC_ROLE_PROVENANCE = frozenset(
    {"deterministic_policy", "synthesized_lens", "synthesized_role_lens"}
)
_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_KNOWN_AGENT_PACKS = {
    "Jean-Claude": "jean-claude",
    "Neo": "neo",
    "Yoda": "yoda",
}
_SUCCESSFUL_RUN_STATUSES = frozenset({"ok", "success", "succeeded", "complete", "completed"})
_REPORT_POSITIONS = frozenset({"affirm", "challenge", "block", "no_eligible_change"})
_BASE_REPORT_CONTENT_FIELDS = frozenset(
    {
        "note",
        "evidence_refs",
        "position",
        "risks",
        "recommended_next_step",
        "owner_decision_required",
    }
)
_RATIFICATION_CONTENT_FIELDS = frozenset({"proposal_disposition", "ratification_reason"})

# A standup prep is intentionally rich local operating context.  Railway is a
# bounded control plane, not a second copy of private workspace strategy.  The
# fields below are therefore never part of a standup promotion, participant
# claim, recommendation request, or derived PM payload sent to Railway.  The
# sole remote copy of the four owner-facing goal fields is the existing Ops
# standup projection.
_REMOTE_PRIVATE_GOAL_KEYS = frozenset(
    {
        "goal",
        "workspace_goal",
        "goal_contract",
        "goal_contract_authority_sha256",
        "goal_contract_observed_at",
        "goal_contract_source_path",
        "progress_signals",
        "phase_gate",
        "no_action_trigger",
        "safe_internal_boundary",
        "owner_required_boundary",
        "authority_refs",
        "matched_goal_terms",
    }
)
_REMOTE_PRIVATE_EXCERPT_KEYS = frozenset(
    {
        "body",
        "content",
        "excerpt",
        "excerpts",
        "findings",
        "inferred_excerpt",
        "private_excerpt",
        "private_excerpts",
        "private_notes",
        "raw_body",
        "raw_content",
        "raw_excerpt",
        "recommendation",
        "supporting_signal",
    }
)
_REMOTE_LOCAL_REFERENCE_KEYS = frozenset(
    {
        "charter_path",
        "conversation_path",
        "identity_path",
        "inferred_brief_path",
        "recommendation_path",
        "reference_artifacts",
        "soul_path",
        "source_path",
        "source_paths",
        "user_path",
    }
)
_REMOTE_STRATEGY_FIELDS = frozenset(
    {
        "display_name",
        "goal_contract_authority_state",
        "goal_contract_fallback_applied",
        "goal_contract_status",
        "strategy_authority",
    }
)
_REMOTE_PRIOR_STANDUP_FIELDS = frozenset(
    {
        "created_at",
        "cycle_id",
        "id",
        "meeting_held",
        "record_kind",
        "standup_kind",
        "status",
        "workspace_key",
    }
)
_REMOTE_PM_CARD_FIELDS = frozenset(
    {
        "created_at",
        "effective_state",
        "id",
        "owner",
        "status",
        "title",
        "updated_at",
        "workspace_key",
    }
)
_DROP_REMOTE_VALUE = object()
_PRIVATE_OVERLAP_WORDS = 5
_PRIVATE_OVERLAP_GENERIC_WORDS = frozenset(
    {
        "a",
        "action",
        "agent",
        "ai",
        "an",
        "and",
        "approved",
        "at",
        "automatic",
        "affirm",
        "bounded",
        "block",
        "by",
        "canonical",
        "challenge",
        "clone",
        "context",
        "decision",
        "do",
        "evidence",
        "exact",
        "eligible",
        "execution",
        "external",
        "for",
        "from",
        "goal",
        "in",
        "internal",
        "is",
        "jean-claude",
        "meeting",
        "neo",
        "next",
        "no",
        "not",
        "of",
        "operator",
        "or",
        "owner",
        "pm",
        "private",
        "project",
        "proposal",
        "ratify",
        "report",
        "required",
        "reason",
        "role",
        "safe",
        "standup",
        "system",
        "the",
        "this",
        "to",
        "verified",
        "with",
        "withhold",
        "workspace",
        "yoda",
    }
)


def semantic_sha256(value: object) -> str:
    """Return the project-wide canonical digest used by meeting receipts."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping_value(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("standup promotion value must be a mapping")


def _collect_private_workspace_literals(value: object) -> tuple[str, ...]:
    """Collect exact private strings so copies in narrative fields are redacted.

    Dropping the structured goal contract is not sufficient when a local prep
    has copied its goal or an exact private excerpt into a summary, instruction,
    or discussion note.  This deliberately matches only exact, substantial
    source strings; it does not attempt to classify or rewrite ordinary owner-
    visible standup prose.
    """

    literals: set[str] = set()

    def collect_strings(candidate: object) -> None:
        if isinstance(candidate, str):
            normalized = " ".join(candidate.split()).strip()
            if len(normalized) >= 12:
                literals.add(normalized)
        elif isinstance(candidate, Mapping):
            for nested in candidate.values():
                collect_strings(nested)
        elif isinstance(candidate, (list, tuple, set, frozenset)):
            for nested in candidate:
                collect_strings(nested)

    def walk(candidate: object) -> None:
        if isinstance(candidate, Mapping):
            for raw_key, nested in candidate.items():
                key = str(raw_key).strip().lower()
                if key in _REMOTE_PRIVATE_GOAL_KEYS or key in _REMOTE_PRIVATE_EXCERPT_KEYS:
                    collect_strings(nested)
                else:
                    walk(nested)
        elif isinstance(candidate, (list, tuple, set, frozenset)):
            for nested in candidate:
                walk(nested)

    walk(value)
    return tuple(sorted(literals, key=lambda item: (-len(item), item)))


def _collect_all_private_source_literals(values: Sequence[object]) -> tuple[str, ...]:
    """Collect full local source text for output-only copy detection."""

    literals: set[str] = set()

    def walk(candidate: object) -> None:
        if isinstance(candidate, str):
            normalized = " ".join(candidate.split()).strip()
            if len(normalized) >= 12:
                literals.add(normalized)
        elif isinstance(candidate, Mapping):
            for nested in candidate.values():
                walk(nested)
        elif isinstance(candidate, (list, tuple, set, frozenset)):
            for nested in candidate:
                walk(nested)

    for value in values:
        walk(value)
    return tuple(sorted(literals, key=lambda item: (-len(item), item)))


def _redact_private_word_overlap(
    text: str,
    *,
    private_literals: Sequence[str],
) -> str:
    """Redact copied sentences and arbitrary middle slices from local sources.

    Exact-value replacement alone misses a second sentence or a bounded middle
    slice copied from a longer identity/strategy document.  Five consecutive
    source words are substantial copied prose.  A shorter span is also private
    when it contains a distinctive word, acronym, or codename from the private
    source corpus.  Matching spans are expanded on both sides so the ends of a
    quoted slice cannot leak.
    """

    token_matches = list(re.finditer(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", text))
    if not token_matches:
        return text
    original_words = [match.group(0) for match in token_matches]
    words = [word.casefold() for word in original_words]
    source_corpora = [
        " ".join(
            match.group(0).casefold()
            for match in re.finditer(
                r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?",
                sanitize_brain_text(literal),
            )
        )
        for literal in private_literals
    ]
    source_corpora = [corpus for corpus in source_corpora if corpus]
    if not source_corpora:
        return text

    def meaningful_short_phrase(index: int, width: int) -> bool:
        if width >= _PRIVATE_OVERLAP_WORDS:
            return True
        phrase_words = words[index : index + width]
        original_phrase_words = original_words[index : index + width]
        if sum(len(word) for word in phrase_words) < 8:
            return False
        for word, original in zip(phrase_words, original_phrase_words, strict=True):
            if word in _PRIVATE_OVERLAP_GENERIC_WORDS:
                continue
            if len(word) >= 8 or (len(original) >= 3 and original.isupper()):
                return True
            if width >= 2 and len(word) >= 5:
                return True
        return False

    matched_indexes: set[int] = set()
    maximum_width = min(_PRIVATE_OVERLAP_WORDS, len(words))
    for width in range(maximum_width, 0, -1):
        for index in range(len(words) - width + 1):
            if not meaningful_short_phrase(index, width):
                continue
            phrase = " ".join(words[index : index + width])
            bounded_phrase = f" {phrase} "
            if any(bounded_phrase in f" {corpus} " for corpus in source_corpora):
                matched_indexes.update(range(index, index + width))
    if not matched_indexes:
        return text

    expanded: set[int] = set()
    for index in matched_indexes:
        expanded.update(
            range(
                max(0, index - (_PRIVATE_OVERLAP_WORDS - 1)),
                min(len(token_matches), index + _PRIVATE_OVERLAP_WORDS),
            )
        )
    groups: list[tuple[int, int]] = []
    for index in sorted(expanded):
        if not groups or index > groups[-1][1] + 1:
            groups.append((index, index))
        else:
            groups[-1] = (groups[-1][0], index)
    for start_index, end_index in reversed(groups):
        start = token_matches[start_index].start()
        end = token_matches[end_index].end()
        text = text[:start] + "[private-workspace-context]" + text[end:]
    return text


def _remote_standup_text(value: object, *, private_literals: Sequence[str]) -> str:
    text = " ".join(sanitize_brain_text(str(value or "")).split()).strip()
    for literal in private_literals:
        normalized = " ".join(literal.split()).strip()
        if normalized and len(normalized) <= 4096:
            text = re.sub(
                re.escape(normalized).replace(r"\ ", r"\s+"),
                "[private-workspace-context]",
                text,
                flags=re.IGNORECASE,
            )
    text = _redact_private_word_overlap(
        text,
        private_literals=private_literals,
    )
    if contains_private_filesystem_reference(text):
        return "[private-local-reference-removed]"
    return text


def _remote_strategy_context(
    value: object,
    *,
    private_literals: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in _REMOTE_STRATEGY_FIELDS:
        cell = value.get(key)
        if cell is None:
            continue
        if isinstance(cell, bool):
            result[key] = cell
        elif isinstance(cell, (str, int, float)):
            result[key] = _remote_standup_text(
                cell,
                private_literals=private_literals,
            )
    return result


def _remote_prior_standup(
    value: object,
    *,
    private_literals: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in _REMOTE_PRIOR_STANDUP_FIELDS:
        cell = value.get(key)
        if cell is None:
            continue
        if isinstance(cell, bool) or isinstance(cell, (int, float)):
            result[key] = cell
        elif isinstance(cell, str):
            result[key] = _remote_standup_text(
                cell,
                private_literals=private_literals,
            )
    return result


def _remote_pm_snapshot(
    value: object,
    *,
    private_literals: Sequence[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    cards: list[dict[str, Any]] = []
    for raw_card in value.get("cards") or []:
        if not isinstance(raw_card, Mapping):
            continue
        card: dict[str, Any] = {}
        for key in _REMOTE_PM_CARD_FIELDS:
            cell = raw_card.get(key)
            if cell is None:
                continue
            if isinstance(cell, bool) or isinstance(cell, (int, float)):
                card[key] = cell
            elif isinstance(cell, str):
                card[key] = _remote_standup_text(
                    cell,
                    private_literals=private_literals,
                )
        if card:
            cards.append(card)
    counts = value.get("counts") if isinstance(value.get("counts"), Mapping) else {}
    safe_counts = {
        str(key): int(cell)
        for key, cell in counts.items()
        if isinstance(cell, int) and not isinstance(cell, bool)
    }
    if not cards and not safe_counts:
        return {}
    return {
        "card_count": len(cards),
        "cards": cards,
        **({"counts": safe_counts} if safe_counts else {}),
    }


def _remote_standup_value(
    value: object,
    *,
    private_literals: Sequence[str],
    key: str = "",
    parent_key: str = "",
) -> Any:
    normalized_key = key.strip().lower()
    if (
        normalized_key in _REMOTE_PRIVATE_GOAL_KEYS
        or normalized_key in _REMOTE_PRIVATE_EXCERPT_KEYS
        or normalized_key in _REMOTE_LOCAL_REFERENCE_KEYS
        or normalized_key in {"memory_promotions", "strategy_context_lines"}
        or normalized_key.endswith("_local_path")
        or normalized_key.endswith("_source_path")
    ):
        return _DROP_REMOTE_VALUE
    if normalized_key in {"trigger", "future_trigger"} and parent_key == "no_action":
        return _DROP_REMOTE_VALUE
    if normalized_key == "strategy_context":
        return _remote_strategy_context(value, private_literals=private_literals)
    if normalized_key == "prior_standup":
        return _remote_prior_standup(value, private_literals=private_literals)
    if normalized_key == "pm_snapshot":
        return _remote_pm_snapshot(value, private_literals=private_literals)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_child_key, child in value.items():
            child_key = str(raw_child_key).strip()
            if not child_key:
                continue
            projected = _remote_standup_value(
                child,
                private_literals=private_literals,
                key=child_key,
                parent_key=normalized_key or parent_key,
            )
            if projected is not _DROP_REMOTE_VALUE:
                result[child_key] = projected
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        result = []
        for child in value:
            projected = _remote_standup_value(
                child,
                private_literals=private_literals,
                parent_key=normalized_key or parent_key,
            )
            if projected is not _DROP_REMOTE_VALUE:
                result.append(projected)
        return result
    if isinstance(value, str):
        return _remote_standup_text(value, private_literals=private_literals)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _remote_standup_text(value, private_literals=private_literals)


def remote_standup_pm_update(
    value: Mapping[str, Any] | object,
    *,
    private_literals: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return the closed recommendation/PM shape allowed on Railway."""

    raw = _mapping_value(value)
    resolved_private_literals = (
        tuple(private_literals)
        if private_literals is not None
        else _collect_private_workspace_literals(raw)
    )
    payload = _remote_standup_value(
        raw.get("payload") or {},
        private_literals=resolved_private_literals,
        key="payload",
    )
    if payload is _DROP_REMOTE_VALUE or not isinstance(payload, Mapping):
        payload = {}
    return {
        "workspace_key": str(raw.get("workspace_key") or "shared_ops"),
        "scope": str(raw.get("scope") or "shared_ops"),
        "owner_agent": str(raw.get("owner_agent") or "jean-claude"),
        "title": _remote_standup_text(
            raw.get("title") or "",
            private_literals=resolved_private_literals,
        ),
        "status": str(raw.get("status") or "todo"),
        "reason": _remote_standup_text(
            raw.get("reason") or "",
            private_literals=resolved_private_literals,
        ),
        "payload": dict(payload),
    }


def remote_standup_report_content(
    value: Mapping[str, Any],
    *,
    promotion_payload: Mapping[str, Any] | object,
    private_contexts: Sequence[object] = (),
) -> dict[str, Any]:
    """Sanitize one role report after local reasoning and before it is signed."""

    promotion = _mapping_value(promotion_payload)
    private_literals = tuple(
        dict.fromkeys(
            (
                *_collect_private_workspace_literals(promotion),
                *_collect_all_private_source_literals(
                    (promotion, *private_contexts)
                ),
            )
        )
    )
    projected = _remote_standup_value(
        value,
        private_literals=private_literals,
    )
    if not isinstance(projected, Mapping):
        raise ValueError("standup participant report projection is malformed")
    return dict(projected)


def remote_standup_promotion_payload(
    value: Mapping[str, Any] | object,
) -> dict[str, Any]:
    """Project a rich local prep into the only promotion shape Railway may see."""

    raw = _mapping_value(value)
    private_literals = _collect_private_workspace_literals(raw)
    projected = _remote_standup_value(
        raw,
        private_literals=private_literals,
    )
    if not isinstance(projected, Mapping):
        raise ValueError("standup promotion projection is malformed")
    result = dict(projected)
    result["conversation_path"] = None
    result["source_paths"] = []
    result["memory_promotions"] = []
    result["recommendation_path"] = None
    result["strategy_context"] = _remote_strategy_context(
        raw.get("strategy_context"),
        private_literals=private_literals,
    )
    result["prior_standup"] = _remote_prior_standup(
        raw.get("prior_standup"),
        private_literals=private_literals,
    )
    result["pm_snapshot"] = _remote_pm_snapshot(
        raw.get("pm_snapshot"),
        private_literals=private_literals,
    )
    result["pm_updates"] = [
        remote_standup_pm_update(update, private_literals=private_literals)
        for update in raw.get("pm_updates") or raw.get("recommendation_requests") or []
        if isinstance(update, Mapping) or hasattr(update, "model_dump")
    ]
    return result


def canonical_promotion_claims(value: Mapping[str, Any] | object) -> dict[str, Any]:
    """Project the exact owner-visible claims participant reports authorize."""

    raw = remote_standup_promotion_payload(value)
    recursion = dict(raw.get("recursion") or {})
    # These fields are written only after the independent reports complete.
    recursion.pop("meeting_attempt", None)
    recursion.pop("recommendation_resolutions", None)
    recursion.pop("async_role_contribution", None)
    pm_updates: list[dict[str, Any]] = []
    for update in raw.get("pm_updates") or raw.get("recommendation_requests") or []:
        if hasattr(update, "model_dump"):
            item = update.model_dump(mode="json")
        elif isinstance(update, Mapping):
            item = dict(update)
        else:
            raise ValueError("meeting PM recommendation claim is malformed")
        pm_updates.append(remote_standup_pm_update(item))
    claims = {
        "meeting_id": str(raw.get("meeting_id") or "").strip(),
        "prep_id": str(raw.get("prep_id") or "").strip() or None,
        "workspace_key": canonicalize_workspace_key(
            str(raw.get("workspace_key") or ""),
            default="shared_ops",
        ),
        "cycle_id": str(raw.get("cycle_id") or "").strip(),
        "standup_kind": str(raw.get("standup_kind") or "").strip(),
        "owner": str(raw.get("owner") or "Jean-Claude"),
        "source": str(raw.get("source") or "standup_prep"),
        "conversation_path": raw.get("conversation_path"),
        "participants": [str(item).strip() for item in raw.get("participants") or [] if str(item).strip()],
        "summary": str(raw.get("summary") or ""),
        "agenda": list(raw.get("agenda") or []),
        "blockers": list(raw.get("blockers") or []),
        "commitments": list(raw.get("commitments") or []),
        "needs": list(raw.get("needs") or []),
        "audience_response": list(raw.get("audience_response") or []),
        "decisions": list(raw.get("decisions") or []),
        "owners": list(raw.get("owners") or []),
        "artifact_deltas": list(raw.get("artifact_deltas") or []),
        "standup_sections": dict(raw.get("standup_sections") or {}),
        "pm_snapshot": dict(raw.get("pm_snapshot") or {}),
        "strategy_context": dict(raw.get("strategy_context") or {}),
        "standup_relevance": dict(raw.get("standup_relevance") or {}),
        "source_paths": list(raw.get("source_paths") or []),
        "memory_promotions": list(raw.get("memory_promotions") or []),
        "prior_standup": dict(raw.get("prior_standup") or {}),
        "continuity": dict(raw.get("continuity") or {}),
        "recursion": recursion,
        "recommendation_path": raw.get("recommendation_path"),
        "pm_updates": pm_updates,
    }
    encoded = json.dumps(
        claims,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    if len(encoded) > MAX_PROMOTION_CLAIMS_BYTES:
        raise ValueError("meeting promotion claims exceed their bound")
    return claims


def promotion_payload_sha256(value: Mapping[str, Any] | object) -> str:
    return semantic_sha256(canonical_promotion_claims(value))


def async_role_contribution_id(
    value: Mapping[str, Any] | object,
    *,
    display_name: str,
) -> str:
    """Return the immutable identity for one non-meeting role contribution."""

    participant = str(display_name or "").strip()
    if not participant:
        raise ValueError("async role contribution requires a participant")
    claims_sha256 = promotion_payload_sha256(value)
    return str(
        uuid5(
            NAMESPACE_URL,
            "ai-clone:standup-async-role:"
            f"{claims_sha256}:{_participant_key(participant)}",
        )
    )


def _participant_key(display_name: str) -> str:
    lowered = "".join(
        character.lower() if character.isalnum() else "-"
        for character in display_name.strip()
    )
    return "-".join(part for part in lowered.split("-") if part)


def _identity_pack_root(*, workspace_key: str, display_name: str) -> Path | None:
    known_slug = _KNOWN_AGENT_PACKS.get(display_name)
    if known_slug:
        return REPO_ROOT / "agents" / known_slug

    entry = workspace_registry_entry(workspace_key)
    allowed_names = {
        str(entry.get(field) or "").strip()
        for field in ("operator_name", "workspace_agent", "target_agent")
        if str(entry.get(field) or "").strip()
    }
    if display_name not in allowed_names:
        return None
    root_slug = str(entry.get("workspace_root") or "").strip()
    if not root_slug:
        return None
    return WORKSPACES_ROOT / root_slug


def _local_identity_pack_sha256(
    workspace_key: str,
    display_name: str,
) -> str | None:
    """Digest one complete canonical participant identity pack.

    The digest deliberately excludes filesystem paths. A report generated from
    a missing, partial, symlinked, or unreadable pack cannot prove attendance.
    """

    canonical_workspace = canonicalize_workspace_key(workspace_key, default="shared_ops")
    pack_root = _identity_pack_root(
        workspace_key=canonical_workspace,
        display_name=str(display_name or "").strip(),
    )
    if pack_root is None:
        return None
    files: list[dict[str, str]] = []
    for name in IDENTITY_PACK_FILES:
        path = pack_root / name
        if path.is_symlink() or not path.is_file():
            return None
        try:
            content = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None
        if not content:
            return None
        files.append({"name": name, "content": content})
    return semantic_sha256(files)


def _projected_identity_pack_digests() -> dict[tuple[str, str], str] | None:
    """Load the protected digest-only deployment projection.

    Railway intentionally has no private identity-pack bodies. The protected
    source release therefore carries only reviewed SHA-256 bindings. Any
    malformed, partial, duplicated, or scope-inconsistent projection fails
    closed rather than turning an arbitrary receipt hash into role authority.
    """

    path = IDENTITY_PACK_DIGEST_PROJECTION_PATH
    try:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > IDENTITY_PACK_DIGEST_PROJECTION_MAX_BYTES
        ):
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, Mapping)
        or set(payload)
        != {
            "schema_version",
            "algorithm",
            "identity_pack_files",
            "entries",
            "data_policy",
        }
        or payload.get("schema_version")
        != IDENTITY_PACK_DIGEST_PROJECTION_SCHEMA_VERSION
        or payload.get("algorithm") != "canonical_identity_pack_sha256/v1"
        or payload.get("identity_pack_files") != list(IDENTITY_PACK_FILES)
        or payload.get("data_policy")
        != {
            "canonical_authority": "private_identity_packs",
            "public_role": "digest_only_verification_projection",
            "private_identity_content_included": False,
        }
        or not isinstance(payload.get("entries"), list)
        or not 1 <= len(payload["entries"]) <= 32
    ):
        return None
    projected: dict[tuple[str, str], str] = {}
    for raw_entry in payload["entries"]:
        if (
            not isinstance(raw_entry, Mapping)
            or set(raw_entry)
            != {"workspace_key", "display_name", "identity_pack_sha256"}
        ):
            return None
        workspace_key = str(raw_entry.get("workspace_key") or "").strip()
        display_name = str(raw_entry.get("display_name") or "").strip()
        digest = str(raw_entry.get("identity_pack_sha256") or "").strip()
        if (
            not display_name
            or len(display_name) > 120
            or _SHA256_RE.fullmatch(digest) is None
        ):
            return None
        if display_name in _KNOWN_AGENT_PACKS:
            if workspace_key != "*":
                return None
        else:
            if workspace_key == "*":
                return None
            canonical_workspace = canonicalize_workspace_key(
                workspace_key,
                default="shared_ops",
            )
            if canonical_workspace != workspace_key:
                return None
            registry_entry = workspace_registry_entry(canonical_workspace)
            allowed_names = {
                str(registry_entry.get(field) or "").strip()
                for field in ("operator_name", "workspace_agent", "target_agent")
                if str(registry_entry.get(field) or "").strip()
            }
            if display_name not in allowed_names:
                return None
        key = (workspace_key, display_name)
        if key in projected:
            return None
        projected[key] = digest.removeprefix("sha256:")
    return projected


def _private_identity_pack_authority_present() -> bool:
    return (REPO_ROOT / "agents").is_dir() or WORKSPACES_ROOT.is_dir()


def canonical_identity_pack_sha256(
    workspace_key: str,
    display_name: str,
) -> str | None:
    """Return the private canonical pack digest only when deployment pins it.

    The private pack remains authoritative. The public file is a digest-only
    projection used to verify the same role binding on Railway. Local pack and
    projected digest must agree; absence or drift fails closed everywhere.
    """

    canonical_workspace = canonicalize_workspace_key(
        workspace_key,
        default="shared_ops",
    )
    normalized_display_name = str(display_name or "").strip()
    projected = _projected_identity_pack_digests()
    if projected is None:
        return None
    projection_key = (
        ("*", normalized_display_name)
        if normalized_display_name in _KNOWN_AGENT_PACKS
        else (canonical_workspace, normalized_display_name)
    )
    projected_digest = projected.get(projection_key)
    if projected_digest is None:
        return None
    local_digest = _local_identity_pack_sha256(
        canonical_workspace,
        normalized_display_name,
    )
    if local_digest is None and _private_identity_pack_authority_present():
        return None
    if local_digest is not None and local_digest != projected_digest:
        return None
    return projected_digest


def _mapping_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _participant_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _explicit_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _integer(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _run_value(run: AutomationRun | Mapping[str, Any], field: str) -> Any:
    if isinstance(run, Mapping):
        return run.get(field)
    return getattr(run, field, None)


def _run_metadata(run: AutomationRun | Mapping[str, Any]) -> dict[str, Any]:
    metadata = _run_value(run, "metadata")
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def _signed_receipt_metadata(
    run_id: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Verify the purpose-signed receipt while excluding one ledger-owned field.

    ``append_local_runs`` adds ``locally_recorded_at`` after the producer signs
    the local metadata. It is a ledger-write timestamp, not participant
    evidence, so it is validated and excluded from that envelope when present.
    The canonical Postgres mirror stores the exact signed producer metadata and
    therefore legitimately has no local-record timestamp.
    """

    candidate = dict(metadata)
    locally_recorded_at = candidate.pop("locally_recorded_at", None)
    if locally_recorded_at is not None and _explicit_utc(locally_recorded_at) is None:
        return None
    if not verify_execution_payload(run_id, candidate):
        return None
    return candidate


def _canonical_report_content(
    value: object,
    *,
    require_ratification: bool,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    content = dict(value)
    required_fields = set(_BASE_REPORT_CONTENT_FIELDS)
    allowed_fields = set(_BASE_REPORT_CONTENT_FIELDS)
    if require_ratification:
        required_fields.update(_RATIFICATION_CONTENT_FIELDS)
        allowed_fields.update(_RATIFICATION_CONTENT_FIELDS)
    if set(content) != required_fields or not set(content).issubset(allowed_fields):
        return None
    note = str(content.get("note") or "").strip()
    evidence_refs = content.get("evidence_refs")
    risks = content.get("risks")
    recommended_next_step = str(content.get("recommended_next_step") or "").strip()
    position = str(content.get("position") or "").strip()
    if (
        len(note) < 12
        or len(note) > 2400
        or not isinstance(evidence_refs, list)
        or len(evidence_refs) > 12
        or any(not isinstance(item, str) or not item.strip() or len(item) > 280 for item in evidence_refs)
        or position not in _REPORT_POSITIONS
        or not isinstance(risks, list)
        or len(risks) > 8
        or any(not isinstance(item, str) or not item.strip() or len(item) > 360 for item in risks)
        or not recommended_next_step
        or len(recommended_next_step) > 700
        or not isinstance(content.get("owner_decision_required"), bool)
    ):
        return None
    canonical = {
        "note": note,
        "evidence_refs": list(evidence_refs),
        "position": position,
        "risks": list(risks),
        "recommended_next_step": recommended_next_step,
        "owner_decision_required": content["owner_decision_required"],
    }
    if require_ratification:
        proposal_disposition = str(content.get("proposal_disposition") or "").strip()
        ratification_reason = str(content.get("ratification_reason") or "").strip()
        if (
            proposal_disposition not in RATIFICATION_DISPOSITIONS
            or len(ratification_reason) < 12
            or len(ratification_reason) > 900
        ):
            return None
        canonical.update(
            {
                "proposal_disposition": proposal_disposition,
                "ratification_reason": ratification_reason,
            }
        )
    return canonical


def _canonical_participant_report(
    run: AutomationRun | Mapping[str, Any],
    *,
    workspace_key: str,
    cycle_id: str,
    meeting_id: str,
    standup_kind: str,
    expected_participants: Sequence[str],
    expected_closing_participant: str,
    verify_current_identity_pack: bool,
    expected_promotion_payload_sha256: str,
) -> tuple[dict[str, Any] | None, str | None]:
    run_id = str(_run_value(run, "id") or "").strip()
    metadata = _signed_receipt_metadata(run_id, _run_metadata(run))
    if metadata is None:
        return None, "participant_report_signature_invalid"

    display_name = str(metadata.get("display_name") or "").strip()
    phase = str(metadata.get("phase") or "").strip()
    phase_index = _integer(metadata.get("phase_index")) or 0
    expected_phase = dict(MEETING_PHASES).get(phase_index)
    canonical_workspace = canonicalize_workspace_key(workspace_key, default="shared_ops")
    run_workspace = canonicalize_workspace_key(
        str(_run_value(run, "workspace_key") or ""),
        default="shared_ops",
    )
    receipt_workspace = canonicalize_workspace_key(
        str(metadata.get("workspace_key") or ""),
        default="shared_ops",
    )
    expected_scope = "shared_ops" if canonical_workspace == "shared_ops" else "workspace"
    generated_at = _explicit_utc(metadata.get("generated_at"))
    run_finished_at = _explicit_utc(
        _run_value(run, "finished_at") or _run_value(run, "run_at")
    )
    raw_report_content = metadata.get("report_content")
    is_closing_report = bool(
        phase == "commitments_resolution"
        and display_name == expected_closing_participant
    )
    report_content = _canonical_report_content(
        raw_report_content,
        require_ratification=is_closing_report,
    )
    report_content_bytes = b""
    if isinstance(report_content, Mapping):
        report_content_bytes = json.dumps(
            dict(report_content),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    note = (
        str(report_content.get("note") or "").strip()
        if isinstance(report_content, Mapping)
        else ""
    )
    observed_identity_digest = str(metadata.get("identity_pack_sha256") or "").strip().removeprefix("sha256:")
    canonical_identity_digest = canonical_identity_pack_sha256(
        canonical_workspace,
        display_name,
    )
    observed_report_digest = str(metadata.get("report_sha256") or "").strip().removeprefix("sha256:")
    report_digest = semantic_sha256(dict(report_content)) if isinstance(report_content, Mapping) else ""
    resolution_reports_considered = _participant_names(
        metadata.get("resolution_reports_considered")
    )

    if (
        not run_id
        or str(_run_value(run, "automation_id") or "").strip()
        != PARTICIPANT_REPORT_AUTOMATION_ID
        or str(_run_value(run, "runtime") or "").strip() != "codex_exec"
        or str(_run_value(run, "source") or "").strip() != "local_launchd_registry"
        or str(_run_value(run, "status") or "").strip().lower()
        not in _SUCCESSFUL_RUN_STATUSES
        or str(_run_value(run, "error") or "").strip()
        or _run_value(run, "action_required") is True
        or str(_run_value(run, "owner_agent") or "").strip() != display_name
        or not str(_run_value(run, "workspace_key") or "").strip()
        or run_workspace != canonical_workspace
        or str(_run_value(run, "scope") or "").strip() != expected_scope
        or metadata.get("schema_version") != PARTICIPANT_REPORT_SCHEMA_VERSION
        or metadata.get("provenance") != PARTICIPANT_REPORT_PROVENANCE
        or str(metadata.get("meeting_id") or "").strip() != meeting_id
        or str(metadata.get("cycle_id") or "").strip() != cycle_id
        or str(metadata.get("standup_kind") or "").strip() != standup_kind
        or not str(metadata.get("workspace_key") or "").strip()
        or receipt_workspace != canonical_workspace
        or display_name not in expected_participants
        or str(metadata.get("participant_key") or "").strip()
        != _participant_key(display_name)
        or expected_phase != phase
        or generated_at is None
        or run_finished_at is None
        or generated_at != run_finished_at
        or not isinstance(report_content, Mapping)
        or not note
        or not report_content_bytes
        or len(report_content_bytes) > MAX_REPORT_CONTENT_BYTES
        or _SHA256_RE.fullmatch(str(metadata.get("input_sha256") or "").strip()) is None
        or _SHA256_RE.fullmatch(str(metadata.get("meeting_packet_sha256") or "").strip()) is None
        or metadata.get("role_context_schema_version") != ROLE_CONTEXT_SCHEMA_VERSION
        or _SHA256_RE.fullmatch(str(metadata.get("role_context_sha256") or "").strip()) is None
        or str(metadata.get("closing_participant") or "").strip()
        != expected_closing_participant
        or metadata.get("is_closing_report") is not is_closing_report
        or (not is_closing_report and resolution_reports_considered)
        or str(metadata.get("promotion_payload_sha256") or "").strip().removeprefix("sha256:")
        != expected_promotion_payload_sha256
        or _SHA256_RE.fullmatch(str(metadata.get("identity_pack_sha256") or "").strip()) is None
        or (
            verify_current_identity_pack
            and (
                canonical_identity_digest is None
                or observed_identity_digest != canonical_identity_digest
            )
        )
        or _SHA256_RE.fullmatch(str(metadata.get("report_sha256") or "").strip()) is None
        or observed_report_digest != report_digest
    ):
        return None, "participant_report_authority_binding_invalid"

    return (
        {
            "schema_version": PARTICIPANT_REPORT_SCHEMA_VERSION,
            "agent_run_id": run_id,
            "display_name": display_name,
            "participant_key": _participant_key(display_name),
            "phase": phase,
            "phase_index": phase_index,
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "identity_pack_sha256": observed_identity_digest,
            "input_sha256": str(metadata.get("input_sha256") or "").strip().removeprefix("sha256:"),
            "meeting_packet_sha256": str(metadata.get("meeting_packet_sha256") or "").strip().removeprefix("sha256:"),
            "role_context_schema_version": ROLE_CONTEXT_SCHEMA_VERSION,
            "role_context_sha256": str(metadata.get("role_context_sha256") or "").strip().removeprefix("sha256:"),
            "closing_participant": expected_closing_participant,
            "is_closing_report": is_closing_report,
            "resolution_reports_considered": resolution_reports_considered,
            "promotion_payload_sha256": expected_promotion_payload_sha256,
            "report_sha256": report_digest,
            "report_content": dict(report_content),
            "provenance": PARTICIPANT_REPORT_PROVENANCE,
        },
        None,
    )


def async_role_contribution_truth(
    evidence: Mapping[str, Any] | None,
    *,
    promotion_payload: Mapping[str, Any] | object,
    verify_current_identity_pack: bool = False,
) -> dict[str, Any]:
    """Verify one independently signed FEEZIE async role contribution.

    This receipt is deliberately separate from meeting evidence.  It proves
    that exactly one relevance-selected role ran against the exact promotion
    claims.  It never proves attendance, a Jean-Claude close, or transferred
    PM/execution authority.
    """

    from app.services.standup_relevance_service import (  # local to avoid a wider import cycle
        validate_standup_relevance_plan,
    )

    raw_evidence = dict(evidence or {})
    if raw_evidence.get("schema_version") != ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION:
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_evidence_schema_invalid",
        }
    try:
        claims = canonical_promotion_claims(promotion_payload)
        relevance = validate_standup_relevance_plan(
            dict(claims.get("standup_relevance") or {})
        )
    except (TypeError, ValueError):
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_relevance_invalid",
        }
    if (
        canonicalize_workspace_key(
            str(claims.get("workspace_key") or ""),
            default="shared_ops",
        )
        != "feezie-os"
        or str(relevance.get("disposition") or "").strip()
        != "decision_record"
    ):
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_disposition_invalid",
        }
    participant_plan = [
        item
        for item in (relevance.get("participant_plan") or [])
        if isinstance(item, Mapping)
    ]
    selected_participants = [
        str(item.get("display_name") or "").strip()
        for item in participant_plan
        if str(item.get("display_name") or "").strip()
    ]
    if len(selected_participants) != 1:
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_participant_count_invalid",
        }
    participant = selected_participants[0]
    if [str(item).strip() for item in claims.get("participants") or []] != [
        participant
    ]:
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_participant_plan_mismatch",
        }

    expected_contribution_id = async_role_contribution_id(
        promotion_payload,
        display_name=participant,
    )
    run_id = str(raw_evidence.get("participant_report_run_id") or "").strip()
    expected_run_id = str(
        uuid5(
            NAMESPACE_URL,
            f"ai-clone:standup-async-role-report:{expected_contribution_id}",
        )
    )
    if (
        str(raw_evidence.get("contribution_id") or "").strip()
        != expected_contribution_id
        or run_id != expected_run_id
        or str(raw_evidence.get("display_name") or "").strip() != participant
        or raw_evidence.get("canonical_pm_execution_authority")
        != CANONICAL_MEETING_CLOSER
        or raw_evidence.get("pm_execution_authority_transferred") is not False
    ):
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_evidence_identity_invalid",
        }

    runs = list_runs(
        limit=2,
        automation_id=PARTICIPANT_REPORT_AUTOMATION_ID,
        run_ids=[run_id],
    )
    exact_runs = [run for run in runs if str(_run_value(run, "id") or "") == run_id]
    if len(exact_runs) != 1:
        return {
            "valid": False,
            "state": "async_role_receipt_missing",
            "reason": "canonical_async_role_receipt_missing",
        }
    run = exact_runs[0]
    metadata = _signed_receipt_metadata(run_id, _run_metadata(run))
    if metadata is None:
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_receipt_signature_invalid",
        }
    workspace_key = "feezie-os"
    run_workspace = canonicalize_workspace_key(
        str(_run_value(run, "workspace_key") or ""),
        default="shared_ops",
    )
    receipt_workspace = canonicalize_workspace_key(
        str(metadata.get("workspace_key") or ""),
        default="shared_ops",
    )
    generated_at = _explicit_utc(metadata.get("generated_at"))
    run_finished_at = _explicit_utc(
        _run_value(run, "finished_at") or _run_value(run, "run_at")
    )
    report_content = _canonical_report_content(
        metadata.get("report_content"),
        require_ratification=False,
    )
    report_bytes = b""
    if isinstance(report_content, Mapping):
        report_bytes = json.dumps(
            dict(report_content),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    report_sha256 = (
        semantic_sha256(dict(report_content))
        if isinstance(report_content, Mapping)
        else ""
    )
    identity_digest = str(
        metadata.get("identity_pack_sha256") or ""
    ).strip().removeprefix("sha256:")
    canonical_identity_digest = canonical_identity_pack_sha256(
        workspace_key,
        participant,
    )
    expected_authority_scope = (
        "jean_claude_pm_execution_closure"
        if participant == CANONICAL_MEETING_CLOSER
        else "independent_role_lens_only"
    )
    claims_sha256 = promotion_payload_sha256(promotion_payload)
    if (
        str(_run_value(run, "automation_id") or "").strip()
        != PARTICIPANT_REPORT_AUTOMATION_ID
        or str(_run_value(run, "runtime") or "").strip() != "codex_exec"
        or str(_run_value(run, "source") or "").strip()
        != "local_launchd_registry"
        or str(_run_value(run, "status") or "").strip().lower()
        not in _SUCCESSFUL_RUN_STATUSES
        or str(_run_value(run, "error") or "").strip()
        or _run_value(run, "action_required") is True
        or str(_run_value(run, "owner_agent") or "").strip() != participant
        or run_workspace != workspace_key
        or str(_run_value(run, "scope") or "").strip() != "workspace"
        or metadata.get("schema_version")
        != ASYNC_ROLE_CONTRIBUTION_SCHEMA_VERSION
        or metadata.get("provenance") != PARTICIPANT_REPORT_PROVENANCE
        or str(metadata.get("contribution_id") or "").strip()
        != expected_contribution_id
        or str(metadata.get("cycle_id") or "").strip()
        != str(claims.get("cycle_id") or "").strip()
        or str(metadata.get("standup_kind") or "").strip()
        != str(claims.get("standup_kind") or "").strip()
        or receipt_workspace != workspace_key
        or str(metadata.get("participant_key") or "").strip()
        != _participant_key(participant)
        or str(metadata.get("display_name") or "").strip() != participant
        or str(metadata.get("relevance_fingerprint") or "").strip()
        != str(relevance.get("input_fingerprint") or "").strip()
        or metadata.get("canonical_pm_execution_authority")
        != CANONICAL_MEETING_CLOSER
        or metadata.get("pm_execution_authority_transferred") is not False
        or metadata.get("participant_is_canonical_pm_execution_authority")
        is not (participant == CANONICAL_MEETING_CLOSER)
        or str(metadata.get("authority_scope") or "").strip()
        != expected_authority_scope
        or str(metadata.get("promotion_payload_sha256") or "")
        .strip()
        .removeprefix("sha256:")
        != claims_sha256
        or generated_at is None
        or run_finished_at is None
        or generated_at != run_finished_at
        or not isinstance(report_content, Mapping)
        or not report_bytes
        or len(report_bytes) > MAX_REPORT_CONTENT_BYTES
        or _SHA256_RE.fullmatch(
            str(metadata.get("input_sha256") or "").strip()
        )
        is None
        or metadata.get("role_context_schema_version")
        != ROLE_CONTEXT_SCHEMA_VERSION
        or _SHA256_RE.fullmatch(
            str(metadata.get("role_context_sha256") or "").strip()
        )
        is None
        or _SHA256_RE.fullmatch(
            str(metadata.get("identity_pack_sha256") or "").strip()
        )
        is None
        or (
            verify_current_identity_pack
            and (
                canonical_identity_digest is None
                or identity_digest != canonical_identity_digest
            )
        )
        or _SHA256_RE.fullmatch(
            str(metadata.get("report_sha256") or "").strip()
        )
        is None
        or str(metadata.get("report_sha256") or "")
        .strip()
        .removeprefix("sha256:")
        != report_sha256
    ):
        return {
            "valid": False,
            "state": "invalid_async_role_evidence",
            "reason": "async_role_receipt_authority_binding_invalid",
        }

    return {
        "valid": True,
        "state": "verified_signed_async_role_contribution",
        "reason": "signed_async_role_contribution_verified",
        "canonical_evidence": {
            "schema_version": ASYNC_ROLE_EVIDENCE_SCHEMA_VERSION,
            "contribution_id": expected_contribution_id,
            "participant_report_run_id": run_id,
            "display_name": participant,
            "participant_key": _participant_key(participant),
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "relevance_fingerprint": str(
                relevance.get("input_fingerprint") or ""
            ).strip(),
            "identity_pack_sha256": identity_digest,
            "promotion_payload_sha256": claims_sha256,
            "report_sha256": report_sha256,
            "report_content": dict(report_content),
            "canonical_pm_execution_authority": CANONICAL_MEETING_CLOSER,
            "participant_is_canonical_pm_execution_authority": (
                participant == CANONICAL_MEETING_CLOSER
            ),
            "pm_execution_authority_transferred": False,
            "authority_scope": expected_authority_scope,
            "meeting_held": False,
            "provenance": PARTICIPANT_REPORT_PROVENANCE,
        },
    }


def _meeting_failure(reason: str, *, state: str = "invalid_meeting_evidence") -> dict[str, Any]:
    return {"is_meeting": False, "state": state, "reason": reason}


def meeting_record_truth(
    payload: Mapping[str, Any] | None,
    *,
    source: str | None = None,
    expected_participants: Sequence[str] | None = None,
    workspace_key: str | None = None,
    verify_current_identity_pack: bool = False,
    promotion_payload: Mapping[str, Any] | object | None = None,
) -> dict[str, Any]:
    """Classify one stored record without turning meeting-shaped text into attendance.

    A genuine standup is admitted only when every named participant has a
    distinct independent-agent report and every transcript round is bound to
    one of those reports.  Prep-generated role lenses remain useful planning
    evidence, but they can never satisfy this predicate.
    """

    body = dict(payload or {})
    record_kind = str(body.get("record_kind") or "").strip()
    participants = _participant_names(body.get("participants"))
    discussion = _mapping_items(body.get("discussion"))
    provenance_values = {
        str(item.get("provenance") or "").strip().lower()
        for item in discussion
        if str(item.get("provenance") or "").strip()
    }
    source_name = str(source or "").strip().lower()

    if body.get("evaluation_only") is True or body.get("meeting_held") is False:
        state = (
            "synthetic_planning_only"
            if record_kind == WORKSPACE_CYCLE_PLAN_RECORD_KIND
            or source_name == "standup_prep"
            or provenance_values.intersection(SYNTHETIC_ROLE_PROVENANCE)
            else "non_meeting_record"
        )
        return {"is_meeting": False, "state": state, "reason": "meeting_not_held"}
    if provenance_values.intersection(SYNTHETIC_ROLE_PROVENANCE):
        return {
            "is_meeting": False,
            "state": "synthetic_planning_only",
            "reason": "synthetic_role_lens_is_not_attendance",
        }

    evidence = body.get("meeting_evidence")
    if not isinstance(evidence, Mapping):
        return _meeting_failure(
            "independent_agent_evidence_missing",
            state="synthetic_planning_only" if source_name == "standup_prep" else "unverified_meeting_shaped_record",
        )

    canonical_workspace = canonicalize_workspace_key(
        workspace_key or str(body.get("workspace_key") or ""),
        default="shared_ops",
    )
    cycle_id = str(body.get("cycle_id") or evidence.get("cycle_id") or "").strip()
    meeting_id = str(body.get("meeting_id") or evidence.get("meeting_id") or "").strip()
    standup_kind = str(body.get("standup_kind") or evidence.get("standup_kind") or "").strip()
    if (
        body.get("meeting_held") is not True
        or record_kind != MEETING_RECORD_KIND
        or str(evidence.get("schema_version") or "").strip()
        != MEETING_EVIDENCE_SCHEMA_VERSION
        or not canonical_workspace
        or not cycle_id
        or not meeting_id
        or not standup_kind
    ):
        return _meeting_failure("meeting_evidence_header_invalid")
    evidence_bindings = {
        "cycle_id": cycle_id,
        "meeting_id": meeting_id,
        "standup_kind": standup_kind,
        "workspace_key": canonical_workspace,
    }
    for field, expected_value in evidence_bindings.items():
        supplied_value = str(evidence.get(field) or "").strip()
        if supplied_value and (
            canonicalize_workspace_key(supplied_value, default="shared_ops")
            if field == "workspace_key"
            else supplied_value
        ) != expected_value:
            return _meeting_failure("meeting_evidence_binding_mismatch")

    expected = [str(item).strip() for item in (expected_participants or participants) if str(item).strip()]
    if not expected or participants != expected or len(set(participants)) != len(participants):
        return _meeting_failure("participant_contract_mismatch")
    if CANONICAL_MEETING_CLOSER not in expected:
        return _meeting_failure("canonical_jean_claude_closer_missing")
    closing_participant = CANONICAL_MEETING_CLOSER

    promotion_source = promotion_payload if promotion_payload is not None else body.get("promotion_claims")
    if promotion_source is None:
        return _meeting_failure("promotion_claim_binding_missing")
    try:
        promotion_claims = canonical_promotion_claims(promotion_source)
    except (TypeError, ValueError):
        return _meeting_failure("promotion_claim_binding_invalid")
    promotion_sha256 = semantic_sha256(promotion_claims)
    if (
        promotion_claims.get("meeting_id") != meeting_id
        or promotion_claims.get("cycle_id") != cycle_id
        or promotion_claims.get("workspace_key") != canonical_workspace
        or promotion_claims.get("standup_kind") != standup_kind
        or promotion_claims.get("participants") != expected
    ):
        return _meeting_failure("promotion_claim_binding_mismatch")
    supplied_promotion_sha = str(evidence.get("promotion_payload_sha256") or "").strip()
    if supplied_promotion_sha and supplied_promotion_sha.removeprefix("sha256:") != promotion_sha256:
        return _meeting_failure("promotion_claim_hash_mismatch")

    raw_run_ids = evidence.get("participant_report_run_ids")
    run_ids = (
        [str(item).strip() for item in raw_run_ids if str(item).strip()]
        if isinstance(raw_run_ids, list)
        else []
    )
    expected_report_count = len(participants) * len(MEETING_PHASES)
    if (
        len(run_ids) != expected_report_count
        or len(set(run_ids)) != len(run_ids)
        or any(not item for item in run_ids)
    ):
        return _meeting_failure("participant_report_run_references_invalid")

    try:
        ledger_runs = list_runs(
            limit=expected_report_count,
            automation_id=PARTICIPANT_REPORT_AUTOMATION_ID,
            run_ids=run_ids,
        )
    except Exception:
        return _meeting_failure(
            "canonical_participant_report_authority_unavailable",
            state="meeting_authority_unavailable",
        )
    runs_by_id: dict[str, AutomationRun | Mapping[str, Any]] = {}
    for run in ledger_runs:
        run_id = str(_run_value(run, "id") or "").strip()
        if run_id in run_ids and run_id not in runs_by_id:
            runs_by_id[run_id] = run
    if set(runs_by_id) != set(run_ids):
        return _meeting_failure(
            "canonical_participant_report_receipt_missing",
            state="meeting_authority_unavailable",
        )

    canonical_reports: list[dict[str, Any]] = []
    seen_participant_phases: set[tuple[str, int]] = set()
    for run_id in run_ids:
        report, reason = _canonical_participant_report(
            runs_by_id[run_id],
            workspace_key=canonical_workspace,
            cycle_id=cycle_id,
            meeting_id=meeting_id,
            standup_kind=standup_kind,
            expected_participants=expected,
            expected_closing_participant=closing_participant,
            verify_current_identity_pack=verify_current_identity_pack,
            expected_promotion_payload_sha256=promotion_sha256,
        )
        if report is None:
            return _meeting_failure(reason or "participant_report_authority_binding_invalid")
        participant_phase = (report["display_name"], int(report["phase_index"]))
        if participant_phase in seen_participant_phases:
            return _meeting_failure("participant_phase_report_duplicated")
        seen_participant_phases.add(participant_phase)
        canonical_reports.append(report)

    required_participant_phases = {
        (participant, phase_index)
        for phase_index, _phase in MEETING_PHASES
        for participant in expected
    }
    if seen_participant_phases != required_participant_phases:
        return _meeting_failure("participant_phase_report_missing")

    participant_order = {name: index for index, name in enumerate(expected)}
    canonical_reports.sort(
        key=lambda report: (
            int(report["phase_index"]),
            (
                len(expected)
                if report["phase"] == "commitments_resolution"
                and report["display_name"] == closing_participant
                else participant_order[str(report["display_name"])]
            ),
        )
    )
    canonical_run_ids = [str(report["agent_run_id"]) for report in canonical_reports]
    if run_ids != canonical_run_ids:
        return _meeting_failure("participant_report_order_mismatch")
    packet_hashes = {str(report["meeting_packet_sha256"]) for report in canonical_reports}
    role_hashes_by_participant = {
        participant: {
            str(report["role_context_sha256"])
            for report in canonical_reports
            if report["display_name"] == participant
        }
        for participant in expected
    }
    if len(packet_hashes) != 1 or any(
        len(hashes) != 1 for hashes in role_hashes_by_participant.values()
    ):
        return _meeting_failure("participant_context_binding_inconsistent")
    if len({next(iter(hashes)) for hashes in role_hashes_by_participant.values()}) != len(expected):
        return _meeting_failure("participant_role_context_not_independent")

    resolution_reports = {
        str(report["display_name"]): report
        for report in canonical_reports
        if report["phase"] == "commitments_resolution"
    }
    closing_report = resolution_reports.get(closing_participant)
    if closing_report is None:
        return _meeting_failure("canonical_closing_report_missing")
    expected_considered_run_ids = [
        str(resolution_reports[participant]["agent_run_id"])
        for participant in expected
        if participant != closing_participant
    ]
    if closing_report.get("resolution_reports_considered") != expected_considered_run_ids:
        return _meeting_failure("canonical_closer_did_not_consider_resolution_reports")
    closing_content = dict(closing_report["report_content"])
    blocked_by = [
        participant
        for participant in expected
        if str(resolution_reports[participant]["report_content"].get("position") or "")
        == "block"
    ]
    if blocked_by and closing_content.get("proposal_disposition") != "withhold":
        return _meeting_failure("blocked_resolution_cannot_be_ratified")
    resolution_positions = [
        {
            "participant": participant,
            "report_run_id": str(resolution_reports[participant]["agent_run_id"]),
            "position": str(resolution_reports[participant]["report_content"]["position"]),
            "owner_decision_required": bool(
                resolution_reports[participant]["report_content"]["owner_decision_required"]
            ),
            "recommended_next_step": str(
                resolution_reports[participant]["report_content"]["recommended_next_step"]
            ),
        }
        for participant in expected
    ]
    challenged_reports = [
        {
            "participant": participant,
            "report_run_id": str(resolution_reports[participant]["agent_run_id"]),
        }
        for participant in expected
        if str(resolution_reports[participant]["report_content"].get("position") or "")
        == "challenge"
    ]
    owner_decision_required_by = [
        item["participant"]
        for item in resolution_positions
        if item["owner_decision_required"]
    ]
    proposal_ratified = closing_content["proposal_disposition"] == "ratify_exact"
    owner_decision_routing_required = bool(
        proposal_ratified and owner_decision_required_by
    )
    challenge_disposition = (
        "overridden_by_exact_ratification"
        if proposal_ratified
        else "retained_for_proposal_revision"
    )
    canonical_ratification = {
        "schema_version": RATIFICATION_SCHEMA_VERSION,
        "closing_participant": closing_participant,
        "closing_report_run_id": str(closing_report["agent_run_id"]),
        "considered_resolution_report_run_ids": expected_considered_run_ids,
        "proposal_disposition": str(closing_content["proposal_disposition"]),
        "ratification_reason": str(closing_content["ratification_reason"]),
        # Ratification authorizes the exact recommendation to enter its
        # existing governed terminality path.  It does not imply automatic
        # execution when any signed resolution explicitly requires the owner.
        "recommendations_authorized": proposal_ratified,
        "automatic_dispatch_authorized": bool(
            proposal_ratified and not owner_decision_routing_required
        ),
        "owner_decision_routing_required": owner_decision_routing_required,
        "recommendation_routing": (
            "owner_decision_required"
            if owner_decision_routing_required
            else "automatic_system_decision"
            if proposal_ratified
            else "withheld"
        ),
        "blocked_by": blocked_by,
        "challenged_by": [item["participant"] for item in challenged_reports],
        "challenge_dispositions": [
            {
                **item,
                "disposition": challenge_disposition,
                "closed_by": closing_participant,
                "closing_report_run_id": str(closing_report["agent_run_id"]),
                "reason": str(closing_content["ratification_reason"]),
            }
            for item in challenged_reports
        ],
        "owner_decision_required_by": owner_decision_required_by,
        "resolution_positions": resolution_positions,
        "next_step_or_trigger": str(closing_content["recommended_next_step"]),
    }
    if len(discussion) != expected_report_count or len(discussion) < 3:
        return _meeting_failure("minimum_three_bound_rounds_missing")

    canonical_discussion: list[dict[str, Any]] = []
    for global_round, (round_item, report) in enumerate(
        zip(discussion, canonical_reports, strict=True),
        start=1,
    ):
        expected_note = str(report["report_content"].get("note") or "").strip()
        if (
            _integer(round_item.get("round")) != global_round
            or _integer(round_item.get("phase_index")) != int(report["phase_index"])
            or str(round_item.get("phase") or "").strip() != report["phase"]
            or str(round_item.get("speaker") or "").strip() != report["display_name"]
            or str(round_item.get("note") or "").strip() != expected_note
            or str(round_item.get("participant_report_run_id") or "").strip()
            != report["agent_run_id"]
            or str(round_item.get("provenance") or "").strip()
            != PARTICIPANT_REPORT_PROVENANCE
        ):
            return _meeting_failure("transcript_round_not_bound_to_canonical_report")
        report_content = dict(report["report_content"])
        canonical_item = {
            "round": global_round,
            "phase": report["phase"],
            "phase_index": report["phase_index"],
            "speaker": report["display_name"],
            "note": expected_note,
            "position": report_content["position"],
            "risks": list(report_content["risks"]),
            "recommended_next_step": report_content["recommended_next_step"],
            "owner_decision_required": report_content["owner_decision_required"],
            **(
                {
                    "proposal_disposition": report_content["proposal_disposition"],
                    "ratification_reason": report_content["ratification_reason"],
                }
                if report["is_closing_report"]
                else {}
            ),
            "participant_report_run_id": report["agent_run_id"],
            "provenance": PARTICIPANT_REPORT_PROVENANCE,
        }
        canonical_discussion.append(canonical_item)

    canonical_report_projection = [
        {key: value for key, value in report.items() if key != "report_content"}
        for report in canonical_reports
    ]
    transcript_sha = semantic_sha256(canonical_discussion)
    canonical_evidence = {
        "schema_version": MEETING_EVIDENCE_SCHEMA_VERSION,
        "meeting_id": meeting_id,
        "cycle_id": cycle_id,
        "workspace_key": canonical_workspace,
        "standup_kind": standup_kind,
        "transcript_provenance": "compiled_from_signed_canonical_participant_reports",
        "promotion_payload_sha256": promotion_sha256,
        "participant_report_run_ids": canonical_run_ids,
        "participant_reports": canonical_report_projection,
        "transcript_sha256": transcript_sha,
        "proposal_ratification": canonical_ratification,
    }
    supplied_reports = evidence.get("participant_reports")
    if supplied_reports not in (None, []) and supplied_reports != canonical_report_projection:
        return _meeting_failure("caller_supplied_report_receipt_mismatch")
    supplied_transcript_sha = str(evidence.get("transcript_sha256") or "").strip()
    if supplied_transcript_sha and supplied_transcript_sha.removeprefix("sha256:") != transcript_sha:
        return _meeting_failure("transcript_hash_mismatch")
    return {
        "is_meeting": True,
        "state": "verified_independent_agent_meeting",
        "reason": "signed_canonical_participant_reports_verified",
        "canonical_meeting_evidence": canonical_evidence,
        "canonical_discussion": canonical_discussion,
        "canonical_promotion_claims": promotion_claims,
        "canonical_ratification": canonical_ratification,
    }


def is_verified_meeting_record(
    payload: Mapping[str, Any] | None,
    *,
    source: str | None = None,
    expected_participants: Sequence[str] | None = None,
    workspace_key: str | None = None,
    verify_current_identity_pack: bool = False,
    promotion_payload: Mapping[str, Any] | object | None = None,
) -> bool:
    return bool(
        meeting_record_truth(
            payload,
            source=source,
            expected_participants=expected_participants,
            workspace_key=workspace_key,
            verify_current_identity_pack=verify_current_identity_pack,
            promotion_payload=promotion_payload,
        )["is_meeting"]
    )


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def classify_standup(standup: StandupEntry, *, now: datetime | None = None) -> dict[str, Any]:
    """Describe whether a standup is fresh and whether it produced decisions."""

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("Standup evaluation time must include an ai_clone_utc timezone offset.")
    current_time = current_time.astimezone(timezone.utc)
    workspace_key = canonicalize_workspace_key(getattr(standup, "workspace_key", None), default="shared_ops")
    payload = dict(getattr(standup, "payload", {}) or {})
    observed_at, freshness_clock = resolve_payload_observation(
        payload,
        created_at=getattr(standup, "created_at", None),
    )
    commitments = _items(getattr(standup, "commitments", []))
    blockers = _items(getattr(standup, "blockers", []))
    needs = _items(getattr(standup, "needs", []))
    decisions = _items(payload.get("decisions"))
    pm_updates = _items(payload.get("pm_updates"))
    pm_recommendations = _items(payload.get("pm_recommendations"))
    summary = _text(payload.get("summary"))

    freshness_limit = STANDUP_FRESHNESS_HOURS.get(workspace_key, DEFAULT_STANDUP_FRESHNESS_HOURS)
    if observed_at is None:
        age_hours = None
        freshness = "invalid"
    else:
        age_hours = max(0.0, (current_time - observed_at).total_seconds() / 3600)
        freshness = (
            "degraded"
            if freshness_clock == "legacy_created_at_fallback"
            else "current"
            if age_hours <= freshness_limit
            else "stale"
        )
    decision_yield = len(decisions) + len(pm_updates) + len(pm_recommendations)

    if not summary and not commitments and not blockers and not needs:
        quality = "empty"
        quality_reason = "The standup contains no summary, commitment, blocker, or owner need."
    elif len(commitments) >= 4 and decision_yield == 0:
        quality = "ceremonial"
        quality_reason = "The standup repeats several commitments without recording a decision or PM handoff."
    elif blockers and decision_yield == 0:
        quality = "unrouted_blocker"
        quality_reason = "The standup names a blocker without a recorded decision or PM handoff."
    else:
        quality = "actionable"
        quality_reason = "The standup produced a bounded update, decision, or execution handoff."

    return {
        "workspace_key": workspace_key,
        "freshness": freshness,
        "freshness_limit_hours": freshness_limit,
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "observed_at": utc_iso(observed_at) if observed_at is not None else None,
        "freshness_clock": freshness_clock,
        "freshness_degraded": freshness_clock == "legacy_created_at_fallback",
        "quality": quality,
        "quality_reason": quality_reason,
        "decision_yield": decision_yield,
        "commitment_count": len(commitments),
        "blocker_count": len(blockers),
        "owner_need_count": len(needs),
        "has_decision_output": decision_yield > 0,
    }
