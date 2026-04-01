#!/usr/bin/env python3
"""Append a structured Codex Chronicle event to canonical memory."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PATH = Path("/Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl")


def _read_list(values: list[str] | None, file_path: str | None) -> list[str]:
    items = [value.strip() for value in (values or []) if value and value.strip()]
    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")
        items.extend(line.strip() for line in text.splitlines() if line.strip())
    return items


def _read_summary(args: argparse.Namespace) -> str:
    if args.summary is not None:
        return args.summary.strip()
    if args.summary_file is not None:
        return Path(args.summary_file).read_text(encoding="utf-8").strip()
    return sys.stdin.read().strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="Absolute path to the canonical Chronicle JSONL file.")
    parser.add_argument("--summary", help="Short summary of what happened in Codex.")
    parser.add_argument("--summary-file", help="Path to a file containing the Chronicle summary.")
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--scope", default="shared_ops")
    parser.add_argument("--source", default="codex-cli")
    parser.add_argument("--author-agent", default="neo")
    parser.add_argument("--importance", default="medium")
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--context-usage-pct", type=int)
    parser.add_argument("--signal-type", action="append", dest="signal_types")
    parser.add_argument("--decision", action="append", dest="decisions")
    parser.add_argument("--decision-file")
    parser.add_argument("--blocker", action="append", dest="blockers")
    parser.add_argument("--blocker-file")
    parser.add_argument("--project-update", action="append", dest="project_updates")
    parser.add_argument("--project-update-file")
    parser.add_argument("--learning", action="append", dest="learning_updates")
    parser.add_argument("--learning-file")
    parser.add_argument("--identity-signal", action="append", dest="identity_signals")
    parser.add_argument("--identity-signal-file")
    parser.add_argument("--mindset-signal", action="append", dest="mindset_signals")
    parser.add_argument("--mindset-signal-file")
    parser.add_argument("--phrase-signal", action="append", dest="phrase_signals")
    parser.add_argument("--phrase-signal-file")
    parser.add_argument("--outcome", action="append", dest="outcomes")
    parser.add_argument("--outcome-file")
    parser.add_argument("--follow-up", action="append", dest="follow_ups")
    parser.add_argument("--follow-up-file")
    parser.add_argument("--memory-promotion", action="append", dest="memory_promotions")
    parser.add_argument("--memory-promotion-file")
    parser.add_argument("--pm-candidate", action="append", dest="pm_candidates")
    parser.add_argument("--pm-candidate-file")
    parser.add_argument("--artifact", action="append", dest="artifacts")
    parser.add_argument("--artifact-file")
    parser.add_argument("--tag", action="append", dest="tags")
    args = parser.parse_args()

    target = Path(args.path).expanduser()
    if not target.is_absolute():
        raise SystemExit("Target path must be absolute.")
    target.parent.mkdir(parents=True, exist_ok=True)

    summary = _read_summary(args)
    if not summary:
        raise SystemExit("A non-empty summary is required.")

    payload = {
        "schema_version": "codex_chronicle/v1",
        "entry_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": args.source,
        "author_agent": args.author_agent,
        "workspace_key": args.workspace_key,
        "scope": args.scope,
        "trigger": args.trigger,
        "context_usage_pct": args.context_usage_pct,
        "importance": args.importance,
        "summary": summary,
        "signal_types": _read_list(args.signal_types, None),
        "decisions": _read_list(args.decisions, args.decision_file),
        "blockers": _read_list(args.blockers, args.blocker_file),
        "project_updates": _read_list(args.project_updates, args.project_update_file),
        "learning_updates": _read_list(args.learning_updates, args.learning_file),
        "identity_signals": _read_list(args.identity_signals, args.identity_signal_file),
        "mindset_signals": _read_list(args.mindset_signals, args.mindset_signal_file),
        "phrase_signals": _read_list(args.phrase_signals, args.phrase_signal_file),
        "outcomes": _read_list(args.outcomes, args.outcome_file),
        "follow_ups": _read_list(args.follow_ups, args.follow_up_file),
        "memory_promotions": _read_list(args.memory_promotions, args.memory_promotion_file),
        "pm_candidates": _read_list(args.pm_candidates, args.pm_candidate_file),
        "artifacts": _read_list(args.artifacts, args.artifact_file),
        "tags": _read_list(args.tags, None),
    }

    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    print(f"Appended Codex Chronicle entry to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
