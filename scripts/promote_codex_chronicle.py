#!/usr/bin/env python3
"""Promote Chronicle/standup signal into durable memory and PM recommendation files."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
SCRIPT_DIR = WORKSPACE_ROOT / "scripts"
DEFAULT_PREP_ROOT = MEMORY_ROOT / "standup-prep"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _latest_prep(prep_root: Path, standup_kind: str) -> Path | None:
    matches = sorted((prep_root / standup_kind).glob("*.json"))
    return matches[-1] if matches else None


def _append_markdown(path: Path, heading: str, body: str) -> None:
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "append_markdown_block.py"),
        str(path),
        "--heading",
        heading,
        "--body",
        body,
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-json", help="Path to a standup prep JSON file.")
    parser.add_argument("--prep-root", default=str(DEFAULT_PREP_ROOT))
    parser.add_argument("--standup-kind", default="executive_ops")
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--write-learnings", action="store_true")
    parser.add_argument("--write-pm-recommendations", action="store_true")
    args = parser.parse_args()

    prep_path = Path(args.prep_json).expanduser() if args.prep_json else _latest_prep(Path(args.prep_root), args.standup_kind)
    if prep_path is None or not prep_path.exists():
        raise SystemExit("No standup prep JSON found to promote.")

    prep = json.loads(prep_path.read_text(encoding="utf-8"))
    promotions = prep.get("memory_promotions") or []
    pm_updates = prep.get("pm_updates") or []
    pm_updates_blocked_reason = prep.get("pm_updates_blocked_reason")
    timestamp = datetime.now().astimezone()
    daily_path = MEMORY_ROOT / f"{timestamp:%Y-%m-%d}.md"

    promotion_lines = [
        f"- Workspace: `{args.workspace_key}`",
        f"- Prep Source: `{prep_path}`",
        "",
        "### Durable Memory Candidates",
    ]
    if not promotions:
        promotion_lines.append("- None.")
    else:
        for item in promotions:
            promotion_lines.append(f"- `{item.get('target')}`: {item.get('content')}")

    promotion_lines.extend(["", "### PM Recommendation Candidates"])
    if not pm_updates:
        if pm_updates_blocked_reason:
            reason_label = {
                "pm_snapshot_unavailable": "Blocked: PM snapshot unavailable during prep.",
            }.get(pm_updates_blocked_reason, f"Blocked: {pm_updates_blocked_reason}")
            promotion_lines.append(f"- None. ({reason_label})")
        else:
            promotion_lines.append("- None.")
    else:
        for item in pm_updates:
            promotion_lines.append(f"- `{item.get('workspace_key')}`: {item.get('title')}")

    _append_markdown(
        daily_path,
        f"## Codex Chronicle Promotion — {timestamp:%Y-%m-%d %H:%M %Z}",
        "\n".join(promotion_lines),
    )

    learnings_written = 0
    if args.write_learnings:
        learnings = [
            item.get("content")
            for item in promotions
            if item.get("target") == "learnings" and isinstance(item.get("content"), str)
        ]
        if learnings:
            _append_markdown(
                MEMORY_ROOT / "LEARNINGS.md",
                f"## Chronicle Promotions — {timestamp:%Y-%m-%d}",
                "\n".join(f"- {item}" for item in learnings),
            )
            learnings_written = len(learnings)

    recommendation_path: Path | None = None
    if args.write_pm_recommendations and pm_updates and not pm_updates_blocked_reason:
        recommendation_path = MEMORY_ROOT / "pm-recommendations" / f"{timestamp.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}.json"
        _write_json(
            recommendation_path,
            {
                "schema_version": "pm_recommendations/v1",
                "recommendation_id": str(uuid.uuid4()),
                "created_at": _iso(_now()),
                "workspace_key": args.workspace_key,
                "source": "codex_chronicle_promotion",
                "prep_json": str(prep_path),
                "pm_updates": pm_updates,
            },
        )

    print(f"Promoted Chronicle prep into {daily_path}")
    if learnings_written:
        print(f"Appended {learnings_written} learning entries to {MEMORY_ROOT / 'LEARNINGS.md'}")
    if recommendation_path is not None:
        print(f"PM recommendations: {recommendation_path}")
    elif args.write_pm_recommendations and pm_updates_blocked_reason:
        print(f"Skipped PM recommendation write: {pm_updates_blocked_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
