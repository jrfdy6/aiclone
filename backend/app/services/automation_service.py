from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional

from app.models.automations import Automation, AutomationInstruction, AutomationRun

OPENCLAW_JOBS_PATH = Path("/Users/neo/.openclaw/cron/jobs.json")
OPENCLAW_RUNS_DIR = Path("/Users/neo/.openclaw/cron/runs")
OPENCLAW_SOURCE = "openclaw_jobs_json"
STATIC_SOURCE = "static_registry"
LOCAL_LAUNCHD_SOURCE = "local_launchd_registry"
STATIC_FALLBACK_IDS = {
    "feezie_content_pipeline",
    "persona_bundle_sync",
    "youtube_watchlist_auto_ingest",
}


def _dt(hours_ago: int = 0, hours_ahead: int = 0) -> datetime:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if hours_ago:
        return now - timedelta(hours=hours_ago)
    if hours_ahead:
        return now + timedelta(hours=hours_ahead)
    return now


def _instructions(*steps: str) -> List[AutomationInstruction]:
    return [AutomationInstruction(title=f"Step {idx + 1}", detail=detail) for idx, detail in enumerate(steps)]


def _static_automations() -> List[Automation]:
    """Return the legacy static automation definitions backing Mission Control + Brain views."""

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
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=5),
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
            description="Generates the daily Markdown brief with priorities, cron summary, and AI Pulse news, then syncs the saved markdown into the backend brief store so Brain and Ops read the same latest brief.",
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
                "Append Markdown into memory/daily-briefs.md and mirror it into /api/briefs/sync",
            ),
        ),
        Automation(
            id="youtube_watchlist_auto_ingest",
            name="YouTube Watchlist Auto-Ingest",
            description="OpenClaw-local automation that runs on the machine to discover fresh watchlist videos, retry older URL-only watchlist assets, prefer YouTube captions first, and only fall back to local audio plus a compatible Whisper runtime when needed before registering the result into the shared Brain source system.",
            type="scheduled",
            status="active",
            schedule="Every 2 hours",
            cron="0 */2 * * *",
            channel="brain/youtube-watchlist",
            isolation=True,
            last_run_at=_dt(hours_ago=2),
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(hours=2),
            metrics={
                "framework": "openclaw local workspace automation + launchd",
                "runtime": "local machine only",
                "discovery": "watchlists.yaml -> youtube_channels",
                "media_stack": "yt-dlp captions first -> ffmpeg + compatible whisper fallback",
                "cheap_task_defaults": "ollama -> gemini flash -> openai",
            },
            instructions=_instructions(
                "Resolve tracked YouTube channels and discover fresh videos from the watchlist",
                "Retry pending YouTube assets that were previously registered without transcripts",
                "Prefer downloadable captions first, then fall back to local audio + Whisper only when a compatible runtime is available",
                "Register each source into the shared Brain long-form ingest lane and refresh the FEEZIE snapshots",
            ),
            notes="Runs inside the OpenClaw workspace on the local machine because Railway does not have the media runtime required for caption download fallback, audio extraction, or transcript capture.",
        ),
        Automation(
            id="feezie_content_pipeline",
            name="FEEZIE Content Pipeline",
            description="OpenClaw-local automation that refreshes the FEEZIE workspace signal lane, rebuilds weekly planning and reaction artifacts, and materializes owner-review drafts in the FEEZIE workspace.",
            type="scheduled",
            status="active",
            schedule="Every 2 hours",
            cron="0 */2 * * *",
            channel="workspace/feezie-os",
            isolation=True,
            last_run_at=_dt(hours_ago=2),
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(hours=2),
            metrics={
                "workspace": "workspaces/linkedin-content-os",
                "runtime": "local machine only",
                "pipeline": "refresh_social_feed -> weekly_plan -> reaction_queue -> owner_review_drafts",
                "output": "plans/*.json + drafts/*.md",
            },
            instructions=_instructions(
                "Refresh safe FEEZIE source intake and rebuild the social feed artifacts",
                "Regenerate weekly plan and reaction queue from the current workspace state",
                "Materialize owner-review drafts so the workspace holds real draft files instead of only planning JSON",
            ),
            notes="Runs on the local machine so draft files and workspace plans remain durable in the workspace filesystem.",
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


def _local_launchd_automations() -> List[Automation]:
    """Return local-machine automations that are driven by launchd rather than OpenClaw jobs.json."""

    next_half_hour = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=30)
    next_five = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=5)

    return [
        Automation(
            id="brain_canonical_memory_sync",
            name="Brain Canonical Memory Sync",
            description="Local launchd worker that drains reviewed Brain routing into persistent memory files for Chronicle, learnings, and persistent state.",
            type="scheduled",
            status="active",
            schedule="Every 30 minutes",
            cron="every:1800",
            channel="brain/canonical-memory",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_half_hour,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/brain_canonical_memory_sync.py",
                "cadence_seconds": "1800",
            },
            instructions=_instructions(
                "Read queued canonical-memory routes from the Brain API",
                "Append durable updates into local persistent memory files",
                "Write a latest status report for Brain and Ops visibility",
            ),
            notes="Local-machine launchd automation. Live run state is local-first and not yet fully mirrored into backend run history.",
        ),
        Automation(
            id="launchd_health_audit",
            name="Launchd Health Audit",
            description="Local launchd worker that audits installed com.neo launch agents, detects missing scripts, stale installed plists, generic Python drift, and mirrors those findings into Ops.",
            type="scheduled",
            status="active",
            schedule="Every 15 minutes",
            cron="every:900",
            channel="ops/launchd-health",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=15),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/ops/audit_launchd_jobs.py",
                "cadence_seconds": "900",
                "report": "memory/reports/launchd_health_audit_latest.json",
            },
            instructions=_instructions(
                "Read installed and repo com.neo launchd plists",
                "Detect missing scripts, stale installed ProgramArguments, unregistered jobs, and nonzero launchctl exits",
                "Mirror the audit into /api/automations/runs so Ops mismatch reporting reflects local machine drift",
            ),
            notes="Local-machine launchd automation. It makes host launchd drift visible to Brain and Ops instead of relying on the static registry.",
        ),
        Automation(
            id="codex_chronicle_sync",
            name="Codex Chronicle Sync",
            description="Local launchd worker that syncs direct Codex terminal history into the canonical Chronicle lane so Neo and the brain can see current terminal work.",
            type="scheduled",
            status="active",
            schedule="Every 15 minutes",
            cron="every:900",
            channel="brain/codex-chronicle",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=15),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/sync_codex_chronicle.py",
                "cadence_seconds": "900",
            },
            instructions=_instructions(
                "Read new Codex CLI history from the local machine",
                "Append a distilled Chronicle chunk into memory/codex_session_handoff.jsonl",
                "Keep direct Codex terminal work visible to Neo, standups, and memory sync jobs",
            ),
            notes="Local-machine launchd automation. This is the automatic bridge from direct Codex terminal work into OpenClaw memory lanes.",
        ),
        Automation(
            id="operator_story_signals",
            name="Operator Story Signals",
            description="Nightly local distiller that reads Chronicle, persistent memory, briefs, Dream Cycle, and Progress Pulse, then writes a bounded operator-story lane for persona and content routing.",
            type="scheduled",
            status="active",
            schedule="Daily @ 03:15 ET",
            cron="15 7 * * *",
            channel="brain/operator-story",
            isolation=True,
            last_run_at=_dt(hours_ago=6),
            next_run_at=_dt(hours_ahead=18),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/build_operator_story_signals.py",
                "report": "memory/reports/operator_story_signals_latest.json",
                "snapshot_type": "operator_story_signals",
            },
            instructions=_instructions(
                "Read the raw OpenClaw memory files that preserve building-story continuity",
                "Distill only signal-bearing items into bounded operator-story entries with route recommendations",
                "Write the report locally and sync it into the workspace snapshot store for downstream readers",
            ),
            notes="Local-machine nightly bridge. It keeps raw cron noise out of prompts while still letting the system remember the build story.",
        ),
        Automation(
            id="content_safe_operator_lessons",
            name="Content-Safe Operator Lessons",
            description="Nightly local distiller that rewrites operator-story signals into public-safe macro lessons so content can use the learning without exposing internal mechanics.",
            type="scheduled",
            status="active",
            schedule="Daily @ 03:25 ET",
            cron="25 7 * * *",
            channel="brain/content-safe-operator-lessons",
            isolation=True,
            last_run_at=_dt(hours_ago=6),
            next_run_at=_dt(hours_ahead=18),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/build_content_safe_operator_lessons.py",
                "report": "memory/reports/content_safe_operator_lessons_latest.json",
                "snapshot_type": "content_safe_operator_lessons",
            },
            instructions=_instructions(
                "Read the bounded operator-story lane instead of raw OpenClaw memory",
                "Strip file paths, workspace names, and internal implementation nouns into public-safe macro lessons",
                "Write the report locally and sync it into the workspace snapshot store for future content use",
            ),
            notes="Local-machine nightly redaction layer. It is the public-safe bridge between internal build history and future content prompts.",
        ),
        Automation(
            id="meeting_watchdog",
            name="Meeting Watchdog",
            description="Checks whether required standup lanes are fresh and non-trivial so the system does not silently drift into fake meetings.",
            type="scheduled",
            status="active",
            schedule="Every 30 minutes",
            cron="every:1800",
            channel="ops/meeting-watchdog",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_half_hour,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/meeting_watchdog.py",
                "cadence_seconds": "1800",
            },
            instructions=_instructions(
                "Read recent standups from the API",
                "Flag missing, stale, or thin meeting lanes",
                "Write a latest watchdog report into memory/reports",
            ),
            notes="Local-machine launchd automation. It validates meeting freshness, not execution closure.",
        ),
        Automation(
            id="portfolio_standup_prep",
            name="Portfolio Standup Prep",
            description="Local launchd worker that creates stale or missing standup-prep entries across executive and workspace lanes so the watchdog is not detection-only.",
            type="scheduled",
            status="active",
            schedule="Every 4 hours",
            cron="every:14400",
            channel="ops/portfolio-standups",
            isolation=True,
            last_run_at=_dt(hours_ago=4),
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(hours=4),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/ops/build_portfolio_standups.py",
                "cadence_seconds": "14400",
                "report": "memory/reports/portfolio_standup_prep_latest.json",
            },
            instructions=_instructions(
                "Read recent standups from the API",
                "Create missing or stale executive/workspace standup prep entries using scripts/build_standup_prep.py",
                "Mirror the run into automation history so Ops can see what was refreshed or skipped",
            ),
            notes="Local-machine launchd automation. It repairs stale standup lanes by using the existing standup prep builder rather than creating another planning layer.",
        ),
        Automation(
            id="fallback_watchdog",
            name="Fallback Watchdog",
            description="Detects when canonical memory, durable retrieval, or delivery gates leave their expected source contract, then routes the issue into a report and maintained PM follow-up instead of silently degrading.",
            type="scheduled",
            status="active",
            schedule="Every 30 minutes",
            cron="every:1800",
            channel="ops/fallback-watchdog",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_half_hour,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/fallback_watchdog.py",
                "cadence_seconds": "1800",
                "report": "memory/reports/fallback_watchdog_latest.json",
            },
            instructions=_instructions(
                "Inspect canonical memory reads and detect when they resolved from fallback sources",
                "Inspect durable retrieval and delivery gates for indexed-search or material-signal fallback use",
                "Maintain one PM follow-up card while fallback alerts remain active and write the latest report into memory/reports",
            ),
            notes="Local-machine launchd automation. It turns hidden degraded reads into explicit operational work.",
        ),
        Automation(
            id="post_sync_dispatch",
            name="Post-Sync Dispatch",
            description="Scans completed standups and ensures they leave behind concrete PM artifacts and dispatch metadata.",
            type="scheduled",
            status="active",
            schedule="Every 30 minutes",
            cron="every:1800",
            channel="ops/post-sync-dispatch",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_half_hour,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/post_sync_dispatch.py",
                "cadence_seconds": "1800",
            },
            instructions=_instructions(
                "Read recently completed standups",
                "Create missing PM cards for actionable commitments",
                "Annotate the originating standup with dispatch results",
            ),
            notes="Local-machine launchd automation that converts meeting commitments into executable PM truth.",
        ),
        Automation(
            id="accountability_sweep",
            name="Accountability Sweep",
            description="Audits stale PM work, re-dispatches aged ready cards, reroutes stalled lanes back to Jean-Claude for closure, and opens an executive follow-up when drift persists.",
            type="scheduled",
            status="active",
            schedule="Every 2 hours",
            cron="every:7200",
            channel="ops/accountability",
            isolation=True,
            last_run_at=_dt(hours_ago=1),
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(hours=2),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/accountability_sweep.py",
                "cadence_seconds": "7200",
            },
            instructions=_instructions(
                "Inspect the PM execution queue",
                "Re-dispatch ready cards that have aged past the threshold",
                "Reroute stale review/running cards back to Jean-Claude and maintain one executive follow-up card",
            ),
            notes="Local-machine launchd automation focused on pipeline follow-through rather than content generation.",
        ),
        Automation(
            id="jean_claude_execution_dispatch",
            name="Jean-Claude Execution Dispatch",
            description="Polls queued PM cards managed by Jean-Claude, opens the next SOP, and routes delegated work into the correct workspace lane.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="*/5 * * * *",
            channel="pm/execution",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_five,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            owner_agent="Jean-Claude",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/runners/run_jean_claude_execution.py",
                "cadence_seconds": "300",
            },
            instructions=_instructions(
                "Read the next queued PM card managed by Jean-Claude",
                "Open a bounded SOP and workspace briefing",
                "Move the card into direct or delegated execution",
            ),
            notes="Local-machine launchd automation. This is the main PM-to-work runner bridge for Jean-Claude.",
        ),
        Automation(
            id="workspace_agent_dispatch",
            name="Workspace Agent Dispatch",
            description="Polls delegated PM lanes and lets the appropriate workspace agent accept and execute bounded work inside its own workspace.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="*/5 * * * *",
            channel="pm/workspace-execution",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_five,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="workspace",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/runners/run_workspace_agent.py",
                "cadence_seconds": "300",
            },
            instructions=_instructions(
                "Read the next delegated PM card for a workspace lane",
                "Open a workspace-local work order and intake briefing",
                "Move the card into running workspace execution",
            ),
            notes="Local-machine launchd automation. Each workspace agent stays inside its own lane and reports back through the shared PM card.",
        ),
        Automation(
            id="codex_workspace_execution",
            name="Codex Workspace Execution",
            description="Polls running PM execution lanes with local work packets, executes the bounded work through Codex terminal, and writes the result back through the shared PM/result contract.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="*/5 * * * *",
            channel="pm/codex-execution",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_five,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="workspace",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/runners/run_codex_workspace_execution.py",
                "cadence_seconds": "300",
            },
            instructions=_instructions(
                "Read the next running PM execution lane that has a local Codex work packet",
                "Execute the bounded packet inside the repo with Codex terminal",
                "Write the result back through write_execution_result.py so PM, Chronicle, and durable memory stay aligned",
            ),
            notes="Local-machine launchd automation. Jean-Claude or a workspace agent owns the lane; Codex terminal is the bounded execution substrate underneath them.",
        ),
        Automation(
            id="pm_review_resolution",
            name="PM Review Resolution",
            description="Polls PM review lanes that are policy-marked as autonomous, lets the Codex review worker accept routine results, and opens the next PM lane when the workspace policy says to continue.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="*/5 * * * *",
            channel="pm/review-resolution",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_five,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            owner_agent="Codex Review Worker",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/runners/run_pm_review_resolution.py",
                "cadence_seconds": "300",
            },
            instructions=_instructions(
                "Scan PM review cards for lanes that are policy-marked as autonomous rather than owner-gated",
                "Accept routine review results with the workspace default close or continue action",
                "Spawn the next PM card when the policy says the loop should keep moving",
            ),
            notes="Local-machine launchd automation. This is the autonomous closeout worker for routine PM review decisions.",
        ),
        Automation(
            id="feezie_codex_bridge",
            name="FEEZIE Codex Bridge",
            description="Always-on local launchd worker that drains queued FEEZIE content-generation jobs, completes strong local drafts, and escalates to Codex terminal only when the quality gate fails.",
            type="daemon",
            status="active",
            schedule="Always on",
            cron="launchd.keepalive",
            channel="workspace/feezie-os",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=None,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="workspace",
            workspace_key="linkedin-content-os",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/local_codex_bridge.py",
                "wrapper": "scripts/run_local_codex_bridge.sh",
                "launch_agent": "automations/launchd/com.neo.feezie_codex_bridge.plist",
                "execution_mode": "launchd local-first generation worker",
            },
            instructions=_instructions(
                "Poll the backend for pending FEEZIE content-generation jobs",
                "Run the local template path first and score it against the quality gate",
                "Escalate to codex exec only when the local quality gate fails, then write the result back into the shared generation surface",
            ),
            notes="Local-machine keepalive bridge for the thin POST job / GET status generation path. launchd owns execution; the browser and gateway stay on trigger and status only.",
        ),
        Automation(
            id="watchtranscripts",
            name="Transcript Watcher",
            description="Always-on local launchd watcher that observes transcript drops and keeps source intake moving through the local machine path.",
            type="daemon",
            status="active",
            schedule="Always on",
            cron="launchd.keepalive",
            channel="brain/transcript-watch",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=None,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/watch_transcripts.py",
                "python": "watcher-env/bin/python",
                "cadence": "keepalive",
            },
            instructions=_instructions(
                "Watch local transcript intake paths for new files",
                "Hand new transcript material into the source-ingestion lane",
                "Keep transcript intake local because it depends on host filesystem events",
            ),
            notes="Local-machine keepalive watcher. It intentionally uses watcher-env rather than the main workspace venv.",
        ),
        Automation(
            id="weekly_memory_hygiene",
            name="Weekly Memory Hygiene",
            description="Local launchd weekly memory maintenance job that trims and summarizes durable memory surfaces so Brain reads stay current.",
            type="scheduled",
            status="active",
            schedule="Weekly Tuesday @ 07:00 ET",
            cron="0 7 * * 2",
            channel="brain/memory-hygiene",
            isolation=True,
            last_run_at=_dt(hours_ago=24),
            next_run_at=_dt(hours_ahead=24 * 6),
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/weekly_memory_hygiene.py",
                "cadence": "weekly",
            },
            instructions=_instructions(
                "Inspect durable memory files for stale or oversized sections",
                "Write the weekly hygiene summary",
                "Keep memory maintenance visible to Brain and Ops",
            ),
            notes="Local-machine launchd automation. It should run in the workspace venv so memory readers match Brain runtime dependencies.",
        ),
    ]


def _augment_automation_runtime(automation: Automation) -> Automation:
    if automation.id != "youtube_watchlist_auto_ingest":
        return automation
    try:
        from app.services.youtube_watchlist_service import youtube_watchlist_runtime_status

        runtime_status = youtube_watchlist_runtime_status()
    except Exception:
        return automation

    runtime = runtime_status.get("runtime") if isinstance(runtime_status.get("runtime"), dict) else {}
    pending_backfill = int(runtime_status.get("pending_transcript_backfill") or 0)
    metrics = dict(automation.metrics)
    metrics["pending_transcript_backfill"] = str(pending_backfill)
    metrics["transcription_runtime_ready"] = "true" if bool(runtime.get("can_transcribe")) else "false"
    metrics["caption_runtime_available"] = "true" if bool(runtime.get("yt_dlp")) else "false"
    metrics["whisper_runtime_available"] = "true" if bool(runtime.get("whisper")) else "false"
    metrics["whisper_model"] = str(runtime.get("whisper_model") or metrics.get("whisper_model") or "")
    return automation.model_copy(update={"metrics": metrics})


def _load_openclaw_jobs() -> List[dict[str, Any]]:
    if not OPENCLAW_JOBS_PATH.exists():
        return []
    try:
        data = json.loads(OPENCLAW_JOBS_PATH.read_text())
    except json.JSONDecodeError:
        return []
    jobs = data.get("jobs")
    return jobs if isinstance(jobs, list) else []


def openclaw_jobs_snapshot() -> List[dict[str, Any]]:
    return _load_openclaw_jobs()


def _latest_run_record(job_id: str) -> Optional[dict[str, Any]]:
    if not job_id:
        return None
    path = OPENCLAW_RUNS_DIR / f"{job_id}.jsonl"
    if not path.exists():
        return None

    last_line: Optional[str] = None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.strip():
                    last_line = line
    except OSError:
        return None

    if not last_line:
        return None
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _dt_ms(value: Any) -> Optional[datetime]:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)


def _delivery_bool_from_run(record: Optional[dict[str, Any]]) -> Optional[bool]:
    if not record:
        return None
    delivered = record.get("delivered")
    if isinstance(delivered, bool):
        return delivered
    delivery_status = str(record.get("deliveryStatus") or "").strip().lower()
    if delivery_status == "delivered":
        return True
    if delivery_status in {"not-delivered", "failed", "unknown"}:
        return False
    return None


def _summary_is_no_reply(summary: Any) -> bool:
    text = str(summary or "").upper()
    return "NO_REPLY" in text


def _job_allows_no_reply(job: dict[str, Any]) -> bool:
    payload = job.get("payload") or {}
    message = str(payload.get("message") or "").upper()
    return "NO_REPLY" in message


def _run_output_tokens(record: Optional[dict[str, Any]]) -> Optional[int]:
    if not record:
        return None
    usage = record.get("usage")
    if not isinstance(usage, dict):
        return None
    value = usage.get("output_tokens")
    return value if isinstance(value, int) else None


def _infer_no_reply_from_contract(
    job: dict[str, Any],
    record: Optional[dict[str, Any]],
    *,
    status: str,
    delivered: Optional[bool],
    error_text: Optional[str],
) -> bool:
    if not record or not _job_allows_no_reply(job):
        return False
    if status not in {"ok", "success"} or delivered is not False:
        return False
    if error_text:
        return False

    summary = str(record.get("summary") or "").strip()
    if summary:
        return False

    delivery_error = str(record.get("deliveryError") or "").strip()
    if delivery_error:
        return False

    delivery_status = str(record.get("deliveryStatus") or "").strip().lower()
    if delivery_status not in {"", "not-delivered", "unknown"}:
        return False

    output_tokens = _run_output_tokens(record)
    if output_tokens is not None and output_tokens > 80:
        return False

    return True


def _schedule_label(schedule: dict[str, Any]) -> str:
    kind = schedule.get("kind")
    if kind == "cron":
        return str(schedule.get("expr") or "unknown")
    if kind == "every":
        every_ms = schedule.get("everyMs")
        if isinstance(every_ms, (int, float)):
            minutes = int(every_ms // 60000)
            if minutes % 60 == 0 and minutes >= 60:
                hours = minutes // 60
                return f"Every {hours} hour{'s' if hours != 1 else ''}"
            return f"Every {minutes} minutes"
    return "Unknown"


def _cron_label(schedule: dict[str, Any]) -> str:
    kind = schedule.get("kind")
    if kind == "cron":
        return str(schedule.get("expr") or "")
    if kind == "every":
        every_ms = schedule.get("everyMs")
        return f"every:{every_ms}" if every_ms is not None else "every:unknown"
    return ""


def _runtime_label(job: dict[str, Any]) -> str:
    payload = job.get("payload") or {}
    payload_kind = str(payload.get("kind") or "").strip() or "unknown"
    if payload_kind == "agentTurn":
        return "openclaw_agent_turn"
    return payload_kind


def _scope_for_job(job: dict[str, Any]) -> str:
    name = str(job.get("name") or "").lower()
    if "backup" in name or "monitor" in name or "api" in name:
        return "global"
    return "shared_ops"


def _job_to_automation(job: dict[str, Any]) -> Automation:
    delivery = job.get("delivery") or {}
    payload = job.get("payload") or {}
    state = job.get("state") or {}
    schedule = job.get("schedule") or {}
    run_record = _latest_run_record(str(job.get("id") or ""))
    run_status = str((run_record or {}).get("status") or state.get("lastStatus") or state.get("lastRunStatus") or "unknown")
    run_delivered = _delivery_bool_from_run(run_record)
    if run_delivered is None:
        run_delivered = state.get("lastDelivered")
    run_error = str((run_record or {}).get("error") or state.get("lastError") or "") or None
    run_at = _dt_ms((run_record or {}).get("runAtMs")) or _dt_ms(state.get("lastRunAtMs"))
    next_run_at = _dt_ms(state.get("nextRunAtMs"))
    return Automation(
        id=str(job.get("id") or ""),
        name=str(job.get("name") or "Unnamed OpenClaw Job"),
        description=str(job.get("description") or "Mirrored from OpenClaw jobs.json"),
        status="active" if job.get("enabled", True) else "disabled",
        schedule=_schedule_label(schedule),
        cron=_cron_label(schedule),
        channel=str(delivery.get("channel") or "openclaw"),
        isolation=str(job.get("sessionTarget") or "").strip() == "isolated",
        last_run_at=run_at,
        next_run_at=next_run_at,
        last_status=run_status,
        source=OPENCLAW_SOURCE,
        runtime=_runtime_label(job),
        delivery_channel=str(delivery.get("channel") or "") or None,
        delivery_target=str(delivery.get("to") or "") or None,
        last_delivered=run_delivered,
        last_error=run_error,
        session_target=str(job.get("sessionTarget") or "") or None,
        owner_agent=str(job.get("agentId") or "") or None,
        scope=_scope_for_job(job),
        metrics={
            "wake_mode": str(job.get("wakeMode") or ""),
            "delivery_mode": str(delivery.get("mode") or ""),
            "model": str(payload.get("model") or ""),
            "payload_kind": str(payload.get("kind") or ""),
            "consecutive_errors": str((state.get("consecutiveErrors") or 0)),
            "run_log_delivery_status": str((run_record or {}).get("deliveryStatus") or ""),
        },
        notes=str(payload.get("message") or "")[:400] or None,
    )


def _job_to_run(job: dict[str, Any]) -> AutomationRun:
    delivery = job.get("delivery") or {}
    state = job.get("state") or {}
    payload = job.get("payload") or {}
    run_record = _latest_run_record(str(job.get("id") or ""))
    run_at = _dt_ms((run_record or {}).get("runAtMs")) or _dt_ms(state.get("lastRunAtMs"))
    duration_value = (run_record or {}).get("durationMs")
    duration_ms = duration_value if isinstance(duration_value, int) else state.get("lastDurationMs")
    finished_at = _dt_ms((run_record or {}).get("ts"))
    if finished_at is None and run_at and isinstance(duration_ms, (int, float)):
        finished_at = run_at + timedelta(milliseconds=float(duration_ms))
    error_text = str((run_record or {}).get("error") or state.get("lastError") or "") or None
    delivered = _delivery_bool_from_run(run_record)
    if delivered is None:
        delivered = state.get("lastDelivered")
    status = str((run_record or {}).get("status") or state.get("lastStatus") or state.get("lastRunStatus") or "unknown")
    has_observed_run = run_at is not None
    summary = str((run_record or {}).get("summary") or "")
    inferred_no_reply = _infer_no_reply_from_contract(
        job,
        run_record,
        status=status,
        delivered=delivered,
        error_text=error_text,
    )
    no_reply = _summary_is_no_reply(summary) or inferred_no_reply
    no_delivery = str(delivery.get("mode") or "").strip().lower() == "none"
    run_id_suffix = (run_record or {}).get("runAtMs") or state.get("lastRunAtMs") or "never"
    return AutomationRun(
        id=f"{job.get('id')}::{run_id_suffix}",
        automation_id=str(job.get("id") or ""),
        automation_name=str(job.get("name") or "Unnamed OpenClaw Job"),
        source=OPENCLAW_SOURCE,
        runtime=_runtime_label(job),
        status=status,
        delivered=delivered,
        delivery_channel=str(delivery.get("channel") or "") or None,
        delivery_target=str(delivery.get("to") or "") or None,
        run_at=run_at,
        finished_at=finished_at,
        duration_ms=duration_ms if isinstance(duration_ms, int) else None,
        error=error_text,
        owner_agent=str(job.get("agentId") or "") or None,
        session_target=str(job.get("sessionTarget") or "") or None,
        scope=_scope_for_job(job),
        action_required=bool(
            (has_observed_run and status not in {"ok", "success"})
            or (delivered is False and not no_reply and not no_delivery)
        ),
        metadata={
            "delivery_mode": delivery.get("mode"),
            "payload_kind": payload.get("kind"),
            "model": payload.get("model"),
            "consecutive_errors": state.get("consecutiveErrors"),
            "has_observed_run": has_observed_run,
            "summary": summary,
            "delivery_status": (run_record or {}).get("deliveryStatus") or state.get("lastDeliveryStatus"),
            "no_reply": no_reply,
            "no_reply_contract": _job_allows_no_reply(job),
            "no_reply_inferred": inferred_no_reply,
            "no_delivery": no_delivery,
            "run_source": "cron_runs_jsonl" if run_record else "jobs_state",
        },
    )


def automation_source_of_truth() -> str:
    has_openclaw_jobs = bool(_load_openclaw_jobs())
    has_local_launchd = bool(_local_launchd_automations())
    if has_openclaw_jobs and has_local_launchd:
        return f"{OPENCLAW_SOURCE}+{LOCAL_LAUNCHD_SOURCE}"
    if has_openclaw_jobs:
        return OPENCLAW_SOURCE
    if has_local_launchd:
        return f"{STATIC_SOURCE}+{LOCAL_LAUNCHD_SOURCE}"
    return STATIC_SOURCE


def list_automation_runs(limit: Optional[int] = None) -> List[AutomationRun]:
    jobs = _load_openclaw_jobs()
    runs = [_job_to_run(job) for job in jobs]
    floor = datetime.min.replace(tzinfo=timezone.utc)
    runs.sort(key=lambda item: item.run_at or floor, reverse=True)
    if limit is not None:
        return runs[:limit]
    return runs


def list_automations() -> List[Automation]:
    """Return the automation definitions backing Mission Control + Brain views."""

    jobs = _load_openclaw_jobs()
    launchd_items = _local_launchd_automations()
    if not jobs:
        automations = _static_automations()
        existing_ids = {item.id for item in automations}
        automations.extend(item for item in launchd_items if item.id not in existing_ids)
        automations = [_augment_automation_runtime(item) for item in automations]
        automations.sort(key=lambda item: item.name.lower())
        return automations

    automations = [_job_to_automation(job) for job in jobs]
    static_items = _static_automations()
    automations.extend(item for item in static_items if item.id in STATIC_FALLBACK_IDS)
    existing_ids = {item.id for item in automations}
    automations.extend(item for item in launchd_items if item.id not in existing_ids)
    automations = [_augment_automation_runtime(item) for item in automations]
    automations.sort(key=lambda item: item.name.lower())
    return automations
