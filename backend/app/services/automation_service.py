from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional

from app.models.automations import Automation, AutomationInstruction, AutomationRun
from app.services.launchd_policy import RETIRED_INTEGRATED_COMPATIBILITY_IDS

AI_CLONE_RUNTIME_ROOT = Path(os.getenv("AI_CLONE_RUNTIME_ROOT") or (Path.home() / ".codex" / "ai-clone"))
CODEX_RUN_LEDGER_PATH = AI_CLONE_RUNTIME_ROOT / "state" / "automations" / "runs" / "all.jsonl"
CODEX_REGISTRY_SOURCE = "codex_launchd_registry"
CODEX_RUN_LEDGER_SOURCE = "codex_run_ledger"
LOCAL_LAUNCHD_SOURCE = CODEX_REGISTRY_SOURCE
SUPPORTED_RUN_RUNTIMES = {"launchd", "codex_exec"}
SUPPORTED_RUN_SOURCES = {CODEX_REGISTRY_SOURCE, "local_launchd_registry"}

# These are desired launchd targets, not evidence that anything is installed or
# running. Only a fresh launchd health-audit observation may promote one of
# these configured definitions to `active` in the registry response.
CONFIGURED_LAUNCHD_AUTOMATION_IDS = frozenset(
    {
        "brain_canonical_memory_sync",
        "codex_chronicle_sync",
        "codex_memory_sync",
        "codex_workspace_execution",
        "content_safe_operator_lessons",
        "daily_integrated_cycle",
        "external_service_health",
        "feezie_codex_bridge",
        "feezie_content_pipeline",
        "fellowship_scout",
        "jean_claude_execution_dispatch",
        "launchd_health_audit",
        "meeting_watchdog",
        "memory_archive_sweep",
        "memory_health_check",
        "monthly_recovery_drill",
        "neo_guest",
        "operator_story_signals",
        "persona_bundle_sync",
        "pm_review_resolution",
        "post_sync_dispatch",
        "progress_pulse",
        "project_snapshot",
        "workspace_agent_dispatch",
        "youtube_watchlist_auto_ingest",
    }
)
LAUNCHD_HEALTH_AUDIT_AUTOMATION_ID = "launchd_health_audit"
LAUNCHD_HEALTH_STATE_SCHEMA = "launchd_automation_state/v1"
LAUNCHD_HEALTH_EVIDENCE_MAX_AGE_SECONDS = max(
    60,
    int(os.getenv("AI_CLONE_LAUNCHD_HEALTH_MAX_AGE_SECONDS", "2700")),
)
LAUNCHD_HEALTH_CLOCK_SKEW_SECONDS = 300


def _dt(hours_ago: int = 0, hours_ahead: int = 0) -> datetime:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if hours_ago:
        return now - timedelta(hours=hours_ago)
    if hours_ahead:
        return now + timedelta(hours=hours_ahead)
    return now


def _instructions(*steps: str) -> List[AutomationInstruction]:
    return [AutomationInstruction(title=f"Step {idx + 1}", detail=detail) for idx, detail in enumerate(steps)]


def _project_launchd_automations() -> List[Automation]:
    """Return project launchd definitions that predate the detailed worker registry."""

    automations: List[Automation] = [
        Automation(
            id="persona_bundle_sync",
            name="Persona Bundle Sync",
            description="Polls owner-committed Brain promotions and writes them into the private local persona overlay without mutating the Git-tracked seed.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="*/5 * * * *",
            channel="brain/persona-bundle",
            isolation=True,
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=5),
            source=CODEX_REGISTRY_SOURCE,
            runtime="launchd",
            metrics={
                "source": "Brain committed persona deltas",
                "target": "AI_CLONE_STATE_ROOT/persona/canonical/**",
                "delivery": "private local state overlay",
            },
            instructions=_instructions(
                "Read committed persona deltas from the Brain API",
                "Copy the tracked seed once when needed, then write only the private persona overlay",
                "Mark synced deltas so the same canon is not written twice",
            ),
            notes="Runs locally. Private canon bytes and absolute state paths are never sent to Railway or GitHub.",
        ),
        Automation(
            id="youtube_watchlist_auto_ingest",
            name="YouTube Watchlist Auto-Ingest",
            description="Codex-native local automation that runs on the machine to discover fresh watchlist videos, retry older URL-only watchlist assets, prefer YouTube captions first, and only fall back to local audio plus a compatible Whisper runtime when needed before registering the result into the shared Brain source system.",
            type="scheduled",
            status="active",
            schedule="Every 2 hours",
            cron="0 */2 * * *",
            channel="brain/youtube-watchlist",
            isolation=True,
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(hours=2),
            source=CODEX_REGISTRY_SOURCE,
            runtime="launchd",
            metrics={
                "framework": "Codex project automation + launchd",
                "runtime": "local machine only",
                "discovery": "watchlists.yaml -> youtube_channels",
                "media_stack": "yt-dlp captions first -> ffmpeg + compatible whisper fallback",
                "cheap_task_defaults": "deterministic/local first; Codex queue for reasoning",
            },
            instructions=_instructions(
                "Resolve tracked YouTube channels and discover fresh videos from the watchlist",
                "Retry pending YouTube assets that were previously registered without transcripts",
                "Prefer downloadable captions first, then fall back to local audio + Whisper only when a compatible runtime is available",
                "Register each source into the shared Brain long-form ingest lane and refresh the FEEZIE snapshots",
            ),
            notes="Runs inside the Codex project on the local machine because Railway does not have the media runtime required for caption download fallback, audio extraction, or transcript capture.",
        ),
        Automation(
            id="feezie_content_pipeline",
            name="FEEZIE Content Pipeline",
            description="Codex-native local automation that refreshes the FEEZIE RSS/Reddit signal lane and planning artifacts without duplicating the dedicated YouTube scheduler or defaulting to the retired two-draft materializer.",
            type="scheduled",
            status="active",
            schedule="Every 2 hours",
            cron="0 */2 * * *",
            channel="workspace/feezie-os",
            isolation=True,
            next_run_at=datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(hours=2),
            source=CODEX_REGISTRY_SOURCE,
            runtime="launchd",
            metrics={
                "workspace": "workspaces/linkedin-content-os",
                "runtime": "local machine only",
                "pipeline": "RSS/Reddit intake -> market archive -> social feed -> strategy -> source intelligence -> BrainSignal intake",
                "output": "plans/*.json plus canonical integrated content lifecycle",
            },
            instructions=_instructions(
                "Refresh RSS/Reddit FEEZIE source intake and rebuild the social feed artifacts; leave YouTube to its dedicated scheduler",
                "Regenerate weekly plan and reaction queue from the current workspace state",
                "Route qualified opportunities into the canonical-post and on-demand-variant lifecycle",
                "Register the refreshed source lane into Brain source intelligence and BrainSignal intake",
            ),
            notes="Runs on the local machine so generated drafts and plans remain durable in private workspace state.",
        ),
    ]

    return automations


def _local_launchd_automations() -> List[Automation]:
    """Return the detailed local Codex workers installed and scheduled by launchd."""

    next_half_hour = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=30)
    next_five = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=5)
    next_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)

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
            description="Local launchd worker that syncs direct Codex terminal history into Chronicle and closes material Codex learnings into runtime memory.",
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
                "Append extracted learning updates into memory/runtime/LEARNINGS.md and memory promotions into memory/runtime/persistent_state.md",
                "Keep direct Codex terminal work visible to Neo, standups, and memory sync jobs",
            ),
            notes="Local-machine launchd automation. This is the automatic bridge from direct Codex terminal work into Chronicle plus durable runtime memory lanes.",
        ),
        Automation(
            id="codex_memory_sync",
            name="Codex Durable Memory Sync",
            description="Local launchd worker that refreshes the SQLite full-text memory index used by Codex agents and local automation context builders.",
            type="scheduled",
            status="active",
            schedule="Every 5 minutes",
            cron="every:300",
            channel="brain/durable-memory",
            isolation=True,
            next_run_at=next_five,
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/run_codex_memory_sync.py",
                "cadence_seconds": "300",
                "index": "~/.codex/ai-clone/state/memory/codex-memory.sqlite3",
            },
            instructions=_instructions(
                "Scan canonical project memory and knowledge sources",
                "Refresh the private SQLite FTS5 durable-memory index",
                "Append the run result to the Codex automation ledger",
            ),
            notes="Local-machine launchd automation. The private runtime index replaces the retired external memory-search sidecar.",
        ),
        Automation(
            id="operator_story_signals",
            name="Operator Story Signals",
            description="Nightly local distiller that reads Chronicle, persistent memory, briefs, Dream Cycle, and Progress Pulse, then writes a bounded operator-story lane for persona and content routing.",
            type="scheduled",
            status="active",
            schedule="Chained after Dream Cycle @ 06:15 ET",
            cron="dependency:dream_cycle",
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
                "Read the canonical Codex memory files that preserve building-story continuity",
                "Distill only signal-bearing items into bounded operator-story entries with route recommendations",
                "Write the report locally and sync it into the workspace snapshot store for downstream readers",
            ),
            notes="Deterministic second stage of the 06:15 Dream Cycle chain. Its standalone launchd label is manual-only so login or reload cannot race it ahead of Dream.",
        ),
        Automation(
            id="content_safe_operator_lessons",
            name="Content-Safe Operator Lessons",
            description="Nightly local distiller that rewrites operator-story signals into public-safe macro lessons so content can use the learning without exposing internal mechanics.",
            type="scheduled",
            status="active",
            schedule="Chained after Operator Story Signals",
            cron="dependency:operator_story_signals",
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
                "Read the bounded operator-story lane instead of raw runtime memory",
                "Strip file paths, workspace names, and internal implementation nouns into public-safe macro lessons",
                "Write the report locally and sync it into the workspace snapshot store for future content use",
            ),
            notes="Deterministic third stage of the 06:15 Dream Cycle chain. It succeeds only when its source timestamp exactly matches the current operator-story report and Dream lineage survives redaction.",
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
            description="Polls signed PM lanes, executes allowlisted Brain local actions directly or bounded project work through Codex terminal, and writes every result back through the shared PM/result contract.",
            type="scheduled",
            status="active",
            schedule="Every minute",
            cron="* * * * *",
            channel="pm/codex-execution",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=next_minute,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="workspace",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/runners/run_codex_workspace_execution.py",
                "cadence_seconds": "60",
            },
            instructions=_instructions(
                "Read the next running PM execution lane that has a local Codex work packet",
                "Execute signed allowlisted Brain local actions deterministically without invoking a model",
                "Drain host-action cards whose automation payload is marked autostart and does not require host confirmation",
                "Execute the bounded packet inside the repo with Codex terminal",
                "Write the result back through write_execution_result.py so PM, Chronicle, and durable memory stay aligned",
            ),
            notes="Local-machine launchd automation. Brain local actions stay deterministic and token-free; project work uses the authenticated Codex terminal runner.",
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
            id="neo_guest",
            name="Neo Guest Conversation Worker",
            description="Always-on local launchd daemon that serially claims invite-only Neo conversation jobs and answers deterministically from a versioned approved public knowledge pack. Llama-family generation is retired and cannot be enabled.",
            type="daemon",
            status="active",
            schedule="Always on",
            cron="launchd.keepalive",
            channel="neo/guest-conversations",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=None,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            owner_agent="Neo",
            scope="shared_ops",
            workspace_key="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/runners/run_neo_guest.py",
                "launch_agent": "automations/launchd/com.neo.neo_guest.plist",
                "execution_mode": "persistent_serial_queue_worker",
                "idle_poll_seconds": "0.5-2.0",
                "response_runtime": "approved_public_knowledge_packet",
                "generative_model_path": "retired_removed",
                "knowledge_pack_contract": "neo_public_knowledge_pack/v1",
                "local_ledger_content": "metadata_only",
                "capability": "write_capable_guest_response",
            },
            instructions=_instructions(
                "Remain resident under launchd and claim one scoped Neo guest job at a time with bounded idle polling",
                "Send only a query-selected subset of the versioned approved public professional knowledge pack and that guest's bounded conversation; never read raw Brain or private project memory",
                "Write the bounded approved-pack response or failure back to the same claimed job; reject every retired Llama/Ollama generation switch before creating a session or claiming work",
                "Record metadata-only completed or failed execution evidence in the local-first automation ledger before attempting its Railway mirror",
            ),
            notes="Invite-only persistent guest worker with no next scheduled run. It cannot access operator routes or raw Brain/private project memory and has no generative-model path.",
        ),
        Automation(
            id="city_event_scout",
            name="City Event Scout",
            description="Mac-local weekly public-event research and one-recipient allowlisted Event Beacon digest.",
            type="scheduled",
            status="active",
            schedule="Weekly Monday @ 07:00 ET",
            cron="0 7 * * 1",
            channel="local/city-event-scout",
            isolation=True,
            last_run_at=None,
            next_run_at=None,
            last_status="unknown",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            workspace_key="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/run_city_event_scout.py --send",
                "launch_agent": "automations/launchd/com.neo.city_event_scout.plist",
                "execution_mode": "local_public_research_send",
                "installation_state": "installed_and_loaded",
                "send_state": "active_single_recipient",
                "remote_state": "prohibited",
            },
            instructions=_instructions(
                "Search only public D.C., Maryland, and Northern Virginia event sources inside the approved 45-day window",
                "Rank verified candidates by referral value, Fusion alignment, relationship depth, geography, efficiency, and source confidence",
                "Exclude unknown pricing and any applicable attendee cost over $100; prefer free and lower-cost events and prominently label every option over $50",
                "Keep research, preference, deduplication, and delivery state private on this Mac",
                "Do not contact Gmail unless the dedicated sender has exact local approval evidence and the live schedule has been separately activated",
            ),
            notes="Owner-approved weekly Monday 07:00 ET Mac-local schedule. Delivery uses only the dedicated private OAuth configuration and one private allowlisted recipient; event, recipient, and delivery state must not mirror to Railway.",
        ),
        Automation(
            id="fellowship_scout",
            name="Fellowship Scout",
            description="Mac-local weekly public research that ranks AI and technology fellowships and prepares private application packets without submitting applications.",
            type="scheduled",
            status="active",
            schedule="Weekly Monday @ 08:00 local",
            cron="0 8 * * 1",
            channel="local/fellowship-scout",
            isolation=True,
            last_run_at=None,
            next_run_at=None,
            last_status="unknown",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            workspace_key="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/run_fellowship_scout.py",
                "launch_agent": "automations/launchd/com.neo.fellowship_scout.plist",
                "execution_mode": "local_public_research_prepare_only",
                "private_state": "AI_CLONE_STATE_ROOT/fellowship_scout/**",
                "submission_state": "prohibited",
                "remote_state": "prohibited",
            },
            instructions=_instructions(
                "Search only configured public HTTPS sources for currently open or opening-soon programs",
                "Rank candidates against the verified mid-career profile and preserve ambiguous requirements for owner review",
                "Write the report, application queue, and preparation packets only to private local state",
                "Never submit an application, choose demographic answers, name references, upload files, accept terms, or pay fees",
            ),
            notes="Owner-approved weekly Monday 08:00 local schedule. Research and preparation remain private on this Mac, and every final application submission requires exact interactive owner confirmation.",
        ),
        Automation(
            id="email_codex_bridge",
            name="Email Codex Bridge",
            description="Local email-drafting worker definition retained for a future canary, but intentionally not installed or running.",
            type="daemon",
            status="paused",
            schedule="Paused — intentionally not installed",
            cron="disabled",
            channel="email/drafting",
            isolation=True,
            last_run_at=_dt(),
            next_run_at=None,
            last_status="success",
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            workspace_key="shared_ops",
            metrics={
                "runtime": "local_launchd",
                "script": "scripts/local_codex_bridge.py",
                "wrapper": "scripts/run_local_codex_bridge.sh",
                "launch_agent": "automations/launchd/com.neo.email_codex_bridge.plist",
                "workspace_slug": "email-drafts",
                "execution_mode": "launchd dedicated email drafting worker",
                "installation_state": "intentionally_uninstalled",
            },
            instructions=_instructions(
                "Poll the backend for pending grounded email drafting jobs only",
                "Run Codex terminal against the email-specific context packet and return exactly one draft body",
                "Keep inbox drafting isolated from the LinkedIn content queue so the two lanes do not contend for the same worker",
            ),
            notes="The worker remains intentionally uninstalled while the email execution lane is disabled. Its plist is retained as an inert future canary definition.",
        ),
        Automation(
            id="watchtranscripts",
            name="Transcript Watcher",
            description="Local transcript-watcher definition retained for a future canary, but intentionally not installed or running.",
            type="daemon",
            status="paused",
            schedule="Paused — intentionally not installed",
            cron="disabled",
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
                "installation_state": "intentionally_uninstalled",
            },
            instructions=_instructions(
                "Watch local transcript intake paths for new files",
                "Hand new transcript material into the source-ingestion lane",
                "Keep transcript intake local because it depends on host filesystem events",
            ),
            notes="The watcher remains intentionally uninstalled. Its plist is retained as an inert future canary definition.",
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


def _codex_parity_automations() -> List[Automation]:
    """Launchd jobs that replace the useful retired scheduler contracts."""

    definitions = (
        (
            "codex_nightly_self_improvement",
            "Codex Nightly Self-Improvement",
            "Daily @ 01:00 ET",
            "0 1 * * *",
            "scripts/runners/run_codex_maintenance_job.py --job nightly-self-improvement",
            "ops/self-improvement",
            "Runs a read-only Codex analysis through saved ChatGPT login and writes a bounded local report.",
        ),
        (
            "codex_daily_memory_flush",
            "Codex Daily Memory Flush",
            "Daily @ 03:00 ET",
            "0 3 * * *",
            "scripts/runners/run_codex_maintenance_job.py --job daily-memory-flush",
            "brain/durable-memory",
            "Synthesizes material daily decisions and blockers into the local durable-memory lane.",
        ),
        (
            "codex_rolling_docs",
            "Codex Rolling Docs",
            "Every 2 days @ 04:00 ET",
            "0 4 */2 * *",
            "scripts/runners/run_codex_maintenance_job.py --job rolling-docs",
            "ops/documentation",
            "Produces a bounded documentation-drift report through a read-only Codex runner.",
        ),
        (
            "morning_daily_brief",
            "Morning Daily Brief",
            "Daily @ 11:30 ET",
            "30 11 * * *",
            "scripts/run_codex_morning_daily_brief.py",
            "ops/daily-brief",
            "Builds the deterministic daily operating brief and records it locally first.",
        ),
        (
            "progress_pulse",
            "Progress Pulse",
            "Every hour",
            "every:3600",
            "scripts/run_codex_progress_pulse.py",
            "ops/progress-pulse",
            "Publishes a local digest only when material Chronicle movement has landed.",
        ),
        (
            "daily_integrated_cycle",
            "Daily Integrated Cycle",
            "Daily @ 06:15 ET",
            "15 6 * * *",
            "scripts/run_daily_integrated_cycle.py",
            "ops/daily-integrated-cycle",
            "Owns the ordered Dream readiness, Morning Brief, workspace stand-up, Ops conclusion, and bounded remote-projection dependency chain.",
        ),
        (
            "dream_cycle",
            "Dream Cycle",
            "Daily @ 06:15 ET",
            "15 6 * * *",
            "scripts/run_codex_dream_cycle.py",
            "brain/dream-cycle",
            "Builds the deterministic daily memory and execution snapshot.",
        ),
        (
            "memory_health_check",
            "Memory Health Check",
            "Daily @ 03:10 ET",
            "10 3 * * *",
            "scripts/run_codex_memory_health.py",
            "brain/memory-health",
            "Verifies the SQLite durable-memory index and canonical memory source freshness.",
        ),
        (
            "monthly_recovery_drill",
            "Monthly Recovery Drill",
            "Month day 1 @ 03:15 ET",
            "15 3 1 * *",
            "scripts/run_monthly_recovery_drill_scheduled.py",
            "ops/recovery",
            "Creates an encrypted off-site state backup and proves isolated restoration without touching live state.",
        ),
        (
            "memory_archive_sweep",
            "Memory Archive Sweep",
            "Month day 1 @ 04:00 ET",
            "0 4 1 * *",
            "scripts/run_codex_memory_archive_sweep.py",
            "brain/memory-archive",
            "Moves eligible memory files into a checksummed archive with rollback on failure.",
        ),
        (
            "external_service_health",
            "External Service Health",
            "Daily @ 06:05 ET",
            "5 6 * * *",
            "scripts/run_codex_external_service_health.py",
            "ops/service-health",
            "Checks authenticated Railway application health and records a bounded local report.",
        ),
        (
            "project_snapshot",
            "Secure Project Snapshot",
            "Daily @ 06:00 ET",
            "0 6 * * *",
            "scripts/run_secure_project_snapshot.py",
            "ops/backup",
            "Creates verified private project and local-state archives outside Git with credentials and dependencies excluded.",
        ),
        (
            "secure_config_backup",
            "Secure Configuration Backup",
            "Sunday @ 05:00 ET",
            "0 5 * * 0",
            "scripts/run_secure_config_backup.py",
            "ops/backup",
            "Writes a private permission/checksum manifest and encrypts secret contents only when configured.",
        ),
        (
            "fusion_feedback_refresh",
            "Fusion Feedback Refresh",
            "Daily @ 12:15 ET",
            "15 12 * * *",
            "scripts/run_fusion_feedback_refresh.py",
            "workspace/fusion-os",
            "Refreshes public Fusion feedback and rebuilds its grounded standup packet.",
        ),
    )
    return [
        Automation(
            id=automation_id,
            name=name,
            description=description,
            type="scheduled",
            status="active",
            schedule=schedule,
            cron=cron,
            channel=channel,
            isolation=True,
            source=LOCAL_LAUNCHD_SOURCE,
            runtime="launchd",
            scope="shared_ops",
            metrics={"runtime": "local_launchd", "script": script, "local_first": "true"},
            instructions=_instructions(
                "Run on the local Mac under launchd",
                "Persist the result to the private Codex run ledger before any network mirror",
                "Mirror bounded status into the authenticated Railway control plane when available",
            ),
            notes="Codex-native parity job. It requires neither a gateway scheduler nor a model-provider API token.",
        )
        for automation_id, name, schedule, cron, script, channel, description in definitions
    ]


def automation_source_of_truth() -> str:
    return f"{CODEX_REGISTRY_SOURCE}+{CODEX_RUN_LEDGER_SOURCE}"


def is_codex_run(run: AutomationRun) -> bool:
    return run.runtime in SUPPORTED_RUN_RUNTIMES or run.source in SUPPORTED_RUN_SOURCES


def _run_timestamp(run: AutomationRun) -> datetime:
    value = run.run_at or run.finished_at
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_launchd_health_evidence(
    runs: List[AutomationRun],
    *,
    now: datetime | None = None,
) -> tuple[str, datetime | None, dict[str, dict[str, Any]]]:
    """Return fresh/stale/missing path-free host evidence from the audit run.

    An ordinary worker success cannot prove launchd installation or health.
    The evidence is accepted only from the newest launchd health-audit run,
    with the expected schema, a parseable host observation timestamp, and a
    per-automation state map.
    """

    audit_runs = [
        run for run in runs if run.automation_id == LAUNCHD_HEALTH_AUDIT_AUTOMATION_ID
    ]
    if not audit_runs:
        return "missing", None, {}
    latest = max(audit_runs, key=_run_timestamp)
    metadata = latest.metadata if isinstance(latest.metadata, dict) else {}
    if metadata.get("launchd_state_schema") != LAUNCHD_HEALTH_STATE_SCHEMA:
        return "missing", None, {}
    observed_at = _parse_utc_datetime(metadata.get("launchd_observed_at"))
    raw_states = metadata.get("launchd_automation_states")
    if observed_at is None or not isinstance(raw_states, dict):
        return "missing", observed_at, {}

    checked_at = _parse_utc_datetime(now) or datetime.now(timezone.utc)
    age_seconds = (checked_at - observed_at).total_seconds()
    if (
        age_seconds < -LAUNCHD_HEALTH_CLOCK_SKEW_SECONDS
        or age_seconds > LAUNCHD_HEALTH_EVIDENCE_MAX_AGE_SECONDS
    ):
        return "stale", observed_at, {}

    states = {
        str(automation_id): dict(state)
        for automation_id, state in raw_states.items()
        if isinstance(automation_id, str) and isinstance(state, dict)
    }
    return "fresh", observed_at, states


def _metric_bool(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def _metric_count(value: Any) -> str:
    try:
        return str(max(0, int(value or 0)))
    except (TypeError, ValueError):
        return "0"


def list_automation_runs(limit: Optional[int] = None) -> List[AutomationRun]:
    """Read, validate, and de-duplicate the append-only local Codex run ledger."""

    runs_by_id: dict[str, AutomationRun] = {}
    if CODEX_RUN_LEDGER_PATH.exists():
        try:
            lines = CODEX_RUN_LEDGER_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            lines = []
        for line in lines:
            try:
                payload = json.loads(line)
                run = AutomationRun.model_validate(payload)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
            if is_codex_run(run):
                runs_by_id[run.id] = run

    runs = sorted(runs_by_id.values(), key=_run_timestamp, reverse=True)
    if limit is not None:
        return runs[: max(0, limit)]
    return runs


def _registry_automations() -> List[Automation]:
    automations = _project_launchd_automations()
    existing_ids = {item.id for item in automations}
    automations.extend(item for item in _local_launchd_automations() if item.id not in existing_ids)
    existing_ids = {item.id for item in automations}
    automations.extend(item for item in _codex_parity_automations() if item.id not in existing_ids)
    normalized: List[Automation] = []
    for item in automations:
        metrics = dict(item.metrics)
        retired_integrated_compatibility = item.id in RETIRED_INTEGRATED_COMPATIBILITY_IDS
        intentionally_uninstalled = (
            metrics.get("installation_state") == "intentionally_uninstalled"
            or retired_integrated_compatibility
        )
        configured = item.id in CONFIGURED_LAUNCHD_AUTOMATION_IDS
        if retired_integrated_compatibility:
            metrics.update(
                {
                    "retirement_state": "integrated_coordinator_replacement",
                    "replacement_automation_id": "daily_integrated_cycle",
                }
            )
        metrics.update(
            {
                "configuration_state": (
                    "configured_target"
                    if configured
                    else "intentionally_uninstalled"
                    if intentionally_uninstalled
                    else "planned_definition"
                ),
                "installation_state": (
                    "intentionally_uninstalled"
                    if intentionally_uninstalled
                    else "unverified"
                    if configured
                    else "not_expected"
                ),
                "health_state": "unverified" if configured else "not_running",
                "health_evidence_state": "missing" if configured else "not_applicable",
            }
        )
        normalized.append(
            item.model_copy(
                update={
                    "source": CODEX_REGISTRY_SOURCE,
                    "runtime": item.runtime or "launchd",
                    "status": "unknown" if configured else "paused",
                    "next_run_at": item.next_run_at if configured else None,
                    "last_run_at": None,
                    "last_status": "unknown",
                    "last_delivered": None,
                    "last_error": None,
                    "metrics": metrics,
                }
            )
        )
    normalized.sort(key=lambda item: item.name.lower())
    return normalized


def automation_registry_ids() -> set[str]:
    return {item.id for item in _registry_automations()}


def list_automations(runs: Optional[List[AutomationRun]] = None) -> List[Automation]:
    """Return configured definitions overlaid with fresh observed host truth."""

    automations = _registry_automations()
    observed_runs = list_automation_runs() if runs is None else [run for run in runs if is_codex_run(run)]
    evidence_state, observed_at, launchd_states = _latest_launchd_health_evidence(
        observed_runs
    )
    latest_by_automation: dict[str, AutomationRun] = {}
    for run in observed_runs:
        current = latest_by_automation.get(run.automation_id)
        if current is None or _run_timestamp(run) > _run_timestamp(current):
            latest_by_automation[run.automation_id] = run

    enriched: List[Automation] = []
    for item in automations:
        metrics = dict(item.metrics)
        configured = metrics.get("configuration_state") == "configured_target"
        intentionally_uninstalled = (
            metrics.get("configuration_state") == "intentionally_uninstalled"
        )
        state = launchd_states.get(item.id) if evidence_state == "fresh" else None
        status = item.status
        next_run_at = item.next_run_at

        if configured:
            metrics["health_evidence_state"] = evidence_state
            metrics["health_evidence_max_age_seconds"] = str(
                LAUNCHD_HEALTH_EVIDENCE_MAX_AGE_SECONDS
            )
            if observed_at is not None:
                metrics["health_observed_at"] = observed_at.isoformat().replace(
                    "+00:00", "Z"
                )
            if state is None:
                metrics["installation_state"] = "unverified"
                metrics["health_state"] = (
                    "evidence_incomplete" if evidence_state == "fresh" else "unverified"
                )
                status = "error" if evidence_state == "fresh" else "unknown"
                next_run_at = None
            else:
                installed = state.get("installed")
                loaded = state.get("loaded")
                enabled = state.get("enabled")
                healthy = state.get("healthy")
                metrics.update(
                    {
                        "installation_state": (
                            "installed"
                            if installed is True
                            else "not_installed"
                            if installed is False
                            else "unverified"
                        ),
                        "launchd_loaded": _metric_bool(loaded),
                        "launchd_enabled": _metric_bool(enabled),
                        "health_state": (
                            "healthy"
                            if healthy is True
                            else "unhealthy"
                            if healthy is False
                            else "unverified"
                        ),
                        "health_issue_count": _metric_count(state.get("issue_count")),
                        "health_error_count": _metric_count(state.get("error_count")),
                        "health_warning_count": _metric_count(state.get("warning_count")),
                    }
                )
                if (
                    installed is True
                    and loaded is True
                    and enabled is True
                    and healthy is True
                ):
                    status = "active"
                else:
                    status = "error"
                    next_run_at = None
        elif evidence_state == "fresh" and isinstance(state, dict):
            installed = state.get("installed")
            loaded = state.get("loaded")
            enabled = state.get("enabled")
            metrics.update(
                {
                    "health_evidence_state": "fresh",
                    "installation_state": (
                        "installed"
                        if installed is True
                        else "intentionally_uninstalled"
                        if intentionally_uninstalled
                        else "not_expected"
                    ),
                    "launchd_loaded": _metric_bool(loaded),
                    "launchd_enabled": _metric_bool(enabled),
                }
            )
            if observed_at is not None:
                metrics["health_observed_at"] = observed_at.isoformat().replace(
                    "+00:00", "Z"
                )
            if installed is True or loaded is True:
                metrics["health_state"] = "unexpected_running"
                status = "error"

        latest = latest_by_automation.get(item.id)
        if latest is None:
            enriched.append(
                item.model_copy(
                    update={
                        "status": status,
                        "next_run_at": next_run_at,
                        "metrics": metrics,
                    }
                )
            )
            continue
        enriched.append(
            item.model_copy(
                update={
                    "status": status,
                    "next_run_at": next_run_at,
                    "last_run_at": latest.run_at or latest.finished_at,
                    "last_status": latest.status,
                    "last_delivered": latest.delivered,
                    "last_error": latest.error,
                    "delivery_channel": latest.delivery_channel,
                    "delivery_target": latest.delivery_target,
                    "owner_agent": latest.owner_agent or item.owner_agent,
                    "session_target": latest.session_target or item.session_target,
                    "workspace_key": latest.workspace_key or item.workspace_key,
                    "metrics": metrics,
                }
            )
        )
    return enriched
