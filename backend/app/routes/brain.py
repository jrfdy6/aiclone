from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import BrainLongFormIngestRequest
from app.services.brain_long_form_ingest_service import brain_long_form_ingest_service
from app.services.workspace_snapshot_service import workspace_snapshot_service

router = APIRouter(tags=["Brain"], prefix="/api/brain")


@router.post("/ingest-long-form")
async def ingest_long_form(payload: BrainLongFormIngestRequest):
    try:
        result = brain_long_form_ingest_service.register_source(
            url=payload.url,
            title=payload.title,
            summary=payload.summary,
            notes=payload.notes,
            transcript_text=payload.transcript_text,
            source_type=payload.source_type,
            author=payload.author,
            run_refresh=payload.run_refresh,
        )
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Long-form source registered in Brain",
        **result,
        "source_assets": snapshot.get("source_assets"),
        "long_form_routes": snapshot.get("long_form_routes"),
        "persona_review_summary": snapshot.get("persona_review_summary"),
    }
