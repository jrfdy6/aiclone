# AGC Email Lane System Blueprint

## Objective

Build a workspace-aware email system inside the existing frontend/backend stack that:

- organizes inbound email into clear operating lanes
- drafts replies when confidence is high
- escalates risky or high-value threads to humans
- turns qualified inbound email into traceable AGC traction data

The first goal is not full auto-reply.
The first goal is controlled intake, routing, and human-legible action.

## Current Recommendation

Use a `human-in-the-loop first` model.

That means:

- auto-classify every inbound message
- auto-summarize every thread
- auto-draft responses when useful
- auto-send only low-risk acknowledgements later, after the review lane is stable

Do not start with a fully autonomous mailbox.
AGC is still tightening positioning, proof, and qualification rules.

## Why This Fits The Current Stack

The existing system already has the right orchestration primitives:

- PM cards for human action and escalation
- execution queues for active work
- owner-review patterns in the frontend
- AGC-specific inbound email qualification rules in `docs/inbound_email_protocol.md`

The clean implementation path is to add `email intake + classification + draft/review` on top of those existing primitives.

Portfolio-wide mailbox routing should follow:

- `../../shared-ops/docs/portfolio_inbox_routing_spec.md`

That shared-ops document is the upstream source of truth for:

- one-mailbox alias design
- workspace routing precedence
- Gmail labels and starter filters
- AGC workspace routing entry conditions

## Routing Model

Email should route in two steps.

### Step 1: Workspace Route

Every thread should be assigned to a top-level workspace:

- `agc`
- `fusion-os`
- `feezie-os`
- `shared_ops`
- `unknown`

For the current AGC build, `agc` is the only required live lane.

### Step 2: AGC Functional Lane

Inside `agc`, use these working lanes:

1. `consulting_opportunity`
   Consulting buyers asking about operational clarity, workflow modernization, audits, implementation support, or discovery calls.
2. `product_sourcing`
   Requests for products, catalogs, pricing, supplier availability, or sourcing support.
3. `supplier_partner`
   Manufacturers, distributors, teaming partners, reseller onboarding, or vendor relationship emails.
4. `registrations_compliance`
   Vendor onboarding, required forms, certifications, insurance, tax docs, portals, and registration workflow.
5. `finance_admin`
   Invoices, payments, accounting, scheduling logistics, general administration.
6. `noise_archive`
   Spam, newsletters, irrelevant outreach, low-signal noise, or duplicates.

## Message States

Each thread should move through a simple state machine:

`new -> triaged -> drafted -> human_review -> sent -> waiting -> qualified_or_closed`

Additional flags:

- `needs_human`
- `high_value`
- `high_risk`
- `sla_at_risk`
- `linked_opportunity`

## Human Escalation Rules

Always escalate to a human when any of these are true:

- the message asks for pricing, terms, or scope commitment
- the message asks for certifications, legal language, security answers, or compliance commitments
- the message contains an RFP, RFQ, SOW, or attached procurement document
- the message appears to come from a real buyer, prime, or institutional decision-maker
- the system confidence is below threshold
- the draft would require proof AGC cannot honestly claim

Auto-send should be allowed only for narrow low-risk cases later:

- acknowledgement of receipt
- scheduling confirmation
- portal-registration confirmation
- simple routing confirmation

## Recommended Frontend Surface

Build a dedicated inbox surface in the frontend instead of hiding this inside generic ops.

Recommended route:

- `frontend/app/agc-inbox/page.tsx`

Core panels:

1. `Lane Board`
   Shows thread counts, overdue items, and SLA pressure by lane.
2. `Needs Human`
   Mirrors the owner-inbox pattern for threads that need human review.
3. `Thread Detail`
   Shows full email history, extracted entities, lane decision, opportunity link, and suggested response.
4. `Draft Review`
   Lets the operator approve, edit, reject, or escalate a draft.
5. `Traction Log`
   Shows which qualified emails were linked to `analytics/inbound_email_log.csv` and `analytics/opportunity_ledger.csv`.

## Recommended Backend Surface

Create a workspace-aware inbox route instead of a mailbox-specific one.

Recommended route file:

- `backend/app/routes/email_ops.py`

Recommended API shape:

- `GET /api/email/threads?workspace_key=agc&lane=consulting_opportunity`
- `GET /api/email/threads/{thread_id}`
- `POST /api/email/sync`
- `POST /api/email/threads/{thread_id}/classify`
- `POST /api/email/threads/{thread_id}/draft`
- `POST /api/email/threads/{thread_id}/approve`
- `POST /api/email/threads/{thread_id}/send`
- `POST /api/email/threads/{thread_id}/escalate`
- `POST /api/email/threads/{thread_id}/link-opportunity`

## Data Model

Use database tables for live operations.
Do not try to run the operational inbox from markdown or CSV alone.

Recommended core tables:

### `email_threads`

- `id`
- `provider`
- `provider_thread_id`
- `workspace_key`
- `lane`
- `status`
- `subject`
- `from_address`
- `from_name`
- `organization`
- `priority`
- `confidence_score`
- `needs_human`
- `linked_opportunity_id`
- `last_message_at`
- `last_synced_at`
- `created_at`
- `updated_at`

### `email_messages`

- `id`
- `thread_id`
- `provider_message_id`
- `direction`
- `from_address`
- `to_addresses`
- `cc_addresses`
- `subject`
- `body_text`
- `body_html`
- `attachments_meta`
- `received_at`
- `created_at`

### `email_actions`

- `id`
- `thread_id`
- `action_type`
- `actor`
- `notes`
- `draft_body`
- `sent_message_id`
- `created_at`

### `email_classifications`

- `id`
- `thread_id`
- `workspace_key`
- `lane`
- `buyer_type`
- `risk_flags`
- `qualification_status`
- `recommended_next_action`
- `model_name`
- `created_at`

When a thread becomes real traction, write through to:

- `analytics/inbound_email_log.csv`
- `analytics/opportunity_ledger.csv`

## Provider Recommendation

Use the provider AGC already runs on, not a new mailbox product, unless the current mailbox is blocking automation.

### If AGC uses Google Workspace / Gmail

Use the Gmail API for message access and sending.
For near-real-time mailbox updates, Gmail supports push notifications through Cloud Pub/Sub.

### If AGC uses Microsoft 365 / Outlook

Use Microsoft Graph for message access and sending.
For near-real-time updates, use Graph change-notification subscriptions.

### If mailbox control is limited and you want simpler inbound processing

Use an inbound-processing provider that can forward inbound mail to a webhook payload, then let the backend handle routing and draft generation.

This is the fallback, not the first recommendation.

## Classification Logic

Do not rely on pure LLM classification.
Use a hybrid model:

1. hard rules
   - sender domain
   - known contacts
   - keywords like `quote`, `bid`, `proposal`, `invoice`, `vendor`, `insurance`, `W-9`
2. model classification
   - lane
   - urgency
   - qualification status
   - response posture
3. human override
   - operator can re-route and reclassify any thread

## Response Logic

Each draft should be one of five response types:

1. `acknowledge`
   We received this and are reviewing it.
2. `qualify`
   Ask clarifying questions before committing.
3. `schedule`
   Move the conversation into a meeting or call.
4. `decline_or_redirect`
   Not a fit, or needs a different lane.
5. `escalate`
   Human review required before any response.

For AGC, the default should be `qualify` rather than `promise`.

## PM Card Integration

Create PM cards only when a thread requires human action.

Recommended PM card triggers:

- `high_value buyer email`
- `scope/pricing decision required`
- `portal or registration task required`
- `supplier relationship follow-up required`
- `compliance or certification question raised`

Do not create PM cards for every email.
The inbox should stay operationally useful, not become another noisy board.

## Recommended Build Phases

### Phase 1: Organize First

Outcome:
AGC can see all inbound threads in one place and route them into lanes.

Build:

- provider sync job
- thread/message persistence
- lane classifier
- frontend lane board
- manual re-route
- no auto-send yet

### Phase 2: Draft Assist

Outcome:
AGC can review suggested replies and move faster without losing control.

Build:

- thread summarization
- suggested response generation
- human approve/edit/send flow
- escalation queue
- PM card creation for high-risk threads

### Phase 3: Controlled Automation

Outcome:
The system auto-sends only narrow, low-risk reply types.

Build:

- confidence thresholds
- allowlisted auto-response types
- audit trail for every send
- auto-log of qualified traction events

### Phase 4: Organization-Wide Routing

Outcome:
The same system can route into additional workspaces beyond AGC.

Build:

- workspace router
- reusable lane maps per workspace
- shared inbox analytics across the portfolio

## First Implementation Order

1. Build the backend `email_threads` and `email_messages` layer.
2. Add a single provider sync path for the live AGC mailbox.
3. Create the AGC inbox page in the frontend.
4. Add lane classification and manual overrides.
5. Add draft generation with human approval.
6. Add PM-card escalation for risky threads.
7. Only then allow limited auto-send for acknowledgements and scheduling.

## Current Decisions Locked For AGC

- AGC is `hybrid`, but the next `12 months` are `consulting-led`
- lead problem is `operational clarity`
- secondary problem is `workflow modernization`
- `Johnnie` is the primary outreach face
- qualified inbound email remains the first traction signal

That means the first live lane should optimize for:

- university and institutional buyer conversations
- consulting-fit inbound threads
- qualification before capability claims

## Open Questions Before Build

1. Which mailbox provider is AGC currently using for the live domain?
2. Which exact addresses should enter this system first?
3. Should AGC start with one shared inbox or separate inboxes by function?
4. Who besides Johnnie needs review access?
5. What reply types are safe enough for later auto-send?
6. What SLA matters most: `same day`, `24h`, or `48h`?
7. Which emails should bypass the system entirely?

## Recommended Immediate Next Move

Start with `Phase 1` and one mailbox only.

The fastest credible build is:

- one shared AGC mailbox
- six AGC lanes
- no auto-send
- human review for every outbound draft
- PM card escalation only for high-value or high-risk threads

That gets AGC organized immediately without creating reputational risk.
