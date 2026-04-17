from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from app.models import (
    BrainCanonicalMemorySyncStatusRequest,
    BrainContentSafeOperatorLessonsSyncRequest,
    BrainLongFormIngestRequest,
    BrainOperatorStorySignalsSyncRequest,
    BrainPersonaReviewRequest,
    BrainPersonaRerouteRequest,
    BrainSystemRouteRequest,
    BrainYouTubeWatchlistIngestRequest,
    PersonaDelta,
)
from app.services import persona_delta_service
from app.services.brain_long_form_ingest_service import brain_long_form_ingest_service
from app.services.brain_system_route_service import route_delta_signal
from app.services.brain_control_plane_service import build_brain_control_plane
from app.services.persona_promotion_service import build_committed_persona_overlay, promote_delta_to_canon, reroute_delta_promotion
from app.services.persona_review_queue_service import annotate_for_brain_queue
from app.services.social_belief_engine import load_persona_truth
from app.services.workspace_snapshot_store import upsert_snapshot
from app.services.workspace_snapshot_service import workspace_snapshot_service
from app.services.youtube_watchlist_service import build_youtube_watchlist_payload, list_ingest_jobs, queue_youtube_ingest, run_ingest_job

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
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
            include_workspace_files=False,
            include_doc_entries=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Long-form source registered in Brain",
        **result,
        "source_assets": snapshot.get("source_assets"),
        "content_reservoir": snapshot.get("content_reservoir"),
        "long_form_routes": snapshot.get("long_form_routes"),
        "persona_review_summary": snapshot.get("persona_review_summary"),
    }


@router.get("/youtube-watchlist")
async def get_youtube_watchlist():
    try:
        return build_youtube_watchlist_payload()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/youtube-watchlist/jobs")
async def get_youtube_watchlist_jobs():
    return {"jobs": list_ingest_jobs()}


@router.post("/youtube-watchlist/ingest")
async def queue_youtube_watchlist_ingest(payload: BrainYouTubeWatchlistIngestRequest, background_tasks: BackgroundTasks):
    try:
        job = queue_youtube_ingest(
            url=payload.url,
            title=payload.title,
            summary=payload.summary,
            author=payload.author,
            channel_name=payload.channel_name,
            priority_lane=payload.priority_lane,
            run_refresh=payload.run_refresh,
        )
        background_tasks.add_task(run_ingest_job, job["job_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "YouTube watchlist ingest queued",
        "job": job,
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
        "message": "Persona promotion committed. Local bundle sync queued.",
        "delta": annotate_for_brain_queue(updated),
        "overlay_counts": overlay.get("counts") if isinstance(overlay, dict) else {},
        "committed_target_files": (updated.metadata or {}).get("committed_target_files") or [],
        "bundle_written_files": (updated.metadata or {}).get("bundle_written_files") or [],
    }


@router.post("/persona-reroute/{delta_id}")
async def reroute_brain_persona_delta(delta_id: str, payload: BrainPersonaRerouteRequest):
    try:
        updated = reroute_delta_promotion(delta_id, target_file=payload.target_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not updated:
        raise HTTPException(status_code=404, detail="Persona delta not found")

    return {
        "message": f"Queued promotion rerouted to {payload.target_file}. Ready for canon commit.",
        "delta": annotate_for_brain_queue(updated),
        "target_file": payload.target_file,
    }


@router.post("/system-route/{delta_id}")
async def route_brain_signal(delta_id: str, payload: BrainSystemRouteRequest):
    try:
        updated, canonical_targets, standup, pm_card, route_results = route_delta_signal(
            delta_id,
            reflection_excerpt=payload.reflection_excerpt,
            selected_promotion_items=[item.model_dump(exclude_none=True) for item in payload.selected_promotion_items],
            workspace_key=payload.workspace_key,
            workspace_keys=payload.workspace_keys,
            canonical_memory_targets=payload.canonical_memory_targets,
            route_to_standup=payload.route_to_standup,
            standup_kind=payload.standup_kind,
            route_to_pm=payload.route_to_pm,
            pm_title=payload.pm_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Brain triage routed the reviewed signal.",
        "delta": annotate_for_brain_queue(updated),
        "canonical_memory_targets_queued": canonical_targets,
        "standup": standup,
        "pm_card": pm_card,
        "routes": route_results,
    }


@router.post("/memory-sync-status")
async def publish_brain_memory_sync_status(payload: BrainCanonicalMemorySyncStatusRequest):
    try:
        snapshot = upsert_snapshot(
            "shared_ops",
            "brain_memory_sync",
            payload.model_dump(),
            metadata={
                "source": payload.source,
                "payload_generated_at": payload.generated_at,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Brain canonical-memory sync status stored.",
        "snapshot": snapshot,
    }


@router.post("/operator-story-signals/sync")
async def publish_operator_story_signals(payload: BrainOperatorStorySignalsSyncRequest):
    try:
        snapshot = upsert_snapshot(
            payload.workspace_key,
            "operator_story_signals",
            payload.model_dump(),
            metadata={
                "source": payload.source,
                "payload_generated_at": payload.generated_at,
                "signal_count": payload.signal_count,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Operator story signals stored.",
        "snapshot": snapshot,
    }


@router.post("/content-safe-operator-lessons/sync")
async def publish_content_safe_operator_lessons(payload: BrainContentSafeOperatorLessonsSyncRequest):
    try:
        snapshot = upsert_snapshot(
            payload.workspace_key,
            "content_safe_operator_lessons",
            payload.model_dump(),
            metadata={
                "source": payload.source,
                "payload_generated_at": payload.generated_at,
                "lesson_count": payload.lesson_count,
                "source_snapshot_type": payload.source_snapshot_type,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Content-safe operator lessons stored.",
        "snapshot": snapshot,
    }


@router.post("/refresh-persona-review")
async def refresh_brain_persona_review():
    try:
        refreshed = workspace_snapshot_service.refresh_persisted_linkedin_os_state()
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(
            include_workspace_files=False,
            include_doc_entries=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "message": "Brain persona review and workspace snapshots refreshed.",
        "refreshed_snapshot_keys": sorted(refreshed.keys()),
        "persona_review_summary": snapshot.get("persona_review_summary"),
        "long_form_routes": snapshot.get("long_form_routes"),
        "source_assets": snapshot.get("source_assets"),
    }
