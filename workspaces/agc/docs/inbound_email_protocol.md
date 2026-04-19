# AGC Inbound Email Protocol

Qualified inbound email is AGC's first traction signal.
Do not count every email as traction.

## A Message Counts As Qualified Traction Only When

- it comes from a prospective buyer, credible prime, or credible partner
- it references a real need, program, capability question, or next step
- it creates a plausible path to a live conversation
- it fits AGC's government-contracting-first AI consulting posture

If one of those is missing, log it as signal or noise instead of traction.

## Intake Steps

1. Add the email to `analytics/inbound_email_log.csv`.
2. Link it to an existing `opportunity_id` or create a new row in `analytics/opportunity_ledger.csv`.
3. Mark the qualification status:
   - `noise`
   - `signal_only`
   - `needs_followup`
   - `qualified`
4. Record the next move and response deadline.
5. Update the next standup if the email changed `Traction`, `Opportunities`, or `Next Focus`.

## Response Posture

- lead with clarity, not hype
- answer the stated need before broadening the conversation
- offer a bounded next step
- qualify by asking for context, constraints, timeline, or decision path
- avoid claims that exceed the evidence model

## Good Response Shapes

- clarify the use case
- suggest a short call
- offer a concise capability note
- confirm whether AGC is speaking to the right buyer or partner

## Bad Response Shapes

- generic sales language
- promise-heavy capability claims
- pretending AGC has contract vehicles, certifications, or past performance it does not have
- long strategy dumps before buyer context is clear

## Escalate When

- the email requests legal, security, or compliance commitments
- the buyer asks for proof AGC cannot honestly provide
- the next step would commit AGC to delivery scope that has not been qualified
