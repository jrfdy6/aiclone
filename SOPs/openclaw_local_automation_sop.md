# SOP: OpenClaw Local Automation Scheduling

## Purpose
Define how local automations should run inside the OpenClaw system without confusing `OpenClaw`, `launchd`, `Railway`, and `Brain`.

This is the canonical rule:
- `launchd` schedules heavy local jobs on the Mac
- `OpenClaw` provides the workspace, continuity, logs, and shared system context
- `Railway` handles hosted backend work
- `Brain` displays and explains the automation layer

## Scope
- Local media-heavy jobs
- Filesystem-writing jobs that must run on the machine
- OpenClaw workspace automations that should survive chat/session boundaries
- Brain automation inventory and operator visibility

## Decision Rules
Use `launchd` when the job:
- needs `yt-dlp`
- needs `ffmpeg`
- needs caption download, a compatible Whisper runtime, or other local media tooling
- writes durable local files under the workspace
- should keep running even if an OpenClaw chat session is idle or gone

Use `Railway` when the job:
- only needs hosted backend/runtime access
- does not depend on local binaries or local filesystem state
- should run as part of the deployed app

Use `OpenClaw` as the framework layer when the job:
- lives inside `/Users/neo/.openclaw/workspace`
- reads shared SOPs, memory, or watchlists
- writes into the shared Brain/source system
- should appear in Brain / Mission Control as part of the operating system

## Boundary
OpenClaw is not the cron engine.

OpenClaw is the operating environment:
- repo/workspace
- startup/boot context
- shared logs
- shared source system
- Brain/Mission Control visibility

For local heavy jobs, the scheduler should be `launchd`, not the OpenClaw gateway.

That is the preferred pattern because `launchd` is more durable for:
- long-running downloads
- transcript generation
- jobs that can take hours on the local machine

## Thin Trigger Pattern
If a human can start a workflow from the Railway UI, OpenClaw should not click the frontend.

OpenClaw should call the same backend contract directly, then let the existing watcher or `launchd` worker handle execution.

Canonical examples:
- content generation trigger:
  `python3 /Users/neo/.openclaw/workspace/scripts/enqueue_content_generation_job.py --topic "workflow clarity" --context "Use the operator angle." --wait --include-artifacts`
- coding / PM trigger:
  `python3 /Users/neo/.openclaw/workspace/scripts/enqueue_pm_execution_card.py --workspace-key fusion-os --title "Wire the next delegated coding lane" --reason "OpenClaw queued this task without using the UI." --instruction "Use the PM card as the source of truth."`

This keeps the trigger cheap:
- OpenClaw only spends tokens deciding when to enqueue work
- the Railway backend stays the thin trigger/status layer
- the local watcher or `launchd` worker does the heavy execution

Do not make OpenClaw depend on:
- DOM selectors
- browser login state
- page layout
- UI hydration timing

## Current Pattern
The current canonical example is the YouTube watchlist worker:
- runner: [youtube_watchlist_auto_ingest.py](/Users/neo/.openclaw/workspace/automations/youtube_watchlist_auto_ingest.py)
- launch agent: [com.neo.youtube_watchlist_auto_ingest.plist](/Users/neo/.openclaw/workspace/automations/com.neo.youtube_watchlist_auto_ingest.plist)
- visible in Brain/Mission Control through:
  - [automation_service.py](/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py)
  - `/api/automations/`

That worker:
- runs inside the OpenClaw workspace
- is scheduled by `launchd`
- reads the watchlist
- discovers new YouTube videos
- prefers downloadable YouTube captions first
- falls back to local audio + Whisper only when a compatible runtime is actually present
- ingests them into the shared Brain long-form/source system
- refreshes workspace snapshots after ingest

## Current Cadence
For the local YouTube watchlist worker:
- interval: every `2 hours`
- reason: caption retrieval, fallback media download, and local transcript generation can take a long time on this device

Do not set local media-heavy automations to aggressive cadences unless the runtime has been proven stable.

## Cheap Model Defaults
If a local automation needs lightweight model help for easy tasks, prefer:
1. `ollama`
2. `gemini flash`
3. `openai`

The current YouTube watchlist worker applies these defaults for cheap downstream tasks:
- provider order: `ollama,gemini,openai`
- local Ollama model: `llama3.1:latest`
- Gemini fast/editor model: `gemini-2.5-flash`

Important:
- ingest/download/transcription itself is not an LLM task
- those cheap-model defaults are for lightweight downstream processing, not for the media pipeline itself

## Transcript Runtime Rule
Do not treat any installed `whisper` Python package as valid by default.

The local media runtime is only transcript-capable when:
- `yt-dlp` is available
- `ffmpeg` is available
- the installed `whisper` module exposes `load_model` from a compatible Whisper backend

If that runtime is not present:
- the worker should still attempt caption-based transcript capture
- URL-only assets should remain pending if neither captions nor a compatible Whisper backend are available
- Brain should reflect the true runtime state instead of claiming local Whisper support

## Required Artifacts For A New Local Automation
Any new OpenClaw-local automation should have:
1. a runner script under `automations/`
2. a matching `LaunchAgent` plist
3. a Brain-visible entry in [automation_service.py](/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py)
4. a test covering the registry or contract
5. a log path inside `/Users/neo/.openclaw/logs/`

## Notes
- If Brain says an automation exists, there should be a real script or runtime behind it.
- If a job is local-only, Brain should say so explicitly.
- If the runtime needs local binaries, do not pretend Railway is the execution environment.
- Cross-link back to [SOP Index](./_index.md) when adding future automation contracts.
