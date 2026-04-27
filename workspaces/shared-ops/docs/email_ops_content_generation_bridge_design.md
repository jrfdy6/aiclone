# Email Ops Content Generation Bridge Design

## Purpose

Define how the live inbox system should use the current content-generation pipeline to draft emails without re-importing the old `downloads/aiclone` outreach model as architecture.

This document answers one specific question:

How should `email_ops` call into the current content-generation system so Gmail-thread drafting becomes grounded, production-safe, and operationally useful?

## Current Read

### What exists now

The current inbox system is real and operationally grounded:
- Gmail sync and thread ingestion
- workspace and lane routing
- `needs_human` / `high_value` / `high_risk`
- thread list/detail UI
- PM escalation

Relevant files:
- `backend/app/routes/email_ops.py`
- `backend/app/services/email_ops_service.py`
- `backend/app/services/gmail_inbox_service.py`
- `frontend/app/inbox/page.tsx`
- `frontend/app/inbox/[threadId]/page.tsx`
- `workspaces/shared-ops/docs/portfolio_inbox_routing_spec.md`

The current content-generation system is also real:
- codex-job execution path
- grounded retrieval modes
- persona/source-aware prompts
- existing `cold_email` mode

Relevant files:
- `backend/app/routes/content_generation.py`
- `backend/app/services/content_generation_context_service.py`
- `frontend/app/content-pipeline/page.tsx`

### What the gap is

`email_ops` currently drafts with lane templates, not the content-generation system.

Current behavior in `email_ops_service.py`:
- `acknowledge`
- `qualify`
- `schedule`
- `decline_or_redirect`

These are operationally safe, but they are simple templates. They do not use:
- thread-specific generation
- persona-aware drafting
- proof-aware writing
- current content-generation grounding and voice controls

### What the old repo actually represents

The old `downloads/aiclone` email lane was primarily:
- outbound cold-email drafting
- topic/context/personal-brand framing
- mock outreach operator UX

It was **not** a Gmail-thread reply system.

So the compatibility judgment is:

- legacy cold-email framing may still be useful as editorial guidance
- the legacy email architecture should **not** be ported into the new runtime

## Decision

Do **not** migrate the legacy email framework wholesale.

Instead:

1. Keep `email_ops` as the control plane for inbox work.
2. Use the current content-generation system as the draft engine.
3. Add an email-specific grounding layer between them.
4. Treat legacy cold-email patterns as optional writing heuristics only.

In short:

`Gmail thread -> email_ops routing/state -> email drafting packet -> content generation -> review/store`

not:

`legacy outreach UI -> old cold-email prompts -> inbox`

## Current Target State

For the current rollout, the app is a drafting authority, not a sending authority.

The intended near-term outcome is:

- live Gmail thread ingest
- routing and lane classification inside `email_ops`
- grounded draft generation using the current content-generation system
- draft stored on the thread/inbox surface
- human review and editing before any send decision

Manual send outside the app is acceptable for now.

`approve` / `send` / sent-message audit closure is explicitly deferred unless there is a later decision to make the app the system of record for sending.

## Recommended Architecture

### Ownership split

`email_ops` should own:
- provider sync
- thread model
- workspace and lane routing
- draft intent
- human review requirements
- draft persistence on the thread/inbox surface
- optional future approve/send/audit lifecycle

`content_generation` should own:
- prompt construction
- voice grounding
- proof/story retrieval
- option generation
- quality shaping

`email drafting bridge` should own:
- conversion of a thread into a generation packet
- allowed email generation modes
- email-specific prompt safety rules
- draft metadata and audit handoff

### New bridge layer

Add a dedicated service:

- `backend/app/services/email_drafting_bridge_service.py`

Its job:
- accept an `EmailThread`
- derive an email-drafting packet
- choose the right content-generation mode
- submit a codex job or direct internal generation call
- return a structured email draft payload back to `email_ops`

This keeps `email_ops` from embedding prompt logic directly.

## Drafting Modes

The current `cold_email` content type is not enough for inbox work.

Add these email-specific drafting modes:

1. `email_reply`
   Use for replying to an inbound live thread.

2. `email_follow_up`
   Use when a prior conversation exists and we are nudging or advancing next steps.

3. `outbound_email`
   Use for proactive outreach where there is no inbound thread grounding.

Recommended rule:
- inbox thread draft button defaults to `email_reply`
- outbound prospecting/workspace tools may later use `outbound_email`

Do not force inbound Gmail replies through `cold_email`.

## Grounding Modes

The current source modes are:
- `persona_only`
- `selected_source`
- `recent_signals`

That is not enough for email replies.

Add one new grounding mode:

- `email_thread_grounded`

Its precedence should be:

1. current thread facts
2. workspace lane and approved operational facts
3. persona/voice guidance
4. optional source/support material if explicitly relevant

This matters because email drafting should privilege:
- what the sender actually asked
- what the workspace can actually claim
- what action is appropriate for the lane

over general brand voice.

## Email Drafting Packet

The bridge should build a canonical packet with fields like:

```json
{
  "thread_id": "email-thread-id",
  "workspace_key": "agc",
  "lane": "consulting_opportunity",
  "draft_mode": "email_reply",
  "draft_type": "qualify",
  "source_mode": "email_thread_grounded",
  "subject": "Original thread subject",
  "from_address": "sender@example.com",
  "organization": "Sender Org",
  "thread_summary": "Short factual summary",
  "latest_inbound_message": "Last inbound body text",
  "recent_thread_history": ["...", "..."],
  "routing_reasons": ["alias:agc", "keyword:quote"],
  "needs_human": true,
  "high_value": true,
  "high_risk": false,
  "allowed_claims": ["We can review the request and propose next steps."],
  "disallowed_claims": ["Do not promise pricing or compliance claims not verified."],
  "cta_goal": "ask_for_scope_details",
  "signature_name": "Johnnie Fields",
  "signature_block": "Johnnie Fields\\nAcorn Global Collective"
}
```

This packet should be factual and operational, not prose-heavy.

## Model Changes

### `EmailThreadDraftRequest`

Expand beyond only `draft_type`.

Recommended additions:

```python
draft_mode: Literal["email_reply", "email_follow_up", "outbound_email"] | None
draft_engine: Literal["template", "content_generation"] | None
source_mode: Literal["email_thread_grounded", "persona_only", "selected_source", "recent_signals"] | None
operator_notes: str | None
```

### `EmailThread`

Add draft metadata fields:

```python
draft_engine: str | None
draft_source_mode: str | None
draft_job_id: str | None
draft_audit: dict[str, Any] | None
draft_confidence: float | None
```

This lets the inbox audit panel show where the draft came from.

## API Contract

Keep the main route:

- `POST /api/email/threads/{thread_id}/draft`

But change its behavior so it can choose between:
- `template`
- `content_generation`

Recommended near-term default:

- `template` for high-risk or missing-context cases
- `content_generation` for grounded reply drafting when thread data is sufficient

Later, if send authority is intentionally brought into the app, add:
- `POST /api/email/threads/{thread_id}/approve`
- `POST /api/email/threads/{thread_id}/send`

Those already exist in the inbox spec, but they are not required for the current draft-first target state.

## Prompt Contract

The bridge prompt should be email-specific, not social-post specific.

Required rules:

1. Reply to the actual thread, not the abstract topic.
2. Preserve only claims supported by:
   - thread text
   - routed workspace facts
   - approved operational truths
3. Do not invent:
   - prior relationship
   - pricing
   - product capability
   - legal/compliance posture
   - availability promises
4. Keep the body skimmable:
   - short paragraphs
   - one clear next action
   - no social-post cadence
5. Match workspace tone:
   - AGC: direct, competent, buyer-ready
   - Fusion: warm, clear, intake-oriented
   - FEEZIE: human and relational, not salesy
   - Shared Ops: concise and operational

## Legacy Rules Worth Keeping

These are the only legacy cold-email traits worth carrying over:

- anti-jargon discipline
- short, skimmable paragraphs
- one clear CTA
- direct but warm tone
- persona consistency where appropriate

Do **not** carry over:

- old outreach runtime assumptions
- topic-only prompting for inbox replies
- fabricated personal-story framing
- old mock outreach UI as product truth

## Fallback Policy

This bridge should be explicit about when it falls back.

Allowed near-term fallback:
- if thread grounding is insufficient, use the current template path

Treat as failure, not silent fallback:
- if the generator cannot produce a draft and the system pretends it did
- if a high-risk lane auto-switches into unreviewed generative mode

Recommended policy class:
- `content_generation_email_thread_to_template_fallback`

This should be added to the fallback inventory when implemented.

## Rollout Plan

### Phase A
Keep existing templates, but add draft metadata and bridge scaffolding.

Status:
- implemented

Exit criteria:
- no behavior change for operators yet
- email draft packet can be built deterministically

### Phase B
Enable `content_generation` for low-risk grounded replies on selected lanes.

Status:
- implemented for selected low-risk `primary` lanes

Current enabled lanes:
- `fusion-os`
- `feezie-os`

Exit criteria:
- operators can compare template vs generated drafts
- drafts show source/audit metadata

### Phase C
Enable human-reviewed generative drafting across major lanes.

Status:
- optional next expansion, not required for current target state

Exit criteria:
- `email_ops` uses content-generation as the preferred engine for supported lanes
- templates remain safety fallback only

### Phase D
Add approve/send/audit closure.

Status:
- deferred

Exit criteria:
- approved drafts can be sent
- sent state is recorded on the thread
- audit trail captures who approved, what changed, and what was sent

This phase is not required for success if draft generation and storage on the inbox surface is sufficient.

## Acceptance Criteria

This bridge is successful when:

- inbound Gmail replies are grounded in actual thread context
- drafting uses the live content-generation system, not a legacy outreach architecture
- generated or template drafts are stored on the live thread/inbox surface
- operators can review and edit drafts before any send decision
- operators can see whether a draft came from template or generation
- unsupported claims are harder, not easier, to produce
- the inbox review flow gets better without losing operational safety
- the system does not need to become the send authority yet

## Recommendation

The current implementation priority should be:

1. add the email drafting packet builder
2. expand `EmailThreadDraftRequest` and `EmailThread`
3. support `draft_engine=content_generation`
4. introduce `email_thread_grounded`
5. keep templates as the explicit safety fallback during rollout
6. stop after Phase B or Phase C if draft generation and storage meets the operational need

Do not start by porting the old cold-email framework.
Start by making the current inbox system capable of grounded generative replies.
