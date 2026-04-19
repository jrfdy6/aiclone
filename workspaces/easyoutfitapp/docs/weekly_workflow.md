# Easy Outfit App Weekly Workflow

This file defines the weekly layer on top of the continuous machine loop.
The lane is expected to work every day, often multiple times per day.

## Intra-Day Rhythm

- Every `5 minutes`: execution polling decides whether a queued packet should move
- Every `30 minutes`: internal sync updates `Signal`, `Work Produced`, `Traction`, `Opportunities`, and `Next Focus`
- End of day: write a short rollup when meaningful product, traffic, or blocker changes occurred

## Daily Priorities

- Keep the lane in explicit `restore mode` or `grow mode`
- Keep the next recommendation-quality or product-health move visible
- Record whether visits or product use changed in a meaningful way
- Capture blockers before they silently stall the lane

## Rolling Weekly Expectations

- Maintain one clear product-health or recommendation-quality focus
- Keep the next trustworthy user-facing improvement obvious
- End the week with a plain-language summary of what product signal changed
- Make the next move explicit enough that Jean-Claude can open the next SOP cleanly

## Social Rule

Social activity can support growth, but it should stay secondary until the operating rhythm is stable and the product is reliably usable.
