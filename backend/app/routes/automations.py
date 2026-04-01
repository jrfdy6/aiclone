"""Automations Routes.

Provides visibility into all scheduled/triggered automations (cron jobs).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models.automations import AutomationMismatchReport, AutomationRun, AutomationRunMirrorRequest, AutomationRunMirrorResponse
from app.services import automation_mismatch_service, automation_run_service
from app.services.automation_service import automation_source_of_truth, list_automations

router = APIRouter(tags=["Automations"])


@router.get("/", response_model=dict)
async def automations_index() -> dict:
    automations = list_automations()
    synced = automation_run_service.sync_openclaw_run_mirror(limit=200)
    runs = automation_run_service.list_runs(limit=50)
    mismatch_report = automation_mismatch_service.build_mismatch_report()
    return {
        "success": True,
        "count": len(automations),
        "run_count": len(runs),
        "source_of_truth": automation_source_of_truth(),
        "run_sync_count": synced,
        "data": automations,
        "runs": runs,
        "mismatches": mismatch_report,
    }


@router.get("/runs", response_model=dict)
async def automation_runs_index(limit: int = 50) -> dict:
    synced = automation_run_service.sync_openclaw_run_mirror(limit=max(limit, 200))
    runs = automation_run_service.list_runs(limit=limit)
    return {
        "success": True,
        "count": len(runs),
        "source_of_truth": automation_source_of_truth(),
        "run_sync_count": synced,
        "data": runs,
    }


@router.post("/runs/mirror", response_model=AutomationRunMirrorResponse)
async def automation_runs_mirror(payload: AutomationRunMirrorRequest) -> AutomationRunMirrorResponse:
    count = automation_run_service.upsert_runs(payload.runs)
    return AutomationRunMirrorResponse(
        success=True,
        count=count,
        source_of_truth=automation_source_of_truth(),
    )


@router.get("/mismatches", response_model=AutomationMismatchReport)
async def automation_mismatches_index() -> AutomationMismatchReport:
    automation_run_service.sync_openclaw_run_mirror(limit=200)
    return automation_mismatch_service.build_mismatch_report()
