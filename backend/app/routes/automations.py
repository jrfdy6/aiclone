"""Automations Routes.

Provides visibility into all scheduled/triggered automations (cron jobs).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.models.automations import AutomationMismatchReport, AutomationRun, AutomationRunMirrorRequest, AutomationRunMirrorResponse
from app.services import automation_mismatch_service, automation_run_service
from app.services.automation_service import automation_source_of_truth, list_automations

router = APIRouter(tags=["Automations"])


def _build_automations_index() -> dict:
    """Build the read-only automation view from the existing mirror/local fallback."""

    observed_runs = automation_run_service.list_runs(limit=500)
    automations = list_automations(runs=observed_runs)
    runs = observed_runs[:50]
    mismatch_report = automation_mismatch_service.build_mismatch_report(
        automations=automations,
        runs=observed_runs,
    )
    return {
        "success": True,
        "count": len(automations),
        "run_count": len(runs),
        "source_of_truth": automation_source_of_truth(),
        # Kept for response compatibility. Mirroring is an explicit write through
        # POST /runs/mirror; a GET must never mutate the Railway mirror.
        "ledger_sync_count": 0,
        "ledger_sync_performed": False,
        "data": automations,
        "runs": runs,
        "mismatches": mismatch_report,
    }


def _build_automation_runs_index(limit: int) -> dict:
    runs = automation_run_service.list_runs(limit=limit)
    return {
        "success": True,
        "count": len(runs),
        "source_of_truth": automation_source_of_truth(),
        "ledger_sync_count": 0,
        "ledger_sync_performed": False,
        "data": runs,
    }


def _build_automation_mismatch_report() -> AutomationMismatchReport:
    observed_runs = automation_run_service.list_runs(limit=500)
    automations = list_automations(runs=observed_runs)
    return automation_mismatch_service.build_mismatch_report(
        automations=automations,
        runs=observed_runs,
    )


@router.get("", response_model=dict, include_in_schema=False)
@router.get("/", response_model=dict)
async def automations_index() -> dict:
    return await run_in_threadpool(_build_automations_index)


@router.get("/runs", response_model=dict)
async def automation_runs_index(limit: int = Query(50, ge=1, le=500)) -> dict:
    return await run_in_threadpool(_build_automation_runs_index, limit)


@router.post("/runs/mirror", response_model=AutomationRunMirrorResponse)
async def automation_runs_mirror(payload: AutomationRunMirrorRequest) -> AutomationRunMirrorResponse:
    try:
        count = await run_in_threadpool(automation_run_service.upsert_runs, payload.runs)
    except automation_run_service.AutomationRunMirrorError as exc:
        raise HTTPException(status_code=503, detail="Automation run mirror storage is unavailable.") from exc
    return AutomationRunMirrorResponse(
        success=True,
        count=count,
        source_of_truth=automation_source_of_truth(),
    )


@router.get("/mismatches", response_model=AutomationMismatchReport)
async def automation_mismatches_index() -> AutomationMismatchReport:
    return await run_in_threadpool(_build_automation_mismatch_report)
