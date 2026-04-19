# Easy Outfit App Operating Model

## Definition

Easy Outfit App is a closet-first AI styling and product-restoration system.
It exists to reduce daily decision fatigue, not to pressure users into buying more clothes.

## Primary User Problem

- Help users decide what to wear from their existing wardrobe with context-aware recommendations they can trust

## Core Loop

1. Wardrobe Signal
   Capture what the user, product, or visit data is revealing.
2. Context
   Make weather, occasion, and wardrobe reality explicit.
3. Recommendation
   Produce or improve the suggestion logic.
4. Visit or Use
   Watch whether people arrive and whether the product experience is usable.
5. Feedback
   Capture what worked, what failed, and what felt untrustworthy.
6. Improve
   Tighten the product, restore the broken piece, or clarify the next growth move.

## Inputs

- Website visits
- Product and session behavior
- User feedback
- Wardrobe metadata
- Occasion and weather context
- Recommendation misses

## Outputs

- Product fixes
- Recommendation-quality improvements
- Onboarding and workflow improvements
- Visit and usage learnings
- Standup-ready summaries

## Two Valid Modes

- `Restore mode`: bring the product and local operating environment back into reliable shape
- `Grow mode`: improve recommendation quality, product usage, and traffic once the base is healthy

## Machine Cadence

- `5-minute` execution polling
- `30-minute` internal sync and standup-prep loop
- Daily rollups when the sync loop surfaces meaningful change

## Operating Priorities

- Use `website visits` as the first traction signal
- Keep recommendations closet-first and context-aware
- Treat recommendation integrity as more important than style theater
- Keep the workspace isolated from other workspace memory and execution

## Non-Goals

- Affiliate-biased shopping pressure
- Context-blind outfit recommendations
- Social publishing quotas before the rhythm is stable
- Cross-workspace orchestration
