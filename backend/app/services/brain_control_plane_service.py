from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services import open_brain_metrics, open_brain_service
from app.services.automation_service import list_automations
from app.services.workspace_snapshot_store import get_snapshot_payload
from app.services.workspace_snapshot_service import workspace_snapshot_service


def build_brain_control_plane() -> dict[str, Any]:
    automations = list_automations()
    telemetry = open_brain_metrics.fetch_metrics()
    telemetry_health = open_brain_service.fetch_health().model_dump()
    workspace_snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
        persisted_only=True,
        include_workspace_files=False,
        include_doc_entries=False,
    )
    brain_memory_sync = get_snapshot_payload("shared_ops", "brain_memory_sync")
    persona_counts = ((workspace_snapshot.get("persona_review_summary") or {}).get("counts") or {}) if isinstance(workspace_snapshot, dict) else {}
    source_asset_counts = ((workspace_snapshot.get("source_assets") or {}).get("counts") or {}) if isinstance(workspace_snapshot, dict) else {}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automations": automations,
        "telemetry": telemetry,
        "telemetry_health": telemetry_health,
        "brain_memory_sync": brain_memory_sync,
        "workspace_snapshot": workspace_snapshot,
        "summary": {
            "automation_count": len(automations),
            "active_automation_count": len([job for job in automations if str(getattr(job, "status", "")).lower() == "active"]),
            "capture_count": int(((telemetry.get("captures") or {}).get("total")) or 0),
            "doc_count": len((workspace_snapshot.get("doc_entries") or [])) if isinstance(workspace_snapshot, dict) else 0,
            "workspace_file_count": len((workspace_snapshot.get("workspace_files") or [])) if isinstance(workspace_snapshot, dict) else 0,
            "pending_review_count": int(persona_counts.get("brain_pending_review") or 0),
            "workspace_saved_count": int(persona_counts.get("workspace_saved") or 0),
            "source_asset_count": int(source_asset_counts.get("total") or 0),
            "brain_memory_sync_queue_count": int(((brain_memory_sync or {}).get("queued_route_count")) or 0),
        },
    }
