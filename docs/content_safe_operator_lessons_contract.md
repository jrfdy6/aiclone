# Content-Safe Operator Lessons Contract

This lane exists so public content can learn from the build story without exposing internal workflow detail.

## 1. Why This Exists

`operator_story_signals` is the right bridge out of raw OpenClaw memory, but it is still an internal lane.

It can still contain:

- workspace names
- file paths
- internal agent names
- playbook and handoff terminology
- execution mechanics that should stay private

That means it should not flow directly into content prompts.

## 2. Design Rule

Public content should use the lesson, not the plumbing.

The path becomes:

`raw memory -> operator_story_signals -> content_safe_operator_lessons -> future content use`

## 3. Output Shape

Each content-safe lesson includes:

- `macro_thesis`
- `public_takeaway`
- `public_proof`
- `safe_angle`
- `topic_tags`
- `visibility = public_safe`
- `workspace_scope`
- `source_signal_id`

This keeps the useful pattern while stripping sensitive system detail.

## 4. Redaction Rules

The distiller should remove or generalize:

- file paths
- workspace slugs
- internal agent names
- PM / SOP / work-order language
- exact implementation details that would reveal internal architecture unnecessarily

The result should stay:

- true
- useful
- macro
- non-sensitive

## 5. Reports

The local worker writes:

- `memory/reports/content_safe_operator_lessons_latest.json`
- `memory/reports/content_safe_operator_lessons_latest.md`

## 6. Backend Sync

The sync contract is:

- `POST /api/brain/content-safe-operator-lessons/sync`

The persisted snapshot type is:

- `content_safe_operator_lessons`

## 7. Boundary

This lane is not final post copy.

It is a public-safe lesson surface for future content use.
The final content system can still:

- choose whether to use a lesson
- combine it with persona and source context
- decide how much of the macro lesson belongs in a specific post
