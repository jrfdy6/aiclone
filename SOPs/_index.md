# SOP Index

> Authority: procedure registry subordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md)
> Last reconciled: 2026-07-20

Start with `SOURCE_OF_TRUTH.md`. Use this index to identify whether a procedure is active, evolving, planned, or retired before following it. A file existing in `SOPs/` does not make it active runtime truth.

## Status meanings

- **Active** — governs a live workflow now.
- **Evolving** — active guardrails with implementation still being improved.
- **Planned** — design or roadmap; do not describe its proposed components as live.
- **Retired** — compatibility pointer or historical evidence; never an active dependency.

## Active procedures

| Capability | Status | Procedure | Runtime or evidence |
| --- | --- | --- | --- |
| Codex-native local scheduling and execution authorization | Active | [Codex-Native Local Automation](./codex_native_local_automation_sop.md) | `launchd`, signed Railway PM queue, local Codex runners, `execution_gate/v1` |
| Railway deployment and service diagnosis | Active | [Railway API Usage](./railway_api_sop.md) | Railway CLI, production health, service logs |
| Release safety | Active | [Main Safety Release Flow](./main_safety_release_sop.md) | verification scripts and staged Railway deploys |
| Startup worktree hygiene | Active | [Worktree Hygiene](./worktree_hygiene_sop.md) | `scripts/worktree_doctor.py` |
| Live, scaffolded, dormant, and reference surface classification | Active | [Repo Surface Truth Map](./repo_surface_truth_map_sop.md) | route wiring, deployed runtime, repo inventory |
| Portfolio identity and project routing | Active | [Workspace Portfolio Registry](./workspace_portfolio_registry_sop.md) | workspace registry, path allowlists, project packs |
| Brain versus project-workspace ownership | Active | [Brain vs Workspace Boundary](./brain_workspace_boundary_sop.md) | Brain global state and workspace-local execution |
| Shared source ingestion and routing | Active | [Shared Source System Contract](./source_system_contract_sop.md) | `knowledge/ingestions/**`, transcript library, source routing |
| Persona canon promotion | Evolving | [Persona Canon Promotion Contract](./persona_canon_promotion_sop.md) | `persona_deltas`, extractor/gate, canonical bundle writer |

## Evolving and planned product contracts

| Capability | Status | Procedure | Boundary |
| --- | --- | --- | --- |
| Pre-draft idea admission | Planned | [Idea Qualification Gate](./idea_qualification_gate_sop.md) | Proposed normalized candidate and qualification report |
| Persona identity-state representation | Planned | [Persona Identity State](./persona_identity_state_sop.md) | Proposed core/bundle/reshape visibility |
| Persona-grounded content generation | Evolving | [Persona-Grounded Content Generation](./persona_grounded_content_generation_sop.md) | Typed retrieval and grounding improvements |
| Staged content planning/writing/critique | Planned | [Staged Content Generation Map](./content_generation_staged_pipeline_map.md) | Target decomposition of the current generation path |
| Social/article persona synthesis | Planned roadmap | [Social Persona Synthesis Roadmap](./social_persona_synthesis_roadmap_sop.md) | Multi-phase source-to-Johnnie-reaction roadmap |
| Invite-only Neo professional conversations | Evolving | [Neo Guest Conversation](./neo_guest_conversation_sop.md) | Separate guest auth, versioned approved public knowledge pack, deterministic local worker, owner-approved meeting requests |

The phase plans linked from the social-persona roadmap are subordinate implementation plans. Their presence does not mean a phase is deployed.

## Retired compatibility documents

| Former capability | Status | Document | Current replacement |
| --- | --- | --- | --- |
| OpenClaw local automation | Retired | [Predecessor Local Automation](./openclaw_local_automation_sop.md) | [Codex-Native Local Automation](./codex_native_local_automation_sop.md) |
| OpenClaw model-mediated workspace alignment | Retired | [Workspace Alignment Verification](./openclaw_workspace_alignment_audit_sop.md) | deterministic registry, path, and launchd audits |

## Maintenance rule

1. Reconcile architecture or policy changes in `SOURCE_OF_TRUTH.md` first.
2. Update the relevant SOP and this status table in the same change.
3. Link every SOP back to `SOURCE_OF_TRUTH.md` and this index.
4. Never leave a broken link in this registry.
5. Run `python3 scripts/verify_documentation_truth.py` before release.
