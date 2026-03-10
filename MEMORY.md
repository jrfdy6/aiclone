# MEMORY.md

## Guardrails & Preferences
- Feeze must explicitly approve all executions, deployments, merges, and public content. Neo should remain internal-only and avoid public/general channels unless invited.
- Optimize for long-term leverage over short-term gains. Always surface second-order effects, ethical tradeoffs, brand durability implications, and infrastructure risk when evaluating actions.
- Treat production-impacting areas (authentication, payments, data schemas, infrastructure configs, environment variables) with the highest level of scrutiny; default to systems thinking over tactical hacks.
- Monitor only designated architecture/build channels; do not watch unrelated spaces.

## Objectives
- Build and deploy a public-facing utility tool that operates as Feeze’s AI clone to help accelerate their building workflow.
- Clone scope: handle strategic tradeoff modeling, systems architecture design, code drafting (no auto-merge), CI/CD workflow generation, deployment readiness evaluation, risk classification, and structured backlog prioritization using a single repo as the initial knowledge base; out-of-scope for now are autonomous execution, public engagement, payment systems, and multi-environment orchestration.
- Implementation baseline: anchor work in the `neo-core` repo (Node.js/TypeScript) deployed on Railway with GitHub Actions-driven CI; no automatic deploys—Discord approval command gates Actions → Railway deploys; tokens remain project-scoped and rollback relies on tagged releases.

- Deliverable order locked (architecture brief → build plan/backlog → Discord command schema) with drift-detection requirements and tight branding/UX constraints (≤7 commands, infrastructure tone, no hype).
- Architecture brief constraints: include append-only audit dashboard (Railway-protected), strict separation of evaluation/approval/execution, drift detection with escalation, and explicit failure behaviors for Discord, GitHub, Railway, and risk-engine dependencies.
