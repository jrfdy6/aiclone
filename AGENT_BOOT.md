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
   SOPs/openclaw_local_automation_sop.md
   SOPs/repo_surface_truth_map_sop.md when the task touches whether a page, route, or subtree is live, scaffolded, dormant legacy, or reference only
   SOPs/social_persona_synthesis_roadmap_sop.md when the task touches article understanding, social response quality, persona-aware drafting, comment/repost synthesis, or Lab content observability
   workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md when the task is specifically about Phase 1 article/world understanding, article stance, world-model comparison, or Lab article-side observability
   workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md when the task is specifically about Phase 2 persona retrieval, approved-delta reuse, belief/experience selection quality, or Lab retrieval observability
   workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md when the task is specifically about Phase 3 Johnnie perspective modeling, agreement/pushback/lived-addition logic, or Lab perspective observability
   workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md when the task is specifically about Phase 4 reaction-brief synthesis, article-view/Johnnie-view packaging, or Lab pre-draft synthesis observability
   workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md when the task is specifically about Phase 5 template composition, family tracing, repetition control, or Lab draft-assembly observability
   workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md when the task is specifically about Phase 6 evaluation hardening, benchmark weighting, shipping gates, or Lab scoring observability
   workspaces/linkedin-content-os/docs/type_matrix_expansion_phase7_implementation_plan.md when the task is specifically about Phase 7 type-matrix expansion, agree/contrarian/personal-story/humor behavior, response-type selection, or Lab type-matrix observability
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
- Treat GitHub/Railway visibility as commit-based: uncommitted local files do not exist to GitHub, and Railway will not redeploy from a dirty worktree.
- If a Railway/browser failure looks like CORS, verify `railway service status` and `railway logs` first; in this repo that often means a crashed backend or an incomplete committed deploy, not a true header problem.
- Treat heavy local automations as `launchd`-scheduled OpenClaw workspace jobs, not as gateway-native cron, per `SOPs/openclaw_local_automation_sop.md`.
- Treat social/article content work as governed by `SOPs/social_persona_synthesis_roadmap_sop.md`; do not skip straight to phrasing tweaks when article understanding, persona retrieval, or Johnnie-perspective synthesis are still missing.
- Boot checklist: confirm `memory/roadmap.md`, `SOURCE_OF_TRUTH.md`, and the worktree doctor output before acting, so Codex can skip relearning the same roots.
