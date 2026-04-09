# AGENTS.md - shared_ops Executive Lane

## Startup
1. Read local `IDENTITY.md`, `SOUL.md`, `USER.md`, and `CHARTER.md`.
2. Read `docs/README.md` plus the latest relevant dated review artifact (`workspace_pack_executive_review_YYYY-MM-DD.md`, `heartbeat_verification_YYYY-MM-DD.md`, or similar) to understand the latest accountability findings.
3. Read `memory/execution_log.md` to confirm what already shipped.
4. Read the active dispatch packet + briefing (`dispatch/*.json`, `briefings/*.md`) for the card being handled.
5. Read the base pack (`../../AGENTS.md`, `../../SOUL.md`, `../../IDENTITY.md`, `../../USER.md`, `../../CHARTER.md`, `../../MEMORY.md`) so executive guardrails stay aligned.
6. Read the linked PM card and standup prep entry before adjusting scope or priority.

## Operating Rules
- Jean-Claude executes directly here. Keep the work inside `shared_ops` and use workspace agents for every other lane.
- Treat PM truth as the north star: dispatch via the PM queue, write results via `scripts/runners/write_execution_result.py`, and log every action in `memory/execution_log.md`.
- Keep registry, packets, and UI labels in sync. If a naming mismatch appears, fix the generator or registry entry before shipping more work.
- Diagnose before declaring victory: cite heartbeat reports, standup prep entries, or workspace review docs when reporting state.
- When a follow-up belongs to another workspace, log it explicitly and route it outward instead of absorbing it here.
