#!/usr/bin/env python3
"""Generate a weekly hygiene summary for MEMORY.md maintenance."""
from datetime import date
from pathlib import Path

workspace = Path(__file__).resolve().parents[1]
mem_dir = workspace / "memory"
report = mem_dir / "weekly_hygiene_summary.md"

if not mem_dir.is_dir():
    raise SystemExit(f"Memory directory not found at {mem_dir}")

logs = sorted(mem_dir.glob("*.md"))[-7:]
lines = [
    f"# Weekly Memory Hygiene — {date.today().isoformat()}",
    "",
]
if not logs:
    lines.append("No daily memory logs found. Run your usual capture routine first.")
else:
    lines.append("## Last 7 daily logs (newest last)")
    for log in logs:
        lines.append(f"- {log.name}")
    lines.extend([
        "",
        "## Quick prompts",
        "1. Open each of the files above and identify 1–3 takeaways worth promoting into MEMORY.md.",
        "2. Remove or merge any outdated entries from MEMORY.md so it stays lean (focus on rules, decisions, and guardrails).",
        "3. Stage and back up the journal files with git (skip credentials and openclaw.json).",
        "4. Trim HEARTBEAT.md / AGENTS.md if new rules have been added and the system prompt is growing.",
        "5. After the hygiene pass, rerun this script to refresh the summary.",
    ])

report.write_text("\n".join(lines) + "\n")
print(f"Weekly hygiene summary ready: {report}")
