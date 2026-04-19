---
title: "Shipping Protocol"
persona_id: "johnnie_fields"
target_file: "history/shipping_protocol.md"
---

# Shipping Protocol

Reusable operating protocol for how Johnnie ships work on AI systems without losing track of what is fixed, what is live, and what still needs follow-up.

## Use When
- Talking about how Johnnie actually ships on `main` without branching into confusion.
- Explaining operator discipline, task boundaries, or how to keep AI system work legible.
- Studying the practical lessons that came out of building AI Clone.

## Core Lessons
- Keep one shipping lane. If everything ships from `main`, the structure stays easier to trust.
- Make the task small enough to finish, verify, commit, and push in one clean loop.
- Treat one Codex session as one unit of work.
- Do not confuse runtime memory churn with broken Git hygiene.
- Stage only the files that belong to the task you are actually shipping.
- Close loops aggressively. A task is not done when it feels clearer; it is done when it is verified and pushed or deliberately handed off.

## Start Protocol
1. Start a fresh Codex session for one concrete task.
2. Read the current repo state before editing:
   - `./scripts/worktree_doctor.py`
   - `git status --short`
3. Name the task in plain language before building.

## Build Protocol
1. Stay on `main`, but keep the scope narrow.
2. If the change is too large to ship safely, split it into smaller slices.
3. Keep unfinished work behind an inert path, a dead route, or a not-yet-used code path instead of carrying long-lived divergence.

## Ship Protocol
1. Run the safety gate:
   - `./scripts/verify_main.sh`
2. Review the diff and stage only the intended files.
3. Commit the task as one understandable unit.
4. Push directly to `origin/main`.

## Close Protocol
1. Close the Codex session when the task is pushed, intentionally paused, or cleanly handed off.
2. Open a new session for the next real unit of work instead of letting many unrelated fixes accumulate in one thread.

## Why This Matters
- Johnnie works best when the system of record stays trustworthy.
- This protocol reduces hidden drift between what feels fixed locally and what is actually live.
- It turns shipping into a repeatable operator habit instead of a memory exercise.
