#!/usr/bin/env python3
"""Sync recent Codex history into the canonical Codex Chronicle lane."""
from __future__ import annotations

import argparse
import json
import re
import uuid
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
DEFAULT_HISTORY_PATH = Path("/Users/neo/.codex/history.jsonl")
DEFAULT_CHRONICLE_PATH = MEMORY_ROOT / "codex_session_handoff.jsonl"
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
        value = _normalize_text(item)
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


def _select_signal_items(records: list[dict[str, Any]], patterns: Iterable[str]) -> list[str]:
    matched: list[str] = []
    for record in records:
        for sentence in _split_sentences(str(record.get("text") or "")):
            if _is_noise(sentence):
                continue
            lowered = sentence.lower()
            if any(pattern in lowered for pattern in patterns):
                matched.append(sentence)
    return _trim_items(matched)


def _extract_phrase_signals(records: list[dict[str, Any]]) -> list[str]:
    phrases: list[str] = []
    for record in records:
        text = str(record.get("text") or "")
        for match in re.findall(r'"([^"]{8,120})"', text):
            if _is_noise(match):
                continue
            phrases.append(match)
    return _trim_items(phrases, limit=4, max_chars=120)


def _build_summary(records: list[dict[str, Any]], workspace_tags: list[str]) -> str:
    session_count = len({str(item.get("session_id") or "") for item in records if item.get("session_id")})
    latest_text = _normalize_text(str(records[-1].get("text") or "")) if records else ""
    latest_text = latest_text[:160].rstrip() + ("..." if len(latest_text) > 160 else "")
    focus = ", ".join(workspace_tags[:3]) if workspace_tags else "shared_ops"
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

    decisions = _select_signal_items(records, DECISION_PATTERNS)
    blockers = _select_signal_items(records, BLOCKER_PATTERNS)
    project_updates = _trim_items(
        [
            record["text"]
            for record in records
            if any(tag.replace("-", " ") in record["text"].lower() for tag in tags) and not _is_noise(record["text"])
        ],
        limit=6,
        max_chars=200,
    )
    learning_updates = _select_signal_items(records, LEARNING_PATTERNS)
    identity_signals = _select_signal_items(records, IDENTITY_PATTERNS)
    mindset_signals = _select_signal_items(records, MINDSET_PATTERNS)
    phrase_signals = _extract_phrase_signals(records)
    outcomes = _select_signal_items(records, OUTCOME_PATTERNS)

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
        + [item for item in blockers if item],
        limit=6,
    )
    memory_promotions = _trim_items(identity_signals + learning_updates + mindset_signals, limit=6)
    pm_candidates = _trim_items(project_updates + follow_ups, limit=6)

    summary = _build_summary(records, tags)
    importance = "high" if blockers or identity_signals or memory_promotions else "medium"

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

    _append_jsonl(chronicle_path, payload)
    max_ts = max(int(item.get("ts") or 0) for item in records)
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
        },
    )
    print(summary)
    print(f"Chronicle: {chronicle_path}")
    print(f"State: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
