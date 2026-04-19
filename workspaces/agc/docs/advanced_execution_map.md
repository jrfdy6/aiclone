# AGC Advanced Execution Map

AGC can do more advanced work now, but only if the work stays traceable to the core loop:

`Signal -> Positioning -> Capability -> Surface -> Inbound Email -> Qualified Conversation -> Capture`

Advanced does not mean broader claims.
It means tighter structure, clearer handoffs, and stronger evidence.

## Sub-Lanes

### 1. Signal Scout

Purpose:
- find agency, prime, partner, and adjacent buyer signal that is worth recording

Typical inputs:
- procurement notices
- partner introductions
- website/contact activity
- buyer or prime conversation fragments

Required outputs:
- add or update a row in `analytics/opportunity_ledger.csv`
- note the signal meaning in a briefing, standup, or execution log when it changes direction

### 2. Qualification and Capture Strategy

Purpose:
- decide whether a signal is weak noise, worth monitoring, or strong enough for active capture motion

Typical inputs:
- scored opportunity rows
- buyer type
- proof fit
- access path

Required outputs:
- qualification score
- current stage
- next move
- blocker or disqualifier when motion should stop

### 3. Capability Evidence Builder

Purpose:
- turn qualified demand into a capability surface that AGC can defend

Typical inputs:
- positioning thesis
- opportunity pattern
- proof the lane can honestly cite

Required outputs:
- proof-bounded capability notes
- response snippets
- buyer-facing language that stays inside the evidence model

### 4. Conversation Operator

Purpose:
- handle inbound email and next-step replies without losing qualification context

Typical inputs:
- inbound email
- current opportunity stage
- requested next step

Required outputs:
- row in `analytics/inbound_email_log.csv`
- linked opportunity update
- response draft or qualification note

## Artifact Contract

Every advanced move should leave a local artifact:

- new signal: `analytics/opportunity_ledger.csv`
- qualified inbound email: `analytics/inbound_email_log.csv`
- operating shift: `briefings/*.md`
- durable milestone: `memory/execution_log.md`
- periodic interpretation: `standups/*.md`

If no artifact changed, the work probably was not advanced enough to matter.

## Active Stage Limits

- Keep one primary positioning thread live at a time.
- Keep no more than three active opportunities above `monitor`.
- Do not move an opportunity into active capture work without a named next move and explicit proof boundary.

## Guardrails

- No invented certifications, contracts, security clearances, or past performance.
- No legal or compliance advice framed as settled fact.
- No broad consulting expansion just because a signal sounds interesting.
- No cross-workspace routing inside AGC artifacts.

## Escalation

Escalate when:
- a signal requires legal or compliance interpretation
- the buyer asks for proof AGC does not have
- the next move depends on claims outside the evidence model
- multiple opportunities compete for the same positioning thread
