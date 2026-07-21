from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


POLICY_ALLOWED = "allowed_in_production"
POLICY_TEMPORARY = "temporary_scaffold"
POLICY_FAILURE = "treat_as_failure"

POLICY_CLASSES = (POLICY_ALLOWED, POLICY_TEMPORARY, POLICY_FAILURE)

_FALLBACK_POLICIES: tuple[dict[str, Any], ...] = (
    {
        "fallback_id": "content_generation_provider_failover",
        "label": "Content generation provider failover",
        "owner": "content_pipeline",
        "policy_class": POLICY_ALLOWED,
        "system": "content_generation",
        "trigger": "Primary provider errors with a fallback-worthy transport or model failure.",
        "behavior": "Route generation work from the primary provider to the next configured provider.",
        "intended_exit": "Remain active as an explicit resilience policy unless production moves to strict single-provider execution.",
        "source_refs": [
            "backend/app/routes/content_generation.py",
        ],
        "notes": "Current local order is non-production and can prefer Ollama before OpenAI.",
    },
    {
        "fallback_id": "content_signal_safe_lessons_to_reservoir",
        "label": "Content-safe lessons to reservoir fallback",
        "owner": "content_pipeline",
        "policy_class": POLICY_TEMPORARY,
        "system": "content_generation",
        "trigger": "Selected-source or recent-signals retrieval cannot produce usable content-safe operator lessons.",
        "behavior": "Fall back from `content_safe_operator_lessons` to raw `content_reservoir` retrieval.",
        "intended_exit": "Reduce or remove once the content-safe lesson lane is reliably populated and sufficient for draft generation.",
        "source_refs": [
            "backend/app/services/content_generation_context_service.py",
            "backend/app/services/content_safe_operator_lesson_service.py",
        ],
        "notes": "This is the key remaining trust-boundary compromise in the active drafting pipeline.",
    },
    {
        "fallback_id": "content_snapshot_runtime_rebuild",
        "label": "Content snapshot runtime rebuild",
        "owner": "content_pipeline",
        "policy_class": POLICY_TEMPORARY,
        "system": "content_generation",
        "trigger": "Persisted snapshot artifacts are missing, stale, or insufficient for request-time context assembly.",
        "behavior": "Allow runtime rebuild or alternate snapshot loading instead of failing immediately.",
        "intended_exit": "Keep only if snapshot freshness cannot be made reliable enough for strict persisted-only reads.",
        "source_refs": [
            "backend/app/services/content_generation_context_service.py",
        ],
        "notes": "Useful for continuity, but it weakens exact reproducibility.",
    },
    {
        "fallback_id": "content_retrieval_support_reinsertion",
        "label": "Content retrieval support reinsertion",
        "owner": "content_pipeline",
        "policy_class": POLICY_TEMPORARY,
        "system": "content_generation",
        "trigger": "Domain filtering removes all retrieved support chunks needed to keep a prompt grounded.",
        "behavior": "Reinsert a limited number of retrieved proof/story chunks after filtering.",
        "intended_exit": "Remove once retrieval and filtering can preserve grounded support without post-filter rescue.",
        "source_refs": [
            "backend/app/services/content_generation_context_service.py",
        ],
        "notes": "Behaviorally meaningful fallback, not just a compatibility alias.",
    },
    {
        "fallback_id": "email_ops_sample_threads",
        "label": "Email ops sample-thread fallback",
        "owner": "email_ops",
        "policy_class": POLICY_TEMPORARY,
        "system": "email_ops",
        "trigger": "Gmail is not connected or inbox sync cannot access live threads.",
        "behavior": "Serve seeded sample threads so the inbox surface remains explorable.",
        "intended_exit": "Keep out of production workflows that claim live inbox truth; remove once Gmail auth is fully mandatory for the live surface.",
        "source_refs": [
            "backend/app/services/email_ops_service.py",
            "workspaces/shared-ops/docs/gmail_inbox_connection_runbook.md",
        ],
        "notes": "Useful for demo/dev, but it must remain clearly labeled as non-live data.",
    },
    {
        "fallback_id": "prospects_firestore_local_storage",
        "label": "Prospects Firestore/local storage fallback",
        "owner": "prospects",
        "policy_class": POLICY_ALLOWED,
        "system": "prospects",
        "trigger": "Firestore or canonical remote persistence is unavailable for a prospects/manual workflow.",
        "behavior": "Allow local/manual storage paths to keep prospect work moving.",
        "intended_exit": "Remain active if manual/local capture is part of the intended operator workflow.",
        "source_refs": [
            "backend/app/routes/prospects.py",
            "backend/app/routes/prospects_manual.py",
        ],
        "notes": "This is tolerated because the workflow itself explicitly includes manual intake paths.",
    },
    {
        "fallback_id": "workspace_registry_frontend_mirror",
        "label": "Workspace registry frontend mirror",
        "owner": "workspace_runtime",
        "policy_class": POLICY_ALLOWED,
        "system": "workspace_registry",
        "trigger": "Frontend needs workspace metadata before or without a live backend registry response.",
        "behavior": "Use the static frontend registry mirror instead of blocking the UI.",
        "intended_exit": "Remain active as a deliberate frontend resilience layer unless the app becomes strictly server-truth-only.",
        "source_refs": [
            "backend/app/services/workspace_registry_service.py",
            "frontend/lib/workspace-registry.ts",
        ],
        "notes": "Machine-readable and already part of the platform contract.",
    },
)


def build_fallback_policy_report(*, include_entries: bool = True) -> dict[str, Any]:
    entries = [dict(policy) for policy in _FALLBACK_POLICIES]
    class_counts = {policy_class: sum(1 for item in entries if item["policy_class"] == policy_class) for policy_class in POLICY_CLASSES}
    payload: dict[str, Any] = {
        "schema_version": "fallback_policy_report/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_policies": len(entries),
            "policy_class_counts": class_counts,
            "allowed_in_production_count": class_counts[POLICY_ALLOWED],
            "temporary_scaffold_count": class_counts[POLICY_TEMPORARY],
            "treat_as_failure_count": class_counts[POLICY_FAILURE],
        },
    }
    if include_entries:
        payload["policies"] = entries
    return payload
