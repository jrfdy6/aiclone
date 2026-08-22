from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool

from app.models import ExecutiveDecisionActionRequest, ExecutiveDecisionActionResult, ExecutiveDecisionQueue
from app.services.executive_decision_service import (
    ExecutiveDecisionActionError,
    ExecutiveDecisionNotFoundError,
    build_executive_decision_queue,
    execute_executive_decision_action,
)


router = APIRouter(tags=["Executive Decisions"], prefix="/api/executive")


@router.get("/decisions", response_model=ExecutiveDecisionQueue)
async def get_executive_decisions(response: Response) -> ExecutiveDecisionQueue:
    started_at = time.monotonic()
    response.headers["Cache-Control"] = "no-store, max-age=0"
    print("Executive decision route phase=threadpool_start", flush=True)
    result = await run_in_threadpool(build_executive_decision_queue)
    print(
        f"Executive decision route phase=threadpool_return duration_ms={int((time.monotonic() - started_at) * 1000)} "
        f"pending={len(result.all_pending)}",
        flush=True,
    )
    return result


@router.post(
    "/decisions/{decision_id}/actions/{action_id}",
    response_model=ExecutiveDecisionActionResult,
)
async def post_executive_decision_action(
    decision_id: str,
    action_id: str,
    payload: ExecutiveDecisionActionRequest,
    response: Response,
    legacy_compatibility: bool = False,
) -> ExecutiveDecisionActionResult:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    try:
        return await run_in_threadpool(
            execute_executive_decision_action,
            decision_id,
            action_id,
            payload,
            legacy_compatibility=legacy_compatibility,
        )
    except ExecutiveDecisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ExecutiveDecisionActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
