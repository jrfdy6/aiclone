from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.models import BrainLongFormIngestRequest, BrainPersonaReviewRequest, PersonaDelta
from app.services import persona_delta_service
from app.services.brain_long_form_ingest_service import brain_long_form_ingest_service
from app.services.brain_control_plane_service import build_brain_control_plane
from app.services.persona_promotion_service import build_committed_persona_overlay, promote_delta_to_canon
from app.services.persona_review_queue_service import annotate_for_brain_queue
from app.services.social_belief_engine import load_persona_truth
from app.services.workspace_snapshot_service import workspace_snapshot_service

router = APIRouter(tags=["Brain"], prefix="/api/brain")


@router.get("/control-plane")
async def get_brain_control_plane(response: Response):
    try:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return build_brain_control_plane()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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


@router.post("/persona-review/{delta_id}", response_model=PersonaDelta)
async def submit_brain_persona_review(delta_id: str, payload: BrainPersonaReviewRequest):
    try:
        updated = persona_delta_service.apply_brain_review(
            delta_id,
            mode=payload.mode,
            response_kind=payload.response_kind,
            reflection_excerpt=payload.reflection_excerpt,
            resolution_capture_id=payload.resolution_capture_id,
            selected_promotion_items=[item.model_dump(exclude_none=True) for item in payload.selected_promotion_items],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")

    return annotate_for_brain_queue(updated)


@router.post("/persona-promote/{delta_id}")
async def promote_brain_persona_delta(delta_id: str):
    try:
        updated = promote_delta_to_canon(delta_id)
        load_persona_truth.cache_clear()
        overlay = build_committed_persona_overlay()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")

    return {
        "message": "Persona promotion committed to runtime canon. Local bundle sync pending.",
        "delta": annotate_for_brain_queue(updated),
        "overlay_counts": overlay.get("counts") if isinstance(overlay, dict) else {},
        "committed_target_files": (updated.metadata or {}).get("committed_target_files") or [],
        "bundle_written_files": (updated.metadata or {}).get("bundle_written_files") or [],
    }
