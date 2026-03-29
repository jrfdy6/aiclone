from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from app.models.automations import Automation, AutomationInstruction


def _dt(hours_ago: int = 0, hours_ahead: int = 0) -> datetime:
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    if hours_ago:
        return now - timedelta(hours=hours_ago)
    if hours_ahead:
        return now + timedelta(hours=hours_ahead)
    return now


def _instructions(*steps: str) -> List[AutomationInstruction]:
    return [AutomationInstruction(title=f"Step {idx + 1}", detail=detail) for idx, detail in enumerate(steps)]


def list_automations() -> List[Automation]:
    """Return the automation definitions backing Mission Control + Brain views."""

    automations: List[Automation] = [
        Automation(
            id="workspace_backup",
            name="Workspace Backup (GitHub)",
            description="Nightly snapshot of /workspace (minus secrets) pushed to the private GitHub repo for fast restores.",
            type="scheduled",
            status="active",
            schedule="Daily @ 02:00 ET",
            cron="0 7 * * *",
            channel="github",
            last_run_at=_dt(hours_ago=2),
            next_run_at=_dt(hours_ahead=22),
            metrics={
                "destination": "github.com/clear-mud/aiclone-backups",
                "excludes": "secrets/, node_modules/, .next/",
                "isolation": "true",
            },
            instructions=_instructions(
                "Export workspace minus secrets + heavy artifacts",
                "Encrypt archive and push to GitHub using PAT",
                "Post summary to Ops → Mission Control",
            ),
            notes="Runs as an isolated session so backups survive even if chat is idle.",
        ),
        Automation(
            id="self_improvement",
            name="Overnight Self-Improvement",
            description="Audits one Goat OS module nightly and stages a single improvement in the lab environment.",
            type="scheduled",
            status="active",
            schedule="Daily @ 01:00 ET",
            cron="0 6 * * *",
            channel="lab/staging",
            isolation=True,
            last_run_at=_dt(hours_ago=7),
            next_run_at=_dt(hours_ahead=17),
            metrics={
                "modules": "ops, brain, lab (rotation)",
                "staging_port": "8900",
                "promotion": "manual approval required",
            },
            instructions=_instructions(
                "Snapshot module state + read SOUL/USER context",
                "Propose + build one improvement in staging",
                "Log outcome in Lab → Build Logs and ping Ops",
            ),
            notes="Never touches prod without approval; writes to Lab build logs and automation audit trail.",
        ),
        Automation(
            id="persona_bundle_sync",
            name="Persona Bundle Sync",
            description="Polls committed Brain promotions and writes them into the local canonical persona bundle so canon survives deploys.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="*/5 * * * *",
            channel="brain/persona-bundle",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=datetime.utcnow().replace(second=0, microsecond=0) + timedelta(minutes=5),
            metrics={
                "source": "Brain committed persona deltas",
                "target": "knowledge/persona/feeze/**",
                "delivery": "local workspace bundle sync",
            },
            instructions=_instructions(
                "Read committed persona deltas from the Brain API",
                "Write new promotion items into the local persona bundle files",
                "Mark synced deltas so the same canon is not written twice",
            ),
            notes="Runs on the local machine because Railway filesystem writes are not the durable source of truth for canon.",
        ),
        Automation(
            id="daily_brief",
            name="Morning Daily Brief",
            description="Generates the daily Markdown brief with priorities, cron summary, and AI Pulse news.",
            type="scheduled",
            status="active",
            schedule="Daily @ 07:30 ET",
            cron="30 12 * * *",
            channel="brain/daily-briefs",
            isolation=True,
            last_run_at=_dt(hours_ago=1),
            next_run_at=_dt(hours_ahead=7),
            metrics={
                "news_sources": "OpenAI, Anthropic, Gemini blogs",
                "delivery": "Brain → Daily Briefs + Discord",
            },
            instructions=_instructions(
                "Summarize priorities + pending actions",
                "List cron successes/failures with timestamps",
                "Curate AI Pulse news (OpenAI/Anthropic/Gemini)",
                "Post Markdown into Brain ↦ Daily Briefs",
            ),
        ),
        Automation(
            id="rolling_docs",
            name="Rolling OS Documentation",
            description="Appends a daily change log describing how each module behaves / changed in the last 24h.",
            type="scheduled",
            status="active",
            schedule="Daily @ 00:00 ET",
            cron="0 5 * * *",
            channel="brain/system-docs",
            isolation=True,
            last_run_at=_dt(hours_ago=12),
            next_run_at=_dt(hours_ahead=12),
            metrics={
                "output": "Brain → System Docs tab",
                "scope": "ops, brain, lab tabs + cron definitions",
            },
            instructions=_instructions(
                "Inspect git/staging diffs + mission control events",
                "Describe new features, risks, and dependencies",
                "Write append-only entry inside Brain → System Docs",
            ),
            notes="Ensures every automation and UI tweak has an auditable narrative.",
        ),
    ]

    return automations
