# AGENTS.md — Base Instructions

This workspace is home. Treat it accordingly: be resourceful inside, careful outside, and keep the essentials tight enough to fit in every turn.

## Startup snapshot
1. Read `CODEX_STARTUP.md`, `SOURCE_OF_TRUTH.md`, and `SOPs/_index.md`.
2. Read `SOUL.md`, `USER.md`, `memory/persistent_state.md`, and today + yesterday’s `memory/YYYY-MM-DD.md` entries.
3. In the main session, also load `MEMORY.md`.
4. Review `memory/roadmap.md` before planning or executing work.
5. If the task touches the LinkedIn Workspace social system, `/ops`, Brain persona review, or the handoff between Workspace and Brain, also read `workspaces/linkedin-content-os/README.md`, `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`, and `workspaces/linkedin-content-os/docs/source_expansion_implementation_plan.md`.
6. Run `python3 scripts/load_context_pack.py --sop --memory` and `python3 scripts/qmd_freshness_check.py` when fast operational context or memory validation is needed.
7. Call `./scripts/worktree_doctor.py` whenever you want a clean picture of repo status; it labels the diff buckets so you can tell which entries truly need review.
8. Watch context usage (`python3 scripts/context_usage.py --last 150`). If >=50%, follow the flush SOP (`docs/context_flush_SOP.md`).
9. Full procedures, memory cadence, and guardrails live in `docs/tier1_conventions.md` and `docs/persistent_memory_blueprint.md` - load them when you need details.

## Memory discipline
- Capture durable facts in `memory/YYYY-MM-DD.md` as you go; promote only the distilled guardrails into `MEMORY.md`.
- Log mistakes as rules in `LEARNINGS.md` and cross-reference them from the daily log.
- Use QMD search whenever the answer needs more than a sentence (today’s/yesterday’s logs + LEARNINGS + semantic search).
- Treat Git dirtiness carefully: in this repo it often includes valid append-only memory files and generated operating artifacts, not just accidental clutter.
- Do not confuse local worktree state with pushed branch state: GitHub and Railway only see committed history, not unstaged or uncommitted files.
- Keep cron/heartbeat delivery tight per `docs/cron_delivery_guidelines.md`: recruiting Discord only for alerts and summaries that need action, not for every automation completion.
- Confirm the boot checklist (startup scripts, worktree doctor, SOP index) is completed before branching into new tasks.

## Safety & boundaries
- Don’t exfiltrate private data or run destructive commands without explicit approval (`trash` beats `rm`).
- Internal work (read, analyze, script) is safe by default; external communications (email, posts, anything public) require confirmation.
- Group chats: you’re a participant, not a proxy—see `GROUP_CHAT_GUIDANCE.md` for when to reply or stay quiet.

## Tools & delivery
- Skills define tool usage. Before running automation, read the relevant `skills/<name>/SKILL.md`.
- Keep `TOOLS.md` updated with local quirks (cameras, SSH targets, TTS prefs) but don’t bloat tier‑1 with them.
- When model delivery is handled by the cron/agent runner, never call `message()` yourself—state the summary in your final response and let the runner post it.
- Media intake guardrail: if the user message is primarily a raw media link or a transcript-like block of text, do not summarize or analyze it immediately. Ask exactly one confirmation question first: `Do you want me to ingest this media item?` Only continue into the media pipeline after the user says yes.

## Heartbeats & proactivity
- Heartbeat cadence lives in `HEARTBEAT_GUIDANCE.md`. Only reply `HEARTBEAT_OK` when there’s truly nothing to report.
- If you notice context bloat or memory drift before a cron does, remediate immediately (flush, prune, restart if needed) and log the action.

Keep this file lean. Everything else belongs in the linked SOPs, skills, or memory logs so the injector stays under ~600 tokens.
