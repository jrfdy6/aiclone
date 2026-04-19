# AGC Opportunity Qualification Framework

This framework decides whether a signal belongs in `monitor`, deserves shaping work, or is strong enough for active capture.

## Scoring Model

Score each category from `0` to `3`.

### 1. Buyer Clarity
- `0`: no clear buyer
- `1`: buyer category is vague
- `2`: buyer type is clear but contact path is weak
- `3`: buyer type and likely contact path are both clear

### 2. Government Relevance
- `0`: not government-related
- `1`: loosely adjacent only
- `2`: credible prime, partner, or adjacent public-sector path
- `3`: direct agency or public-sector buying path

### 3. Problem Urgency
- `0`: no current pain or timeline
- `1`: hypothetical or generic interest
- `2`: active need is visible
- `3`: current timeline, pressure, or response need is explicit

### 4. Proof Fit
- `0`: AGC has no honest basis to speak credibly
- `1`: only broad point of view
- `2`: adjacent process or operator proof exists
- `3`: strong proof exists for the exact problem shape

### 5. Access Path
- `0`: no route to a real conversation
- `1`: indirect or speculative route only
- `2`: one credible route exists
- `3`: live contact, warm path, or inbound thread exists

### 6. Near-Term Motion
- `0`: nothing actionable this cycle
- `1`: research only
- `2`: one clear next move exists
- `3`: multiple concrete next moves are visible now

## Score Interpretation

- `0-5`: archive or ignore
- `6-8`: monitor
- `9-12`: shape positioning or capability around it
- `13-15`: qualify actively
- `16-18`: treat as active capture

Score alone does not override the guardrails.
If the proof boundary is dishonest, the opportunity is blocked even with a high score.

## Stage Model

Use one of these stages in `analytics/opportunity_ledger.csv`:

- `seed`
- `captured`
- `monitor`
- `shape`
- `qualified`
- `conversation`
- `capture_active`
- `parked`
- `closed`

## Required Ledger Fields

Every row should keep:

- `opportunity_id`
- `signal_date`
- `signal_source`
- `buyer_type`
- `agency_or_partner`
- `problem_shape`
- `offer_theme`
- `qualification_score`
- `stage`
- `next_move`
- `owner`
- `evidence_path`
- `last_updated`

## Red Flags

Do not advance the stage when:

- the buyer is still imaginary
- the problem is generic but not urgent
- the offer requires invented proof
- the only path forward is “post more content and hope”
- the opportunity would force AGC into unsupported compliance or delivery claims

## Good Next Moves

Prefer next moves like:

- clarify the buyer and route
- sharpen the capability language around one problem
- answer a concrete inbound email
- prepare a short capability note or response draft
- record the blocker and park the opportunity cleanly
