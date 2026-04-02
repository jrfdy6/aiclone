from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models import IngestSignalRequest, RefreshSocialFeedRequest
from app.services import social_feed_refresh_service
from app.services.social_feed_preview_service import social_feed_preview_service
from app.services.workspace_snapshot_service import workspace_snapshot_service
router = APIRouter(tags=["Workspace"], prefix="/api/workspace")


def _serialize_status(status: dict[str, None | bool | datetime | str]) -> dict[str, None | bool | str]:
    result: dict[str, None | bool | str] = {}
    for key, value in status.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _has_live_workspace_payload(snapshot: dict[str, object]) -> bool:
    source_assets = snapshot.get("source_assets")
    content_reservoir = snapshot.get("content_reservoir")
    social_feed = snapshot.get("social_feed")
    source_items = source_assets.get("items") if isinstance(source_assets, dict) else None
    reservoir_items = content_reservoir.get("items") if isinstance(content_reservoir, dict) else None
    feed_items = social_feed.get("items") if isinstance(social_feed, dict) else None
    if source_items and not reservoir_items:
        return False
    return bool(source_items) or bool(feed_items)


@router.get("/refresh-social-feed")
async def get_social_feed_refresh_status():
    status = social_feed_refresh_service.get_status()
    return _serialize_status(status)


@router.get("/linkedin-os-snapshot")
async def get_linkedin_os_snapshot():
    try:
        snapshot = workspace_snapshot_service.get_linkedin_os_snapshot(persisted_only=True)
        if not _has_live_workspace_payload(snapshot):
            snapshot = workspace_snapshot_service.get_linkedin_os_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    refresh_status = snapshot.get("refresh_status")
    if isinstance(refresh_status, dict):
        snapshot["refresh_status"] = _serialize_status(refresh_status)
    return snapshot


@router.post("/refresh-social-feed")
async def refresh_social_feed(payload: RefreshSocialFeedRequest, background_tasks: BackgroundTasks):
    status = social_feed_refresh_service.get_status()
    if status["running"]:
        raise HTTPException(status_code=409, detail="Social feed refresh already running.")
    background_tasks.add_task(
        social_feed_refresh_service.run_refresh_background,
        payload.skip_fetch,
        payload.sources,
    )
    return {
        "status": "queued",
        "skip_fetch": payload.skip_fetch,
        "sources": payload.sources,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/ingest-signal")
async def ingest_signal(payload: IngestSignalRequest):
    try:
        preview_item = social_feed_preview_service.generate_preview(
            url=payload.url,
            text=payload.text,
            title=payload.title,
            priority_lane=payload.priority_lane,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "message": "Signal preview generated",
        "preview_item": preview_item,
    }
