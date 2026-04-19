#!/usr/bin/env python3
"""Sync recent Codex history into the canonical Codex Chronicle lane."""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
DEFAULT_HISTORY_PATH = Path("/Users/neo/.codex/history.jsonl")
from app.services.core_memory_snapshot_service import resolve_live_memory_write_path
from chronicle_signal_quality import (
    entry_has_material_signal,
    is_low_signal_ack,
    looks_like_action_request,
    looks_like_blocker,
    looks_like_digest_transcript,
    looks_like_negated_blocker,
)


DEFAULT_CHRONICLE_PATH = resolve_live_memory_write_path(WORKSPACE_ROOT, "memory/codex_session_handoff.jsonl")
DEFAULT_STATE_PATH = MEMORY_ROOT / "codex_chronicle_state.json"
REGISTRY_PATH = MEMORY_ROOT / "workspace_registry.json"

DECISION_PATTERNS = (
    "should ",
    "need to ",
    "let's ",
    "use ",
    "treat ",
    "make sure ",
    "the right move",
    "the next move",
    "the clean move",
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
OUTCOME_PATTERNS = (
    "done",
    "fixed",
    "working",
    "confirmed",
    "passed",
    "completed",
    "deployed",
    "verified",
    "clean",
)
LEARNING_PATTERNS = (
    "learned",
    "realized",
    "turns out",
    "the key",
    "important",
    "what changed",
    "the reason",
)
IDENTITY_PATTERNS = (
    "i want",
    "i need",
    "my goal",
    "about me",
    "i am",
    "i'm",
    "the goal here",
    "second brain",
)
MINDSET_PATTERNS = (
    "most importantly",
    "i think",
    "i love",
    "i don't want",
    "i do want",
    "perfect memory",
    "the strongest move",
)
NOISE_PATTERNS = (
    "neo app",
    "context usage summary",
    "current token usage",
    "current context usage",
    "flush status",
    "alert summary",
    "progress pulse",
    "context guard summary",
    "this summary will be delivered automatically",
    "this will be delivered automatically",
    "manual follow-up needed",
    "follow-up status",
    "follow-up:",
    "latest signal:",
    "no additional maintenance signals to report",
    "continue regular checks on crons and context",
    "addressed blockers surrounding codex handoff entries",
    "digest delivered based on new handoff signals",
    "no further action needed",
    "utc:",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _load_registry_terms() -> dict[str, set[str]]:
    terms: dict[str, set[str]] = {
        "linkedin-os": {"linkedin os", "linkedin", "feezie os", "feezie"},
        "fusion-os": {"fusion os", "fusion"},
        "easyoutfitapp": {"easyoutfitapp", "easy outfit", "closetai", "closet ai"},
        "ai-swag-store": {"ai swag store", "swag store"},
        "agc": {"agc"},
        "shared_ops": {"openclaw", "codex", "pm board", "standup", "cron", "heartbeat", "railway", "oracle ledger"},
    }
    if not REGISTRY_PATH.exists():
        return terms
    try:
        payload = _read_json(REGISTRY_PATH)
    except Exception:
        return terms
    workspaces = payload.get("workspaces")
    if not isinstance(workspaces, list):
        return terms
    for item in workspaces:
        if not isinstance(item, dict):
            continue
        key = str(item.get("workspace_key") or "").strip()
        if not key:
            continue
        bucket = terms.setdefault(key, set())
        for field in ("workspace_key", "display_name", "future_name"):
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                bucket.add(value.strip().lower())
    return terms


def _normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def _canonicalize_discussion_signal(text: str) -> str:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    if lowered.startswith("--- ## context") or "current fusion-os workspace is internally inconsistent" in lowered:
        return "Fusion OS needed a coherent content-and-signal operating model before weekly automation could be trusted."
    if "voice system" in lowered and "fusion academy dc" in lowered and "observation" in lowered and "guidance" in lowered:
        return (
            "Fusion content should use institutional voice, represent Fusion Academy DC, avoid first-person singular, "
            "and follow Observation -> Clarification -> Guidance."
        )
    if lowered.startswith("excellent please let me know what you need to implement"):
        return "Implement the approved Fusion operating model and audience-feedback loop."
    if "ai clone" in lowered and "workspace" in lowered and ("stand up" in lowered or "standup" in lowered):
        return "Jean-Claude should use whole-system AI Clone context to inform each workspace while only routing workspace-relevant signal into standups."
    if "jean claude" in lowered and ("multiple wrkspaces" in lowered or "multiple workspaces" in lowered):
        return "Jean-Claude needs a routing contract for using whole-system context across multiple workspaces."
    if lowered.startswith("i think a great place to start") and "jean claude" in lowered:
        return "Start with Jean-Claude's cross-workspace routing contract."
    if lowered.startswith("so he will need") and "workspace" in lowered:
        return "Jean-Claude should filter whole-system context down to the signals that matter for each workspace."
    if lowered in {"yes please do that.", "yes please do that", "please execute on both.", "please execute on both"}:
        return "Confirmed the next execution step."
    return normalized


def _split_sentences(text: str) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part and part.strip()]


def _trim_items(items: Iterable[str], *, limit: int = 6, max_chars: int = 240) -> list[str]:
    seen: set[str] = set()
    trimmed: list[str] = []
    for item in items:
        value = _canonicalize_discussion_signal(item)
        if not value:
            continue
        if len(value) > max_chars:
            value = value[: max_chars - 3].rstrip() + "..."
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        trimmed.append(value)
        if len(trimmed) >= limit:
            break
    return trimmed


def _is_noise(value: str) -> bool:
    lowered = value.lower()
    if looks_like_digest_transcript(value):
        return True
    if any(pattern in lowered for pattern in NOISE_PATTERNS):
        return True
    if value.count(":") >= 4 and len(value) > 120:
        return True
    return False


def _match_workspace_tags(records: list[dict[str, Any]], registry_terms: dict[str, set[str]]) -> tuple[list[str], str]:
    matched: Counter[str] = Counter()
    for record in records:
        text = str(record.get("text") or "").lower()
        for key, values in registry_terms.items():
            if any(term in text for term in values):
                matched[key] += 1
    if not matched:
        return ["codex", "chronicle"], "shared_ops"
    ordered = [item[0] for item in matched.most_common()]
    primary = ordered[0] if ordered else "shared_ops"
    tags = ordered[:4]
    return tags, primary


def _matches_signal_category(sentence: str, patterns: Iterable[str], *, category: str) -> bool:
    lowered = sentence.lower()
    if is_low_signal_ack(sentence):
        return False
    if category == "blocker":
        if looks_like_negated_blocker(sentence):
            return False
        return any(pattern in lowered for pattern in patterns)
    if category == "outcome" and looks_like_blocker(sentence):
        return False
    return any(pattern in lowered for pattern in patterns)


def _select_signal_items(records: list[dict[str, Any]], patterns: Iterable[str], *, category: str) -> list[str]:
    matched: list[str] = []
    for record in records:
        for sentence in _split_sentences(str(record.get("text") or "")):
            if _is_noise(sentence):
                continue
            if _matches_signal_category(sentence, patterns, category=category):
                matched.append(_canonicalize_discussion_signal(sentence))
    return _trim_items(matched)


def _select_project_updates(records: list[dict[str, Any]], workspace_tags: list[str]) -> list[str]:
    matched: list[str] = []
    workspace_terms = tuple(tag.replace("-", " ") for tag in workspace_tags)
    for record in records:
        for sentence in _split_sentences(str(record.get("text") or "")):
            if _is_noise(sentence) or is_low_signal_ack(sentence):
                continue
            lowered = sentence.lower()
            if any(term in lowered for term in workspace_terms) or looks_like_action_request(sentence) or looks_like_blocker(sentence):
                matched.append(_canonicalize_discussion_signal(sentence))
            elif len(sentence) >= 120:
                matched.append(_canonicalize_discussion_signal(sentence))
    return _trim_items(matched, limit=6, max_chars=200)


def _extract_phrase_signals(records: list[dict[str, Any]]) -> list[str]:
    phrases: list[str] = []
    for record in records:
        text = str(record.get("text") or "")
        if looks_like_digest_transcript(text):
            continue
        for match in re.findall(r'"([^"]{8,120})"', text):
            if _is_noise(match):
                continue
            phrases.append(match)
    return _trim_items(phrases, limit=4, max_chars=120)


def _latest_material_signal(records: list[dict[str, Any]]) -> str:
    for record in reversed(records):
        for sentence in reversed(_split_sentences(str(record.get("text") or ""))):
            if _is_noise(sentence) or is_low_signal_ack(sentence):
                continue
            if looks_like_action_request(sentence) or looks_like_blocker(sentence) or len(sentence) >= 80:
                return _canonicalize_discussion_signal(sentence)
    return ""


def _build_summary(records: list[dict[str, Any]], workspace_tags: list[str], *, material_signal: str) -> str:
    session_count = len({str(item.get("session_id") or "") for item in records if item.get("session_id")})
    focus = ", ".join(workspace_tags[:3]) if workspace_tags else "shared_ops"
    if not material_signal:
        return (
            f"Synced {len(records)} new Codex history entries across {session_count or 1} sessions, "
            f"touching {focus}. No durable decision, blocker, or follow-up was extracted."
        )
    latest_text = material_signal[:160].rstrip() + ("..." if len(material_signal) > 160 else "")
    return (
        f"Synced {len(records)} new Codex history entries across {session_count or 1} sessions, "
        f"touching {focus}. Latest signal: {latest_text or 'No concise summary available.'}"
    )


def _load_new_records(history_path: Path, state_path: Path, initial_tail: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = _read_json(state_path)
        except Exception:
            state = {}
    last_ts = int(state.get("last_synced_ts") or 0)

    records: list[dict[str, Any]] = []
    if last_ts > 0:
        with history_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                ts = int(payload.get("ts") or 0)
                if ts <= last_ts:
                    continue
                text = _normalize_text(str(payload.get("text") or ""))
                if not text:
                    continue
                records.append({"session_id": payload.get("session_id"), "ts": ts, "text": text})
        return records, state

    tail: deque[dict[str, Any]] = deque(maxlen=initial_tail)
    with history_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            text = _normalize_text(str(payload.get("text") or ""))
            if not text:
                continue
            tail.append({"session_id": payload.get("session_id"), "ts": int(payload.get("ts") or 0), "text": text})
    return list(tail), state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-path", default=str(DEFAULT_HISTORY_PATH))
    parser.add_argument("--chronicle-path", default=str(DEFAULT_CHRONICLE_PATH))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--initial-tail", type=int, default=20)
    parser.add_argument("--source", default="codex-history")
    parser.add_argument("--author-agent", default="neo")
    parser.add_argument("--scope", default="shared_ops")
    parser.add_argument("--workspace-key", help="Force workspace key instead of auto-detecting.")
    parser.add_argument("--trigger", default="periodic_sync")
    parser.add_argument("--context-usage-pct", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    history_path = Path(args.history_path).expanduser()
    chronicle_path = Path(args.chronicle_path).expanduser()
    state_path = Path(args.state_path).expanduser()
    if not history_path.exists():
        raise SystemExit(f"Codex history file not found: {history_path}")

    records, state = _load_new_records(history_path, state_path, args.initial_tail)
    if not records:
        print("No new Codex history to sync.")
        return 0

    registry_terms = _load_registry_terms()
    tags, detected_workspace = _match_workspace_tags(records, registry_terms)
    workspace_key = args.workspace_key or detected_workspace or "shared_ops"

    decisions = _select_signal_items(records, DECISION_PATTERNS, category="decision")
    blockers = _select_signal_items(records, BLOCKER_PATTERNS, category="blocker")
    project_updates = _select_project_updates(records, tags)
    learning_updates = _select_signal_items(records, LEARNING_PATTERNS, category="learning")
    identity_signals = _select_signal_items(records, IDENTITY_PATTERNS, category="identity")
    mindset_signals = _select_signal_items(records, MINDSET_PATTERNS, category="mindset")
    phrase_signals = _extract_phrase_signals(records)
    outcomes = _select_signal_items(records, OUTCOME_PATTERNS, category="outcome")

    signal_types: list[str] = []
    for name, values in (
        ("decision", decisions),
        ("blocker", blockers),
        ("project_update", project_updates),
        ("learning", learning_updates),
        ("identity", identity_signals),
        ("mindset", mindset_signals),
        ("phrase", phrase_signals),
        ("outcome", outcomes),
    ):
        if values:
            signal_types.append(name)

    follow_ups = _trim_items(
        [item for item in decisions if "need to " in item.lower() or "make sure " in item.lower()]
        + [item for item in project_updates if looks_like_action_request(item)]
        + [item for item in blockers if item],
        limit=6,
    )
    memory_promotions = _trim_items(identity_signals + learning_updates + mindset_signals, limit=6)
    pm_candidates = _trim_items(project_updates + follow_ups, limit=6)

    material_signal = _latest_material_signal(records)
    summary = _build_summary(records, tags, material_signal=material_signal)
    importance = "high" if blockers or identity_signals or memory_promotions else ("medium" if material_signal else "low")

    payload = {
        "schema_version": "codex_chronicle/v1",
        "entry_id": str(uuid.uuid4()),
        "created_at": _iso(_now()),
        "source": args.source,
        "author_agent": args.author_agent,
        "workspace_key": workspace_key,
        "scope": args.scope,
        "trigger": args.trigger,
        "context_usage_pct": args.context_usage_pct,
        "importance": importance,
        "summary": summary,
        "signal_types": signal_types,
        "decisions": decisions,
        "blockers": blockers,
        "project_updates": project_updates,
        "learning_updates": learning_updates,
        "identity_signals": identity_signals,
        "mindset_signals": mindset_signals,
        "phrase_signals": phrase_signals,
        "outcomes": outcomes,
        "follow_ups": follow_ups,
        "memory_promotions": memory_promotions,
        "pm_candidates": pm_candidates,
        "artifacts": [],
        "tags": _trim_items(tags, limit=6, max_chars=60),
        "material_signal": bool(material_signal),
        "signal_quality": "material" if material_signal else "low_signal",
        "source_refs": [
            {
                "session_id": item.get("session_id"),
                "ts": item.get("ts"),
            }
            for item in records[-8:]
        ],
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    max_ts = max(int(item.get("ts") or 0) for item in records)
    if args.source == "codex-history" and not entry_has_material_signal(payload):
        _write_json(
            state_path,
            {
                "last_synced_ts": max_ts,
                "last_synced_at": _iso(_now()),
                "history_path": str(history_path),
                "chronicle_path": str(chronicle_path),
                "records_synced": len(records),
                "last_entry_id": state.get("last_entry_id"),
                "workspace_key": workspace_key,
                "skipped_low_signal_batch": True,
            },
        )
        print("Skipped low-signal Codex history batch; state advanced without Chronicle write.")
        print(f"State: {state_path}")
        return 0

    _append_jsonl(chronicle_path, payload)
    _write_json(
        state_path,
        {
            "last_synced_ts": max_ts,
            "last_synced_at": _iso(_now()),
            "history_path": str(history_path),
            "chronicle_path": str(chronicle_path),
            "records_synced": len(records),
            "last_entry_id": payload["entry_id"],
            "workspace_key": workspace_key,
            "skipped_low_signal_batch": False,
        },
    )
    print(summary)
    print(f"Chronicle: {chronicle_path}")
    print(f"State: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
