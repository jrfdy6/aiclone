from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.operator_story_signal_service import (
    DEFAULT_WORKSPACE_KEY,
    REPORT_ROOT,
    _normalize_text,
    _truncate,
    build_operator_story_signals_payload,
)


OPERATOR_STORY_REPORT_PATH = REPORT_ROOT / "operator_story_signals_latest.json"
CONTENT_SAFE_OPERATOR_LESSONS_PATH = REPORT_ROOT / "content_safe_operator_lessons_latest.json"
MAX_LESSONS = 10
_PATH_RE = re.compile(r"/Users/neo/[^\s,)\]]+")
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"\s+([,.;:])")
_BACKTICK_RE = re.compile(r"`+")
_SAFE_ANGLES = {
    "workflow": {"workflow", "handoff", "lane", "coordination", "clarity"},
    "delegation": {"delegation", "delegate", "ownership", "handoff", "manager"},
    "documentation": {"playbook", "documented", "documentation", "artifact", "repeatable"},
    "memory": {"memory", "chronicle", "brief", "history", "signal"},
    "content": {"content", "voice", "persona", "story", "proof"},
    "execution": {"execution", "feedback", "closure", "follow-through", "review"},
}
_GENERIC_TOPIC_TAGS = {
    "artifact": "proof",
    "brain": "systems",
    "brief": "communication",
    "codex": "ai-workflows",
    "content": "content-systems",
    "execution": "execution",
    "memory": "memory",
    "openclaw": "systems",
    "operator": "operations",
    "persona": "voice",
    "pm": "execution",
    "railway": "systems",
    "workflow": "workflow",
    "workspace": "operations",
}
_TERM_REPLACEMENTS = (
    (re.compile(r"\bJean-Claude\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bNeo\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bCodex\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bOpenClaw\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bRailway\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bFEEZIE\b", re.IGNORECASE), "the content system"),
    (re.compile(r"\bfusion-os\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\blinkedin-content-os\b", re.IGNORECASE), "the content lane"),
    (re.compile(r"\beasyoutfitapp\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\bai-swag-store\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\bagc\b", re.IGNORECASE), "a workspace"),
    (re.compile(r"\bshared_ops\b", re.IGNORECASE), "the shared workflow"),
    (re.compile(r"\bChronicle\b", re.IGNORECASE), "memory"),
    (re.compile(r"\bPM card\b", re.IGNORECASE), "task"),
    (re.compile(r"\bPM\b", re.IGNORECASE), "execution"),
    (re.compile(r"\bSOP\b", re.IGNORECASE), "playbook"),
    (re.compile(r"\bwork order\b", re.IGNORECASE), "handoff"),
    (re.compile(r"\bdispatch\b", re.IGNORECASE), "handoff"),
    (re.compile(r"\bwrite-back\b", re.IGNORECASE), "feedback loop"),
    (re.compile(r"\bqueue\b", re.IGNORECASE), "workflow"),
    (re.compile(r"\bworkspace lane\b", re.IGNORECASE), "workflow lane"),
    (re.compile(r"\bworkspace-agent\b", re.IGNORECASE), "delegated execution"),
    (re.compile(r"\bAPI-first\b", re.IGNORECASE), "shared"),
)
_POST_REPLACEMENTS = (
    (re.compile(r"\bthe system and the system\b", re.IGNORECASE), "the system"),
    (re.compile(r"\bthe system brain jobs\b", re.IGNORECASE), "the system workflows"),
    (re.compile(r"\bdelegated execution execution\b", re.IGNORECASE), "delegated execution"),
    (re.compile(r"\bmemory execution candidates\b", re.IGNORECASE), "signals"),
    (re.compile(r"\bworkflow items\b", re.IGNORECASE), "work"),
)
_PRIVATE_MARKERS = (
    "playbook",
    "handoff",
    "content lane",
    "shared workflow",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _sanitize_public_text(value: Any) -> tuple[str, list[str]]:
    text = str(value or "")
    notes: list[str] = []
    if not text.strip():
        return "", notes
    if _PATH_RE.search(text):
        text = _PATH_RE.sub("a durable artifact", text)
        notes.append("stripped_file_paths")
    if _BACKTICK_RE.search(text):
        text = _BACKTICK_RE.sub("", text)
    for pattern, replacement in _TERM_REPLACEMENTS:
        if pattern.search(text):
            text = pattern.sub(replacement, text)
            notes.append(f"generalized:{replacement}")
    for pattern, replacement in _POST_REPLACEMENTS:
        if pattern.search(text):
            text = pattern.sub(replacement, text)
    text = _normalize_text(text)
    text = text.replace("  ", " ")
    text = _PUNCT_RE.sub(r"\1", text)
    text = _WHITESPACE_RE.sub(" ", text).strip(" -")
    return text, notes


def _topic_tags(raw_tags: list[str]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags:
        normalized = _GENERIC_TOPIC_TAGS.get(str(raw_tag or "").strip().lower())
        if normalized and normalized not in seen:
            seen.add(normalized)
            tags.append(normalized)
    return tags


def _safe_angle(*texts: str, topic_tags: list[str]) -> str:
    combined = " ".join(_normalize_text(text).lower() for text in texts if _normalize_text(text))
    for angle, terms in _SAFE_ANGLES.items():
        if any(term in combined for term in terms):
            return angle
    if topic_tags:
        return topic_tags[0]
    return "systems"


def _generic_public_proof(signal: dict[str, Any], sanitized_proof: str) -> str:
    raw_proof = _normalize_text(signal.get("proof"))
    artifacts = signal.get("artifact_paths") if isinstance(signal.get("artifact_paths"), list) else []
    combined = " ".join(part.lower() for part in (raw_proof, sanitized_proof, " ".join(str(item) for item in artifacts)) if part)
    if "delegated proof" in combined or "review" in combined or "closure" in combined:
        return "Recent system work added a clearer closure step instead of letting work stay open-ended."
    if "playbook" in combined or "documented" in combined or artifacts:
        return "Recent system work turned repeated work into documented process instead of one-off execution."
    if "persona" in combined or "content" in combined or "voice" in combined:
        return "Recent system work tied content decisions more closely to lived proof and operator judgment."
    if "memory" in combined or "brief" in combined or "chronicle" in combined:
        return "Recent system work made the system remember lessons in a way that is easier to reuse."
    if "handoff" in combined or "delegat" in combined:
        return "Recent system work made handoffs more explicit and easier to trust."
    return "Recent system work produced clearer proof, tighter feedback loops, and less drift between intention and execution."


def _macro_thesis(signal: dict[str, Any], sanitized_claim: str, sanitized_lesson: str) -> str:
    combined = " ".join(
        part.lower()
        for part in (
            _normalize_text(signal.get("claim")),
            _normalize_text(signal.get("lesson")),
            _normalize_text(signal.get("proof")),
        )
        if part
    )
    if "direct" in combined and "execution" in combined:
        return "Simple work moves faster when ownership stays direct instead of bouncing between layers."
    if "delegat" in combined and "lane" in combined:
        return "Delegation only helps when the handoff is explicit and the lane stays bounded."
    if "playbook" in combined or "documented" in combined or "one-off experiment" in combined:
        return "If a process matters more than once, it probably needs a playbook."
    if "closure" in combined or "no additional execution" in combined or "accepted the delegated proof" in combined:
        return "A system is not done when motion stops. It is done when closure is explicit."
    if "canonical memory" in combined or "promotion boundary" in combined or "strong signal" in combined:
        return "Strong signals need a review loop before they become execution pressure."
    if "backlog" in combined or "proof anchors" in combined or "content" in combined:
        return "Content gets stronger when it stays tied to lived proof instead of generic ideas."
    if "memory" in combined or "chronicle" in combined or "brief" in combined:
        return "Systems get more useful when they remember the right lesson instead of just storing more history."
    return sanitized_lesson or sanitized_claim


def _public_takeaway(sanitized_claim: str, sanitized_lesson: str) -> str:
    candidate = sanitized_lesson or sanitized_claim
    if not candidate:
        return ""
    normalized = candidate.rstrip(".")
    lowered = normalized.lower()
    if "proof anchors" in lowered or "approval state" in lowered:
        return "Content quality improves when ideas are tied to real proof and clear readiness signals."
    if lowered.startswith("to enhance the context flow"):
        return "Documentation matters most when it closes the loop between memory and execution."
    if lowered.startswith("rewired the system workflows"):
        return "Workflows get stronger when the handoff is part of the system instead of an afterthought."
    if "executive leadership" in lowered or "workflow lane" in lowered:
        return "Execution works better when the work stays in its lane and summaries travel upward."
    if "title normalization" in lowered or "semantic gating" in lowered:
        return "Signals need structure and review before they turn into execution pressure."
    if "split-brain" in lowered:
        return "Delegated work breaks down when updates live in different places."
    if normalized and normalized[0].islower():
        normalized = normalized[0].upper() + normalized[1:]
    return normalized + "."


def _workspace_scope(signal: dict[str, Any]) -> str:
    workspace_keys = [str(item or "").strip() for item in signal.get("workspace_keys") or [] if str(item or "").strip()]
    if not workspace_keys:
        return "shared_pattern"
    if workspace_keys == ["shared_ops"]:
        return "shared_pattern"
    if len(workspace_keys) == 1:
        return "single_workspace_pattern"
    return "cross_workspace_pattern"


def _content_safe_lesson(signal: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(signal, dict):
        return None
    route = str(signal.get("route") or "").strip()
    if route not in {"content_reservoir", "persona_candidate"}:
        return None

    sanitized_claim, claim_notes = _sanitize_public_text(signal.get("claim"))
    sanitized_lesson, lesson_notes = _sanitize_public_text(signal.get("lesson"))
    sanitized_proof, proof_notes = _sanitize_public_text(signal.get("proof"))
    if not sanitized_claim and not sanitized_lesson:
        return None

    macro_thesis = _macro_thesis(signal, sanitized_claim, sanitized_lesson)
    public_takeaway = _public_takeaway(sanitized_claim, sanitized_lesson)
    public_proof = _generic_public_proof(signal, sanitized_proof)
    generic_topic_tags = _topic_tags([str(item) for item in signal.get("topic_tags") or []])
    safe_angle = _safe_angle(macro_thesis, public_takeaway, public_proof, topic_tags=generic_topic_tags)
    redaction_notes = sorted(set(claim_notes + lesson_notes + proof_notes))
    private_marker_count = sum(1 for marker in _PRIVATE_MARKERS if marker in " ".join((macro_thesis, public_takeaway, public_proof)).lower())

    title = _truncate(macro_thesis, 100)
    return {
        "id": str(signal.get("id") or ""),
        "title": title,
        "macro_thesis": _truncate(macro_thesis, 220),
        "public_takeaway": _truncate(public_takeaway, 260),
        "public_proof": _truncate(public_proof, 220),
        "safe_angle": safe_angle,
        "topic_tags": generic_topic_tags,
        "visibility": "public_safe",
        "workspace_scope": _workspace_scope(signal),
        "source_signal_id": str(signal.get("id") or ""),
        "source_kind": str(signal.get("source_kind") or ""),
        "source_route": route,
        "created_at": str(signal.get("created_at") or _utcnow_iso()),
        "redaction_notes": redaction_notes,
        "private_marker_count": private_marker_count,
    }


def _dedupe_lessons(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lesson in lessons:
        key = _normalize_text(lesson.get("macro_thesis")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(lesson)
        if len(deduped) >= MAX_LESSONS:
            break
    return deduped


def build_content_safe_operator_lessons_payload(
    *,
    workspace_key: str = DEFAULT_WORKSPACE_KEY,
    operator_story_payload: dict[str, Any] | None = None,
    operator_story_report_path: Path | None = None,
) -> dict[str, Any]:
    source_payload = operator_story_payload
    report_path = (operator_story_report_path or OPERATOR_STORY_REPORT_PATH).expanduser()
    if not isinstance(source_payload, dict):
        source_payload = _load_json(report_path)
    if not isinstance(source_payload, dict):
        source_payload = build_operator_story_signals_payload(workspace_key=workspace_key)

    raw_signals = source_payload.get("signals") if isinstance(source_payload.get("signals"), list) else []
    lessons = [lesson for lesson in (_content_safe_lesson(signal) for signal in raw_signals) if lesson]
    lessons = sorted(
        lessons,
        key=lambda item: (
            1 if item.get("source_route") == "persona_candidate" else 0,
            1 if item.get("workspace_scope") == "shared_pattern" else 0,
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )
    lessons = _dedupe_lessons(lessons)

    by_angle: dict[str, int] = {}
    by_source_kind: dict[str, int] = {}
    by_workspace_scope: dict[str, int] = {}
    for lesson in lessons:
        by_angle[lesson["safe_angle"]] = by_angle.get(lesson["safe_angle"], 0) + 1
        by_source_kind[lesson["source_kind"]] = by_source_kind.get(lesson["source_kind"], 0) + 1
        by_workspace_scope[lesson["workspace_scope"]] = by_workspace_scope.get(lesson["workspace_scope"], 0) + 1

    return {
        "generated_at": _utcnow_iso(),
        "workspace": workspace_key,
        "source_snapshot_type": "operator_story_signals",
        "source_generated_at": source_payload.get("generated_at"),
        "source_report_path": str(report_path),
        "lessons": lessons,
        "counts": {
            "total": len(lessons),
            "by_angle": by_angle,
            "by_source_kind": by_source_kind,
            "by_workspace_scope": by_workspace_scope,
        },
        "notes": {
            "design_rule": "Only public-safe macro lessons belong in content prompts. Internal mechanics stay in the operator story lane.",
            "visibility": "public_safe",
        },
    }


def render_content_safe_operator_lessons_markdown(payload: dict[str, Any]) -> str:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    lines = [
        "# Content-Safe Operator Lessons",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Lesson count: `{counts.get('total', 0)}`",
        f"- Angles: `{json.dumps(counts.get('by_angle') or {}, sort_keys=True)}`",
        "",
    ]
    for lesson in payload.get("lessons") or []:
        if not isinstance(lesson, dict):
            continue
        lines.extend(
            [
                f"## {lesson.get('title') or 'Lesson'}",
                f"- Angle: `{lesson.get('safe_angle')}`",
                f"- Scope: `{lesson.get('workspace_scope')}`",
                f"- Source: `{lesson.get('source_kind')}`",
                f"- Thesis: {lesson.get('macro_thesis') or ''}",
                f"- Takeaway: {lesson.get('public_takeaway') or ''}",
                f"- Public proof: {lesson.get('public_proof') or ''}",
            ]
        )
        tags = lesson.get("topic_tags") or []
        if tags:
            lines.append(f"- Topic tags: `{', '.join(tags)}`")
        notes = lesson.get("redaction_notes") or []
        if notes:
            lines.append(f"- Redaction notes: `{', '.join(notes[:6])}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
