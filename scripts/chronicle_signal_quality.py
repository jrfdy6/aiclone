from __future__ import annotations

import re
from typing import Any


LOW_SIGNAL_EXACT = {
    "continue",
    "please continue",
    "proceed",
    "go ahead",
    "do it all",
    "ok",
    "okay",
    "okay thanks",
    "ok thanks",
    "sounds good",
    "yes",
    "yes please",
    "yes please do it",
    "yes please do so",
    "yes please do that",
    "yes please do this",
    "yes please do that now",
    "ok please continue",
    "ok please do it",
    "ok please do this",
    "ok please do that",
    "ok please complete all of this",
    "ok please execute the plan",
    "please do it",
    "please do so",
    "please do that",
    "please do this",
}
ACK_WORDS = {"ok", "okay", "yes", "sure", "fine", "thanks", "thank", "please", "continue", "proceed", "go", "ahead"}
ACTION_PREFIXES = (
    "can you ",
    "could you ",
    "please ",
    "help me ",
    "show me ",
    "give me ",
    "explain ",
    "review ",
    "fix ",
    "deploy ",
    "make ",
    "create ",
    "update ",
    "sync ",
    "wire ",
    "match ",
    "ship ",
    "push ",
    "pull ",
)
ACTION_KEYWORDS = (
    "deploy",
    "fix",
    "review",
    "explain",
    "create",
    "make",
    "update",
    "sync",
    "wire",
    "match",
    "diagram",
    "summarize",
    "audit",
    "investigate",
    "ship",
    "push",
    "pull",
)
MATERIAL_HINTS = (
    "frontend",
    "backend",
    "workspace",
    "pm card",
    "standup",
    "stand up",
    "memory",
    "persistent state",
    "cron",
    "brief",
    "deploy",
    "error",
    "bug",
    "broken",
    "blocker",
    "railway",
)
NEGATED_BLOCKER_PATTERNS = (
    "no error",
    "no errors",
    "without error",
    "without errors",
    "no blocker",
    "no blockers",
    "not broken anymore",
    "working now",
    "works now",
    "resolved without error",
)
BLOCKER_PATTERNS = (
    "error",
    "failed",
    "not working",
    "blocker",
    "issue",
    "problem",
    "broken",
    "unreachable",
    "fallback",
    "mismatch",
    "drift",
)
TRANSCRIPT_MARKERS = (
    "progress pulse digest",
    "morning daily brief",
    "latest handoff summary",
    "new handoff entries",
    "follow-up status",
    "status update",
    "checked at:",
    "new codex handoff entries delivered",
)
MAINTENANCE_BOILERPLATE = (
    "continue regular checks on crons and context",
    "addressed blockers surrounding codex handoff entries",
    "no additional maintenance signals to report",
    "digest delivered based on new handoff signals",
    "no further action needed",
)
SIGNAL_FIELDS = (
    "decisions",
    "blockers",
    "project_updates",
    "learning_updates",
    "identity_signals",
    "mindset_signals",
    "outcomes",
    "follow_ups",
    "memory_promotions",
    "pm_candidates",
)


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_signal_text(value: Any) -> str:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    for prefix in ("latest signal:", "latest handoff summary:", "summary:"):
        if lowered.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def compact_lower(value: Any) -> str:
    normalized = normalize_text(value).lower()
    normalized = re.sub(r"[^a-z0-9 ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def is_low_signal_ack(value: Any) -> bool:
    compact = compact_lower(value)
    if not compact:
        return False
    if compact in LOW_SIGNAL_EXACT:
        return True
    if any(hint in compact for hint in MATERIAL_HINTS):
        return False
    words = compact.split()
    if words and len(words) <= 4 and all(word in ACK_WORDS for word in words):
        return True
    return False


def looks_like_action_request(value: Any) -> bool:
    text = normalize_text(value)
    lowered = text.lower()
    if not text or is_low_signal_ack(text):
        return False
    if lowered.startswith(ACTION_PREFIXES):
        return True
    if "?" in text and any(keyword in lowered for keyword in ACTION_KEYWORDS):
        return True
    if any(phrase in lowered for phrase in ("fresh deploy", "fix these errors", "match the backend")):
        return True
    return False


def looks_like_negated_blocker(value: Any) -> bool:
    lowered = compact_lower(value)
    return any(pattern in lowered for pattern in NEGATED_BLOCKER_PATTERNS)


def looks_like_blocker(value: Any) -> bool:
    lowered = compact_lower(value)
    if not lowered or looks_like_negated_blocker(lowered):
        return False
    return any(pattern in lowered for pattern in BLOCKER_PATTERNS)


def looks_like_digest_transcript(value: Any) -> bool:
    lowered = compact_lower(value)
    if "neo app" in lowered:
        return True
    return any(marker in lowered for marker in TRANSCRIPT_MARKERS)


def is_boilerplate_maintenance_text(value: Any) -> bool:
    lowered = compact_lower(clean_signal_text(value))
    return any(pattern in lowered for pattern in MAINTENANCE_BOILERPLATE)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]
    normalized = normalize_text(value)
    return [normalized] if normalized else []


def entry_has_material_signal(entry: dict[str, Any]) -> bool:
    for field in SIGNAL_FIELDS:
        values = _as_list(entry.get(field))
        for value in values:
            value = clean_signal_text(value)
            if field == "blockers":
                if looks_like_blocker(value) and not is_boilerplate_maintenance_text(value):
                    return True
                continue
            if is_boilerplate_maintenance_text(value):
                continue
            if field in {"follow_ups", "pm_candidates", "project_updates"} and looks_like_action_request(value):
                return True
            if not is_low_signal_ack(value):
                return True
    summary = clean_signal_text(entry.get("summary"))
    if summary and not summary.lower().startswith("synced "):
        return not is_low_signal_ack(summary)
    return False


def entry_primary_signal(entry: dict[str, Any]) -> str:
    for field in ("blockers", "pm_candidates", "follow_ups", "project_updates", "decisions", "outcomes"):
        for value in _as_list(entry.get(field)):
            value = clean_signal_text(value)
            if field == "blockers" and not looks_like_blocker(value):
                continue
            if is_boilerplate_maintenance_text(value):
                continue
            if field != "blockers" and is_low_signal_ack(value):
                continue
            return value
    summary = clean_signal_text(entry.get("summary"))
    if summary and not summary.lower().startswith("synced ") and not is_low_signal_ack(summary):
        return summary
    return ""
