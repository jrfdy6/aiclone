# Roadmap — March 19, 2026

## Persistent AI Clone (Phase: Reliability & Memory)
- Stabilize daily workflows so context can be flushed without restarting OpenClaw.
- Verify every cron tied to delivery (Daily Memory Flush, Morning Daily Brief, Memory Health Check, Nightly Self-Improvement, GitHub Backup, Progress Pulse, Rolling Docs) through the runner's final-response path instead of direct `message(...)` calls.
- Exercise Context Guard + manual flush to ensure persistent memory survives compaction.
- Lock in QMD as the backbone: keep the index healthy, rely on search instead of bloating tier‑1 files, and audit AGENTS.md / MEMORY.md budgets so identity + preferences load correctly every wake-up. Treat Railway/Open Brain as the separate app-memory lane, not the restart lane.
- Implement the dream cycle + morning brief automation (gold standard) to ingest YouTube transcripts and other sources overnight, clean memories, and deliver a concise morning recap.
- Run a full shutdown/restart test once the above items are green.

## Media Intake System
- Build one canonical media-ingest pipeline: raw transcript `.txt` drops, podcast/audio files, and video-derived transcripts all converge into the same downstream ingest flow after transcription/normalization.
- Treat file drops as automatic intake:
  1. watcher detects a new `.txt`, audio file, or transcript artifact,
  2. audio/video is transcribed into text if needed,
  3. system scaffolds `knowledge/ingestions/YYYY/MM/<slug>/raw/` + `normalized.md`,
  4. system pushes the content into Open Brain,
  5. system logs a short durable trace to the daily memory lane.
- Keep chat-pasted links or large transcript blocks behind a single confirmation step ("ingest this media item?") instead of guessing from arbitrary pasted content.
- Split review surfaces by job:
  1. build implications stay in OpenClaw for immediate operator decisions,
  2. persona implications go to the Railway Brain/Persona review surface for approval, nuance, and emphasis.
- Shared persona-review rule:
  1. Workspace snippet approval counts as real approval at the shared `persona_deltas` layer,
  2. Brain remains the primary review surface for items that still need context, disagreement, story, wording, or promotion selection,
  3. neither surface auto-writes canonical persona files under `knowledge/persona/feeze/**`.
- Generate draft implications automatically from each ingestion: summary, likely build opportunities, likely persona deltas, standout quotes/stories, and a short review packet for each lane.
- Preserve the promotion boundary: ingest is automatic, but canonical persona updates still require explicit review/approval before writing into `knowledge/persona/feeze/**`.
- Do not create duplicate pipelines for text vs audio vs video; transcription is only the upstream converter, not a separate architecture.
- Reuse existing infrastructure wherever possible (`media/transcripts`, `scripts/watch_transcripts.py`, `scripts/youtube_audio_workflow.py`, `scripts/intake_router.js`, `/api/capture`, `knowledge/ingestions/**`, direct Postgres loaders) instead of introducing a second ingestion stack.
- Implementation sequence:
  1. define the watched inboxes for raw transcript files and audio files,
  2. adapt the existing watcher so new drops are normalized into `knowledge/ingestions/**`,
  3. route normalized content into Open Brain automatically,
  4. generate a build review packet for OpenClaw and a persona review packet for Railway,
  5. persist review outcomes so build actions and persona approvals survive refresh/restart,
  6. only then add extra UX polish or richer automation.
  7. confirmation helper for chat-pasted links/text now routes through `skills/youtube-transcript-ingest/SKILL.md` + `scripts/queue_media_text.py`.
  8. `extensions/media-intake-guard/` now forces the one-question confirmation for raw media links inside OpenClaw chat.
  9. confirmed chat ingests now queue background jobs through `scripts/enqueue_media_job.py` + `scripts/run_media_job.py` and write status artifacts under `memory/media_jobs/<job_id>/status.json` instead of blocking the OpenClaw turn for 30+ minutes.
  10. local status visibility for queued jobs now runs through `python3 scripts/media_job_status.py`.
  11. current follow-up is tightening transcript-paste reliability and the final embedded-local acknowledgement text; the underlying queued media pipeline is now the stable path.

## Automation & Heartbeat hygiene
- Rebuild HEARTBEAT.md guidance around the lighter context pack and cheaper model once Discord delivery is stable.
- Keep Context Guard + cron delivery logs in `memory/cron-prune.md` so we can prove the guardrails work after restarts.
- OpenClaw cron rehab is now tracked explicitly in:
  - `docs/openclaw_cron_rehab_project_plan.md`
  - `docs/openclaw_cron_rehab_execution_checklist.md`
  - `docs/openclaw_cron_rehab_backlog.md`
- Immediate implementation focus is Phase 0 + Phase 1 only:
  - baseline the real OpenClaw cron inventory
  - classify runtime/cost/scope
  - repair stale pathing and missing contract artifacts
  - do not start the 3-agent / 5-workspace operating model until those tickets are closed

## Social Intelligence / Narrative Copilot
- Treat the Workspace social system as LinkedIn-first, not LinkedIn-only: manual URLs, pasted text, LinkedIn saved signals, Reddit, Substack/RSS, and web articles should all converge into one shared signal contract before interpretation.
- Current live baseline:
  1. manual URL/text preview ingestion is live,
  2. split lane taxonomy is live,
  3. quick reply / comment / repost preview generation is live,
  4. quote approval into persona deltas is live,
  5. first-pass belief contrast and lived-experience anchoring are live in the shared social variant builder,
  6. first-pass technique selection and evaluation readouts are live in the shared social variant builder and `/ops`,
  7. expression-quality is now a first-class relational signal in the social variant builder, with source/output quality, expression delta, and structure preservation flowing through evaluation and feedback,
  8. structured feedback logs now capture active lane/stance/technique/evaluation context,
  9. `/ops` now reads a live backend workspace snapshot for plan/reaction/feed state and feedback analytics,
  10. the backend now persists workspace snapshots in Postgres and rebuilds stale snapshot rows from live runtime builders instead of treating container-local artifacts as the source of truth.
  11. `main` now has a repeatable social-workspace safety path: `npm run verify:main` for local smoke/build checks, `npm run verify:production` for live deployed checks, and `.githooks/pre-push` as the local enforcement option.
  12. the live workspace snapshot now carries a first-pass `persona_review_summary`, so `/ops` can show Brain-pending vs Workspace-approved persona state from the same backend source of truth.
- Near-term implementation priority is not more generation. It is a cleaner intelligence stack:
  1. normalize all source paths into one `NormalizedSignal`,
  2. separate extraction from interpretation,
  3. deepen belief contrast beyond the current rule-based first pass and push it into planners,
  4. make technique selection and evaluation data-informed instead of fully rule-based,
  5. expand the structured feedback layer so copy, approval, post outcomes, and expression deltas all feed the same tuning loop,
  6. only then build the shared tuning dashboard and auto-research loops.
- Pinned backlog note (`2026-03-31`): `source_expression` is the next obvious quality pass for LinkedIn OS, but it is intentionally pinned instead of active.
  - Current live state after the latest voice/surfacing pass: `status=passing`, `voice_match_avg=7.5`, `source_expression_avg=7.3`, `benchmark_avg=9.9`.
  - Resume this only after a conscious re-prioritization; do not let it silently replace higher-urgency product or infrastructure work.
- The next source-expansion phase should reuse the parent `Media Intake System` instead of creating a separate transcript stack in the social workspace:
  1. treat YouTube, podcasts, and transcript files as upstream source assets,
  2. segment long-form media into claim-sized units before they enter the social runtime,
  3. route those units into the correct downstream jobs (`comment`, `repost`, `post_seed`, `belief_evidence`) instead of forcing every source into a feed-card response,
  3a. keep `daily_briefs` and `weekly_plan` on that same upstream source system instead of letting briefing or planner work drift into separate ingest assumptions,
  4. use those source contrasts to build reviewable worldview evidence for the persona system without auto-writing canonical persona files.
  5. route that worldview evidence into the shared `persona_deltas` lifecycle so Brain and Workspace stay on one approval substrate instead of parallel persona systems.
     - First pass is now live through `backend/app/services/social_persona_review_service.py` and `backend/app/services/workspace_snapshot_service.py`, which sync transcript-derived worldview segments into draft `persona_deltas` during snapshot rebuilds.
  6. Workspace approval of a snippet should count as approval and should not create a duplicate Brain re-approval loop; Brain should focus on unresolved persona items and long-form worldview review.
  7. the first runtime source-asset inventory is now live in the workspace snapshot and `/ops`; transcript/media assets are visible upstream before segmentation but are not yet eligible for direct feed-card routing.
  7a. the first runtime long-form routing layer is now live through `backend/app/services/social_long_form_signal_service.py`, `workspace_snapshot_service.py`, and `/ops`; the same shared candidate set now classifies transcript/media segments into `comment`, `repost`, `post_seed`, and `belief_evidence`, and Brain review consumes the `belief_evidence` slice from that shared routing pass instead of a second transcript parser.
  7b. the weekly-plan snapshot now reuses that shared route set for `media_post_seeds` and `belief_evidence_candidates`, which keeps planner-side media reuse on the same contract rather than a separate planning-only media parser.
  7c. planner freshness metadata is now live: production returns routed media overlays with fresh `weekly_plan.generated_at`, preserved `base_generated_at`, and consistent `media_post_seeds` / `belief_evidence_candidates` counts.
  7d. the Brain daily-brief surface now reads the same live source-intelligence overlay as the planner and `/ops`, through `backend/app/services/daily_brief_service.py` and `frontend/app/brain/BrainClient.tsx`. The follow-on is to deepen how briefs consume that contract over time, not to build a second briefing/source stack.
  8. keep the live `/ops` tuning dashboard as the benchmark source of truth, using `Avg Source`, `Avg Expr`, `Avg Δ`, `Weak Source`, `Lane Carried`, source-class health, and the attention queue as the main release metrics for each source-expansion step.
  8a. keep the architectural north star explicit: one ingest surface, multiple consumers. The goal is not “put transcripts into the feed.” The goal is “let the same source asset feed briefs, planning, persona review, and feed routing without duplicate stacks.”
  9. treat source-expansion work as incomplete until it passes the full production validation cadence:
     - immediate validation (`0-10m` after deploy),
     - deterministic rebuild validation (`10-20m`),
     - full refresh validation (`20-60m`),
     - next-cycle validation (`12-24h`).
  10. current production note (`2026-03-28`): after the source-taxonomy rollout, the refreshed mixed feed recovered LinkedIn + RSS/Substack items but did not surface Reddit. If that is still true on the next-cycle check, reprioritize Reddit source-adapter debugging ahead of transcript/media expansion.
- `karpathy/autoresearch` is explicitly parked as a later Lab-stage tuning tool. Use it to optimize lane/stance/technique policy once the feedback loop and tuning dashboard are trustworthy, not as the current path for making the product smarter.
- Use orchestration as the core species for the product behavior, coding harnesses for implementation work, auto research for tuning, and dark-factory behavior only for low-risk offline generation.
- Canonical workspace implementation map: `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- Source-expansion implementation map: `workspaces/linkedin-content-os/docs/source_expansion_implementation_plan.md`

## Brain As Control Plane
- Treat `frontend/app/brain/` as the canonical global surface for:
  - daily briefs
  - persona review and promotion
  - automation telemetry
  - docs and knowledge browsing
  - cross-project source intelligence
- Treat project `Workspace` surfaces as execution lanes:
  - project strategy
  - project drafts
  - project tasks
  - project-local research
  - project-specific agents
- A project workspace may expose thin mirrors or quick-capture handoffs into Brain, but it should not become the primary global home for persona, briefs, docs, or automation understanding.
- Near-term implementation goals:
  1. restore rich Brain persona response controls for agreement, disagreement, nuance, personal story, and wording/context refinement
  2. reconcile Brain dashboard telemetry and Brain automations telemetry onto one explainable source of truth
  3. surface knowledge docs in the Brain Docs tab instead of leaving docs fragmented or invisible
  4. move global source-intelligence interpretation and long-form source registration toward Brain-first ownership, while keeping Workspace project-local
  5. keep Workspace approval as a fast approval path into the shared `persona_deltas` lifecycle without forcing duplicate Brain approval
  6. enforce the canonical persona promotion contract:
     - add semantic extraction before canon writes
     - require artifact/output grounding for `history/initiatives.md`
     - block or reroute initiative promotions when no artifact anchor exists
     - stop writing review-note language directly into canonical initiative fields
     - keep local bundle sync as the durability lane and bundle-first content generation as the immediate-read lane
  7. implementation source of truth for that work now lives in `SOPs/persona_canon_promotion_sop.md`
  8. define a separate Brain `Identity State` tab for:
     - tight core identity
     - absorbed bundle material
     - explicit `reinforces_core` / `reshapes_core` / `context_only` / `unresolved_tension` relationships
     - a visible current-state readout of who Johnnie is becoming over time
  9. pin `Identity State` implementation behind persona-to-content quality:
     - do not make this the active build while content generation still needs work reading persona canon and producing meaningful posts
     - current build priority remains bundle-first persona context plus stronger content-generation usage of that canon
  10. implementation source of truth for that future tab now lives in `SOPs/persona_identity_state_sop.md`

## Persona-Grounded Content Generation
- Treat persona-to-content quality as a retrieval-and-grounding architecture problem, not a prompt-only problem.
- Refactor the live content route into a staged planner/writer/critic pipeline so strategy, prose, and genericity control stop competing inside one mega-prompt.
- Keep a small always-on `core identity` lane for content generation:
  - `identity/claims.md`
  - `identity/philosophy.md`
  - `identity/decision_principles.md`
  - `identity/VOICE_PATTERNS.md`
- Split support memory into typed lanes instead of one mixed retrieval pool:
  - `proof`
  - `story`
  - `example`
  - optional `ambient`
- Add typed metadata to bundle chunks in `backend/app/services/persona_bundle_context_service.py` so the route can reason about:
  - memory role
  - domain tags
  - audience tags
  - proof kind / strength
  - artifact grounding
- Move prompt assembly and retrieval composition out of `backend/app/routes/content_generation.py` into a dedicated context service so the route stops hand-managing all retrieval concerns inline.
- Preserve the rhetorical layer as a separate concern from grounding:
  - contrarian reframe
  - agreement-and-extend
  - drama/tension
  - story with payoff
  - recognition
  - warning
  - the system should get more factual and more controlled without getting flatter or more generic
- Add a grounding evaluator before drafting:
  - `proof_ready`
  - `principle_only`
  - `story_supported`
  - `insufficient_grounding`
- Make `tech_ai` and similar domains fail closed:
  - if no AI/operator proof is present, write a principle-led post
  - do not borrow generic leadership, admissions, or school-process stories as AI proof
  - do not transform real metrics into new unsupported claims
- Convert the example lane into a typed example bank selected by:
  - domain
  - audience
  - post archetype
  - tone
  instead of broad similarity alone
- Add fixed eval prompts and production checks for:
  - `workflow clarity`
  - `agent orchestration`
  - `AI systems`
  - `leadership clarity`
  - `relationship-first market development`
- Canonical implementation source of truth: `SOPs/persona_grounded_content_generation_sop.md`

## Parking lot (post-stabilization)
- Memory optimizer skill (nightly tier‑1 audit + progressive disclosure guardrails).
- Rhetorical analyzer skill (Opus-powered fact-checking pipeline for ingesting outside reporting without dragging propaganda into memory).
- Restore native `pgvector` for the Open Brain memory lane once the app is stable; production is currently on `embedding_json` + Python cosine because the live Railway Postgres image does not expose the `vector` extension.

## Roadmap maintenance
- Use `scripts/update_roadmap.sh` to append findings from new transcripts/content ingestions so this file stays current.
- Fold any new objectives (architecture brief, backlog entries, deployment tweaks) into this document instead of reviving the old phase files.

_Last updated via manual entry on 2026-03-22 10:52 ET. Future updates will append to this file using scripts/update_roadmap.sh when new transcripts land._
