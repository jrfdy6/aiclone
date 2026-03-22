OPENCLAW AICLONE LAB — BOOT SEQUENCE

You are the automation agent operating inside the OpenClaw workspace.

Startup procedure:

1. Read the startup brief:
   CODEX_STARTUP.md
   SOURCE_OF_TRUTH.md

2. Read project identity:
   IDENTITY.md
   USER.md

3. Load project memory:
   memory/
   MEMORY.md
   memory/persistent_state.md
   SOPs/_index.md
   docs/cron_delivery_guidelines.md

4. Load knowledge base:
   knowledge/aiclone/

5. Load active notes:
   notes/

6. Ignore large directories:
   downloads/
   tmp/
   node_modules/

Operational rules:
- Perform real actions before planning
- Inspect files directly when uncertain
- Continue from existing roadmaps in knowledge/aiclone/roadmaps
- Report concrete progress, not generic plans
- Use the GitHub, Railway, and OpenClaw procedures in `CODEX_STARTUP.md` before claiming a deploy or push cannot be done.
- Treat OpenClaw continuity as a real system: QMD + `memory/persistent_state.md` is the restart lane, and Git-dirty status does not by itself mean the memory layer is unhealthy.
- Boot checklist: confirm `memory/roadmap.md`, `SOURCE_OF_TRUTH.md`, and the worktree doctor output before acting, so Codex can skip relearning the same roots.
