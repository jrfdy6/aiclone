# Portfolio Inbox Routing Spec

## Purpose

Define one shared inbox pattern for the portfolio, then route inbound email into the correct workspace and lane without forcing a separate mailbox per workspace.

This spec is the source of truth for:

- the Gmail setup
- the first-pass routing rules
- the app-level workspace router
- AGC-specific email routing into the `agc` workspace

## Current Decision

Use one mailbox first.

Recommended model:

- one shared intake inbox
- Gmail labels for immediate visibility
- Gmail filters for obvious rules
- app-level routing as the real source of truth
- human review for risky threads

Do not make Gmail labels the system of record.
Use them as a staging aid only.

## Canonical Mailbox Pattern

Use one canonical inbox:

- `<portfolio_inbox>@gmail.com`

Use plus-address variants when you control the address being published:

- `<portfolio_inbox>+agc@gmail.com`
- `<portfolio_inbox>+agc-universities@gmail.com`
- `<portfolio_inbox>+agc-vendors@gmail.com`
- `<portfolio_inbox>+fusion@gmail.com`
- `<portfolio_inbox>+feezie@gmail.com`
- `<portfolio_inbox>+easyoutfit@gmail.com`
- `<portfolio_inbox>+swag@gmail.com`
- `<portfolio_inbox>+ops@gmail.com`

Notes:

- All of these aliases route into the same Gmail inbox.
- Use the base inbox when a form rejects `+` aliases.
- When the base inbox is used, rely on app-level routing rather than Gmail-only routing.

## Published Alias Matrix

Use these addresses by default:

### AGC

- `+agc` for general AGC contact
- `+agc-universities` for university and institutional outreach
- `+agc-vendors` for suppliers, distributors, and vendor onboarding

### Fusion OS

- `+fusion` for families, schools, referrals, admissions-adjacent communication, and placement support

### FEEZIE / LinkedIn OS

- `+feezie` for content, speaking, brand, creator, collaboration, and visibility opportunities

### Easy Outfit App

- `+easyoutfit` for beta users, support, partnerships, and product feedback

### AI Swag Store

- `+swag` for merch, wholesale, print, and order communication

### Shared Ops

- `+ops` for system admin, operations, infrastructure, billing, or ambiguous portfolio-level communication

## Gmail Label Taxonomy

Create these labels in Gmail:

- `workspace/agc`
- `workspace/fusion-os`
- `workspace/feezie-os`
- `workspace/easyoutfitapp`
- `workspace/ai-swag-store`
- `workspace/shared-ops`
- `workspace/manual-review`
- `state/needs-human`
- `state/high-value`
- `state/high-risk`
- `state/sla-today`
- `state/awaiting-reply`
- `lane/agc-consulting`
- `lane/agc-product-sourcing`
- `lane/agc-supplier-partner`
- `lane/agc-registrations-compliance`
- `lane/agc-finance-admin`
- `lane/noise-archive`

## Gmail Filter Starter Set

These filters are for immediate organization before the app is live.

### Alias-based filters

- `to:(<portfolio_inbox>+agc@gmail.com OR <portfolio_inbox>+agc-universities@gmail.com OR <portfolio_inbox>+agc-vendors@gmail.com)`
  Action:
  apply `workspace/agc`

- `to:(<portfolio_inbox>+fusion@gmail.com)`
  Action:
  apply `workspace/fusion-os`

- `to:(<portfolio_inbox>+feezie@gmail.com)`
  Action:
  apply `workspace/feezie-os`

- `to:(<portfolio_inbox>+easyoutfit@gmail.com)`
  Action:
  apply `workspace/easyoutfitapp`

- `to:(<portfolio_inbox>+swag@gmail.com)`
  Action:
  apply `workspace/ai-swag-store`

- `to:(<portfolio_inbox>+ops@gmail.com)`
  Action:
  apply `workspace/shared-ops`

### Risk and priority filters

- `subject:(RFP OR RFQ OR proposal OR quote OR pricing OR contract OR SOW OR "statement of work")`
  Action:
  apply `state/high-value`

- `subject:(invoice OR payment OR remit OR overdue OR past due)`
  Action:
  apply `state/sla-today`

- `from:(noreply OR no-reply OR notifications OR updates)`
  Action:
  review manually before creating aggressive auto-archive rules

Important:

- Gmail filters only affect new matching messages.
- Replies only get filtered if the reply itself still matches the filter criteria.

## Workspace Routing Precedence

The app-level router should use this order:

1. direct alias hit
2. known sender match
3. known domain match
4. keyword score
5. thread history
6. manual review

If two workspaces score closely, route to `shared_ops` review instead of forcing certainty.

## Workspace Router Rules

### Route To `agc`

Use `agc` when the thread is about:

- consulting for operational clarity
- workflow modernization
- process optimization
- procurement
- supplier onboarding
- vendor registration
- university purchasing
- product sourcing
- quotes, capability statements, or bid-adjacent requests
- teaming, subcontracting, or prime-partner discussion

### Route To `fusion-os`

Use `fusion-os` when the thread is about:

- students
- families
- admissions
- enrollment
- school placement
- school counseling
- referral support
- educational fit or therapeutic placement

### Route To `feezie-os`

Use `feezie-os` when the thread is about:

- content
- LinkedIn
- podcasts
- creator partnerships
- visibility
- interviews
- speaking
- personal brand

### Route To `easyoutfitapp`

Use `easyoutfitapp` when the thread is about:

- app feedback
- beta access
- wardrobe product feedback
- subscriptions
- bugs
- mobile app partnerships

### Route To `ai-swag-store`

Use `ai-swag-store` when the thread is about:

- merch
- swag
- apparel
- bulk product orders
- print and fulfillment

### Route To `shared_ops`

Use `shared_ops` when the thread is about:

- billing for shared infrastructure
- domain, hosting, or tool administration
- cross-workspace requests
- unclear routing
- system incidents
- ambiguous portfolio-wide business development

## AGC Routing Profile

Inside the `agc` workspace, use a second routing pass.

### AGC Lane Map

- `consulting_opportunity`
- `product_sourcing`
- `supplier_partner`
- `registrations_compliance`
- `finance_admin`
- `noise_archive`

### AGC Lane Rules

#### `consulting_opportunity`

Use when the message references:

- operational clarity
- workflow modernization
- process optimization
- discovery
- implementation support
- audit
- assessment
- program management
- project management
- higher-education operations
- institutional operations

#### `product_sourcing`

Use when the message references:

- product request
- catalog
- quote
- pricing
- laboratory products
- scientific products
- medical products
- packaging
- equipment sourcing
- availability
- lead time
- purchase order

#### `supplier_partner`

Use when the message references:

- manufacturer
- distributor
- reseller
- dealer
- supplier application
- teaming
- subcontracting
- prime partnership
- referral or channel partnership

#### `registrations_compliance`

Use when the message references:

- vendor portal
- onboarding package
- W-9
- insurance
- UEI
- CAGE
- SAM
- capability statement
- certifications
- registration documents
- tax forms

#### `finance_admin`

Use when the message references:

- invoice
- remittance
- payment status
- calendar coordination
- administrative follow-up

#### `noise_archive`

Use when the message is:

- irrelevant
- clearly spam
- generic mass outreach
- duplicate notice
- low-signal newsletter

## AGC Positive Signals

Increase `agc` routing confidence when any of these appear:

- `procurement`
- `purchasing`
- `vendor`
- `supplier`
- `quote`
- `pricing`
- `rfq`
- `rfp`
- `proposal`
- `scope of work`
- `statement of work`
- `capability statement`
- `W-9`
- `COI`
- `insurance certificate`
- `registration`
- `reseller`
- `scientific`
- `laboratory`
- `medical supplies`
- `medical equipment`
- `higher education`
- `university`
- `institutional buyer`
- `teaming`
- `subcontracting`
- `prime`
- `operational clarity`
- `workflow modernization`
- `process optimization`

## AGC Negative Signals

Decrease `agc` confidence when these dominate instead:

- `admissions`
- `student`
- `family`
- `placement`
- `therapeutic`
- `enrollment`
- `creator`
- `podcast`
- `audience`
- `beta tester`
- `app bug`
- `merch drop`

## AGC Domain Watchlist

Known or likely AGC-relevant domains should raise confidence, but not override clear contrary context.

### Universities and institutions

- `american.edu`
- `gwu.edu`
- `georgetown.edu`
- `gallaudet.edu`
- `udc.edu`
- `montgomerycollege.edu`
- `umd.edu`
- `umbc.edu`
- `pgcc.edu`
- `howard.edu`

### Supplier and manufacturer paths

- `vwr.com`
- `avantorsciences.com`
- `quantabio.com`
- `fishersci.com`
- `thermofisher.com`
- `uline.com`

### Prime and partner watchlist

- `gdit.com`
- `saic.com`
- `leidos.com`
- `bah.com`
- `accenture.com`

## Workspace Routing Confidence Rules

Use these thresholds:

- `0.90+`
  auto-route to workspace and lane
- `0.70-0.89`
  route to workspace, but mark `needs_human`
- `<0.70`
  route to `workspace/manual-review`

Always force `needs_human` when:

- pricing is requested
- legal/compliance claims are involved
- buyer asks for proof AGC may not have
- an RFP, RFQ, or formal procurement document is attached
- the sender appears high-value

## Thread Status Contract

Use this shared state model:

`new -> triaged -> routed -> drafted -> human_review -> sent -> waiting -> closed`

Flags:

- `high_value`
- `high_risk`
- `needs_human`
- `sla_at_risk`
- `linked_opportunity`

## Frontend Route Structure

Build one shared inbox surface first.

Recommended routes:

- `frontend/app/inbox/page.tsx`
- `frontend/app/inbox/[threadId]/page.tsx`

### `frontend/app/inbox/page.tsx`

Primary sections:

1. `Portfolio Summary`
   Counts by workspace, unread, SLA risk, and needs-human.
2. `Workspace Buckets`
   One card per workspace:
   - AGC
   - Fusion OS
   - FEEZIE OS
   - Easy Outfit App
   - AI Swag Store
   - Shared Ops
   - Manual Review
3. `Needs Human`
   Highest-priority review queue.
4. `AGC Lane Board`
   AGC-specific lane counts:
   - consulting
   - product sourcing
   - supplier/partner
   - registrations/compliance
   - finance/admin
5. `Recent Thread Queue`
   Time-ordered queue with status pills and confidence.

### `frontend/app/inbox/[threadId]/page.tsx`

Primary sections:

1. `Thread Header`
   Subject, sender, organization, workspace, lane, confidence.
2. `Thread History`
   Full message timeline.
3. `Routing Panel`
   Workspace and lane override controls.
4. `Qualification Panel`
   AGC fit, buyer type, opportunity link, next action.
5. `Draft Panel`
   suggested reply, human edit, approve, reject, escalate.
6. `Audit Panel`
   classification history, who overrode what, send log.

## Backend Contract

Recommended route family:

- `GET /api/email/threads`
- `GET /api/email/threads/{thread_id}`
- `POST /api/email/sync`
- `POST /api/email/threads/{thread_id}/route`
- `POST /api/email/threads/{thread_id}/draft`
- `POST /api/email/threads/{thread_id}/approve`
- `POST /api/email/threads/{thread_id}/send`
- `POST /api/email/threads/{thread_id}/escalate`

## Gmail Versus App Responsibilities

### Gmail should do

- basic labels
- basic filters
- quick visibility
- immediate manual triage support

### The app should do

- real workspace routing
- confidence scoring
- thread history memory
- lane classification
- opportunity linking
- PM-card escalation
- draft generation and approval

## Immediate Setup Checklist

1. Create the shared Gmail inbox.
2. Decide the canonical username for the portfolio inbox.
3. Create the plus aliases listed above.
4. Create the Gmail labels in this spec.
5. Add the alias-based Gmail filters first.
6. Add only a few high-signal keyword filters.
7. Publish `+agc`, `+agc-universities`, and `+agc-vendors` first.
8. Build the frontend shared inbox against this routing contract.

## AGC Immediate Rules

Until the app is live, use this manual fallback:

- if the message came to an `+agc*` alias, label `workspace/agc`
- if it references procurement, vendor onboarding, quoting, university purchasing, capability statements, or workflow/operations consulting, label `workspace/agc`
- if it is ambiguous between AGC and another lane, label `workspace/manual-review`
- do not auto-send capability-heavy replies without human review

## Source Links

- Gmail filters: https://support.google.com/mail/answer/6579
- Gmail aliases / plus addressing: https://support.google.com/mail/answer/22370
