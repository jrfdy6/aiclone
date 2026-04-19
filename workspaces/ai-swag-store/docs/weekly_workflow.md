# AI Swag Store Weekly Workflow

This file defines the weekly layer on top of the continuous machine loop.
The lane is expected to work every day, often multiple times per day.

## Intra-Day Rhythm

- Every `5 minutes`: execution polling decides whether a queued packet should move
- Every `30 minutes`: internal sync updates `Signal`, `Work Produced`, `Traction`, `Opportunities`, and `Next Focus`
- End of day: write a short rollup when meaningful learning, traffic movement, or blocker changes occurred

## Daily Priorities

- Keep one clear offer or store hypothesis active
- Keep the next traffic or landing-page move explicit
- Record whether visits changed in a way that affects the next offer decision
- Capture blockers before they silently stall the lane

## Rolling Weekly Expectations

- Maintain at least one active offer or store-improvement hypothesis
- Keep one explicit next catalog decision visible
- End the week with a plain-language summary of what visits taught the workspace
- Make the next test obvious enough that Jean-Claude can open the next SOP cleanly

## Social Rule

Social activity can support the store, but it should stay secondary until the operating rhythm produces clean learning on its own.
