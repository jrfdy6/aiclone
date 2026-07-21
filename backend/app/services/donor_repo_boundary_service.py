from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.workspace_registry_service import REPO_ROOT


ROOT = REPO_ROOT
DONOR_REPO_PATH = ROOT / "downloads" / "aiclone"
BOUNDARY_DOC_PATH = ROOT / "docs" / "downloads_aiclone_donor_boundary.md"

CLASS_PORT = "worth_porting"
CLASS_REFERENCE = "reference_only"
CLASS_ABANDON = "abandon"
TARGET_CLASSES = (CLASS_PORT, CLASS_REFERENCE, CLASS_ABANDON)

STATE_PENDING = "pending_extraction"
STATE_IMPORTED = "already_imported"
STATE_LEAVE = "leave_in_donor"
STATE_DO_NOT_PORT = "do_not_port"
HANDLING_STATES = (STATE_PENDING, STATE_IMPORTED, STATE_LEAVE, STATE_DO_NOT_PORT)

DECISION_MODE = "targeted_extraction_then_remove_from_active_tree"

_EXTRACTION_TARGETS: tuple[dict[str, Any], ...] = (
    {
        "target_id": "cold_email_copy_patterns",
        "label": "Cold-email copy and prompt patterns",
        "target_class": CLASS_PORT,
        "handling_state": STATE_PENDING,
        "owner": "email_workflow",
        "destination_system": "email_ops+content_generation",
        "donor_source_refs": [
            "downloads/aiclone/backend/app/routes/content_generation.py",
            "downloads/aiclone/frontend/app/content-pipeline/page.tsx",
        ],
        "current_destination_refs": [
            "backend/app/routes/email_ops.py",
            "backend/app/services/email_ops_service.py",
            "frontend/app/inbox/[threadId]/page.tsx",
        ],
        "notes": "Old repo still contains outbound cold-email framing and copy patterns that may inform the new inbox drafting layer.",
    },
    {
        "target_id": "topic_intelligence_outreach_templates",
        "label": "Topic-intelligence outreach templates",
        "target_class": CLASS_PORT,
        "handling_state": STATE_PENDING,
        "owner": "prospecting_intelligence",
        "destination_system": "topic_intelligence+email_ops",
        "donor_source_refs": [
            "downloads/aiclone/backend/app/routes/topic_intelligence.py",
            "downloads/aiclone/backend/app/services/topic_intelligence_service.py",
        ],
        "current_destination_refs": [
            "backend/app/routes/topic_intelligence.py",
            "backend/app/services/topic_intelligence_service.py",
            "backend/app/services/email_ops_service.py",
        ],
        "notes": "The old topic-intelligence lane generated explicit outreach templates that may still be worth reintroducing into the production-safe pipeline.",
    },
    {
        "target_id": "outreach_operator_experience_patterns",
        "label": "Outreach operator experience patterns",
        "target_class": CLASS_PORT,
        "handling_state": STATE_PENDING,
        "owner": "workspace_ui",
        "destination_system": "inbox+workspace",
        "donor_source_refs": [
            "downloads/aiclone/frontend/app/outreach/[prospectId]/page.tsx",
            "downloads/aiclone/frontend/app/content-pipeline/page.tsx",
            "downloads/aiclone/frontend/app/prospecting/page.tsx",
        ],
        "current_destination_refs": [
            "frontend/app/inbox/page.tsx",
            "frontend/app/inbox/[threadId]/page.tsx",
            "frontend/app/workspace/page.tsx",
        ],
        "notes": "The donor repo still shows operator-facing outreach affordances that may be selectively reintroduced without restoring the old product surface.",
    },
    {
        "target_id": "historical_docs_and_knowledge_packs",
        "label": "Historical docs and knowledge packs",
        "target_class": CLASS_REFERENCE,
        "handling_state": STATE_IMPORTED,
        "owner": "knowledge_imports",
        "destination_system": "knowledge/aiclone",
        "donor_source_refs": [
            "downloads/aiclone/notebooklm_ready",
            "downloads/aiclone/README.md",
        ],
        "current_destination_refs": [
            "knowledge/aiclone/README.md",
            "DUPLICATE_INVENTORY.md",
        ],
        "notes": "The durable knowledge value is already being captured under knowledge/aiclone and should stay reference-only.",
    },
    {
        "target_id": "historic_app_docs_for_manual_lookup",
        "label": "Historic app docs for manual lookup",
        "target_class": CLASS_REFERENCE,
        "handling_state": STATE_LEAVE,
        "owner": "archive_reference",
        "destination_system": "manual_reference_only",
        "donor_source_refs": [
            "downloads/aiclone/PHASE_6_*",
            "downloads/aiclone/RAILWAY_*",
        ],
        "current_destination_refs": [
            "DUPLICATE_INVENTORY.md",
        ],
        "notes": "Keep available for occasional comparison, but do not promote back into active system truth unless a specific document is re-adopted intentionally.",
    },
    {
        "target_id": "old_runtime_architecture",
        "label": "Old runtime architecture",
        "target_class": CLASS_ABANDON,
        "handling_state": STATE_DO_NOT_PORT,
        "owner": "platform_architecture",
        "destination_system": "none",
        "donor_source_refs": [
            "downloads/aiclone/backend/app/main.py",
            "downloads/aiclone/frontend/app/dashboard/page.tsx",
        ],
        "current_destination_refs": [
            "backend/app/main.py",
            "frontend/app/page.tsx",
        ],
        "notes": "Do not re-import the old app-centric runtime shape; the live repo already replaced it with the current control-plane architecture.",
    },
    {
        "target_id": "legacy_mock_product_surfaces",
        "label": "Legacy mock product surfaces",
        "target_class": CLASS_ABANDON,
        "handling_state": STATE_DO_NOT_PORT,
        "owner": "legacy_cleanup",
        "destination_system": "none",
        "donor_source_refs": [
            "downloads/aiclone/frontend/app/outreach/page.tsx",
            "downloads/aiclone/frontend/app/outreach/[prospectId]/page.tsx",
            "downloads/aiclone/backend/app/routes/outreach_manual.py",
        ],
        "current_destination_refs": [
            "frontend/app/outreach/page.tsx",
            "frontend/app/outreach/[prospectId]/page.tsx",
        ],
        "notes": "These are useful only as historical examples of the product shell; they are not viable execution surfaces for the rebuilt repo.",
    },
    {
        "target_id": "bundled_build_and_secret_artifacts",
        "label": "Bundled build, dependency, and secret artifacts",
        "target_class": CLASS_ABANDON,
        "handling_state": STATE_DO_NOT_PORT,
        "owner": "repo_hygiene",
        "destination_system": "none",
        "donor_source_refs": [
            "downloads/aiclone/frontend/.next",
            "downloads/aiclone/node_modules",
            "downloads/aiclone/.env",
        ],
        "current_destination_refs": [
            "notes/aiclone-inventory.md",
        ],
        "notes": "Treat as archive exhaust only. These files should never influence active runtime truth or future repo structure.",
    },
)


def build_donor_repo_boundary_report(*, include_targets: bool = True) -> dict[str, Any]:
    entries = [dict(target) for target in _EXTRACTION_TARGETS]
    class_counts = {target_class: sum(1 for item in entries if item["target_class"] == target_class) for target_class in TARGET_CLASSES}
    handling_counts = {state: sum(1 for item in entries if item["handling_state"] == state) for state in HANDLING_STATES}
    payload: dict[str, Any] = {
        "schema_version": "donor_repo_boundary_report/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "donor_repo": {
            "repo_id": "downloads_aiclone",
            "label": "downloads/aiclone",
            "path": _relative_path(DONOR_REPO_PATH),
            "present": DONOR_REPO_PATH.exists(),
            "status_class": "reference_only",
            "current_role": "cold_reference_donor",
            "source_of_truth": "do_not_use_for_runtime_truth",
            "doc_ref": _relative_path(BOUNDARY_DOC_PATH),
            "future_state": "move_out_of_active_repo_tree_after_targeted_extraction",
            "forbidden_roles": [
                "active_execution_surface",
                "canonical_repo_source_of_truth",
                "formal_submodule",
            ],
        },
        "decision": {
            "mode": DECISION_MODE,
            "summary": "Treat downloads/aiclone as a bounded donor repo: extract only the narrow outreach/email patterns still worth carrying forward, keep imported knowledge packs as reference-only, and retire the subtree from the active repo once extraction is complete.",
            "doc_ref": _relative_path(BOUNDARY_DOC_PATH),
        },
        "summary": {
            "donor_repo_count": 1,
            "target_count": len(entries),
            "worth_porting_count": class_counts[CLASS_PORT],
            "reference_only_count": class_counts[CLASS_REFERENCE],
            "abandon_count": class_counts[CLASS_ABANDON],
            "pending_extraction_count": handling_counts[STATE_PENDING],
            "already_imported_count": handling_counts[STATE_IMPORTED],
            "leave_in_donor_count": handling_counts[STATE_LEAVE],
            "do_not_port_count": handling_counts[STATE_DO_NOT_PORT],
        },
    }
    if include_targets:
        payload["targets"] = entries
    return payload


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()
