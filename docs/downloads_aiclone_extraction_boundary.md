# downloads/aiclone Extraction Boundary

## Decision

`downloads/aiclone` is a **donor/reference lane**, not an active product surface and not a submodule candidate.

Current boundary:

- status class: `reference_only`
- operational role: `bounded donor repo`
- short-term purpose: preserve old outreach/email/content patterns that may still be worth selective extraction
- long-term goal: stop letting it live as ambient ambiguity inside the active workspace

## What It Is Still Good For

The old repo is still useful for:

1. **outreach prompt and copy patterns**
   - manual outreach prompt flows
   - `cold_email` framing inside the older content pipeline
   - older UI language around prospect outreach and follow-ups

2. **topic-intelligence-to-outreach patterns**
   - template generation concepts
   - prospect intelligence to outbound-message shaping

3. **historic operating context**
   - old docs, persona, and positioning references that may still explain why certain product choices existed

## What Is Not Worth Porting

Do **not** treat the old repo as the source for:

- inbox/email-ops architecture
- production routing model
- PM / Brain / workspace control-plane behavior
- nested runtime artifacts like `.next`, `.venv`, `node_modules`, logs

The rebuilt repo already surpassed the old one in those areas.

## Extraction Classification

### Worth porting

- outbound email / outreach copy patterns that still map to current use cases
- topic-intelligence-derived outreach templates if they improve current drafting lanes
- any prompt-library material that can be cleanly moved into the current persona/content system

### Worth referencing only

- old product pages for visual or workflow memory
- archived deployment guides and roadmaps
- old knowledge packs already imported into `knowledge/aiclone/**`

### Worth abandoning

- legacy dashboard/runtime assumptions
- old unmounted product routes
- old repo build/runtime artifacts
- any architecture that conflicts with the current control-plane model

## Remaining Extraction Targets

Current finite extraction targets:

1. `outreach_manual` prompt/workflow pattern review
2. `cold_email` generation prompts and framing
3. topic-intelligence outreach-template patterns
4. any still-useful admissions / outreach prompt-library material tied to Fusion/client work

If these are extracted or deliberately rejected, the old repo stops earning active workspace residency.

## Post-Extraction Boundary

After the remaining extraction targets are handled:

1. keep `downloads/aiclone` only as cold reference if it is still useful for occasional archaeology
2. otherwise move it out of the active repo tree

Current recommendation:

- **do not** promote it into a formal submodule
- **do not** treat it as an editable secondary workspace
- **do** keep it bounded to explicit extraction decisions only

## Success Condition

This phase is complete when:

- the remaining extraction targets are explicit,
- the old repo is no longer treated as a general-purpose fallback source,
- and operators can explain exactly why it still exists.
