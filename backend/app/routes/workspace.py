from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models import IngestSignalRequest, LinkedinOwnerReviewDecisionRequest, RefreshSocialFeedRequest
from app.services import social_feed_refresh_service
from app.services.linkedin_owner_review_service import list_owner_review_items, record_owner_decision
from app.services.workspace_registry_service import WORKSPACES_ROOT, workspace_registry_payload
from app.services.social_feed_preview_service import social_feed_preview_service
from app.services.workspace_snapshot_service import workspace_snapshot_service
router = APIRouter(tags=["Workspace"], prefix="/api/workspace")

WORKSPACE_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
WORKSPACE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
WORKSPACE_IMAGE_MAX_BYTES = 10 * 1024 * 1024


def _serialize_status(status: dict[str, None | bool | datetime | str]) -> dict[str, None | bool | str]:
    result: dict[str, None | bool | str] = {}
    for key, value in status.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _resolve_workspace_image_target(raw_path: str) -> tuple[str, Path]:
    text = str(raw_path or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Artifact path is required.")
    candidate = Path(text)
    if candidate.is_absolute():
        raise HTTPException(status_code=400, detail="Artifact path must be repo-relative.")
    if any(part in {"..", ""} for part in candidate.parts):
        raise HTTPException(status_code=400, detail="Artifact path must stay inside the workspaces tree.")
    if not candidate.parts or candidate.parts[0] != "workspaces":
        raise HTTPException(status_code=400, detail="Artifact path must start with `workspaces/`.")
    normalized = candidate.as_posix()
    if Path(normalized).suffix.lower() not in WORKSPACE_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .png, .jpg, .jpeg, or .webp workspace images are allowed.")
    workspaces_root = WORKSPACES_ROOT.resolve()
    target = (workspaces_root.parent / normalized).resolve()
    if target != workspaces_root and workspaces_root not in target.parents:
        raise HTTPException(status_code=400, detail="Artifact path must resolve inside the repo workspaces root.")
    return normalized, target


@router.get("/registry")
async def get_workspace_registry(response: Response, include_executive: bool = True):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return workspace_registry_payload(include_executive=include_executive)


@router.get("/refresh-social-feed")
async def get_social_feed_refresh_status():
    status = social_feed_refresh_service.get_status()
    return _serialize_status(status)


@router.get("/linkedin-os-snapshot")
async def get_linkedin_os_snapshot():
    try:
        snapshot = await run_in_threadpool(
            workspace_snapshot_service.get_linkedin_os_snapshot,
            persisted_only=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    refresh_status = snapshot.get("refresh_status")
    if isinstance(refresh_status, dict):
        snapshot["refresh_status"] = _serialize_status(refresh_status)
    return snapshot


@router.get("/linkedin-os-owner-review")
async def get_linkedin_os_owner_review(include_resolved: bool = False):
    try:
        return list_owner_review_items(include_resolved=include_resolved)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/linkedin-os-owner-review/{queue_id}")
async def post_linkedin_os_owner_review(queue_id: str, payload: LinkedinOwnerReviewDecisionRequest):
    try:
        return record_owner_decision(queue_id, payload.decision, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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


@router.post("/artifacts/upload-image")
async def upload_workspace_image(path: str = Form(...), image: UploadFile = File(...)):
    content_type = str(image.content_type or "").strip().lower()
    if content_type not in WORKSPACE_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, or WEBP images can be uploaded to workspace artifacts.")
    normalized_path, target_path = _resolve_workspace_image_target(path)
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded image was empty.")
    if len(payload) > WORKSPACE_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded image exceeds the 10 MB workspace artifact limit.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(payload)
    return {
        "path": normalized_path,
        "content_type": content_type,
        "bytes_written": len(payload),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
