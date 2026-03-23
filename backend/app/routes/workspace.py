from __future__ import annotations

from datetime import datetime, timezone
import subprocess
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models import IngestSignalRequest, RefreshSocialFeedRequest
from app.services import social_feed_refresh_service

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
INGEST_SCRIPT = WORKSPACE_ROOT / "scripts" / "personal-brand" / "ingest_web_signal.py"
router = APIRouter(tags=["Workspace"], prefix="/api/workspace")


def _serialize_status(status: dict[str, None | bool | datetime | str]) -> dict[str, None | bool | str]:
    result: dict[str, None | bool | str] = {}
    for key, value in status.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


@router.get("/refresh-social-feed")
async def get_social_feed_refresh_status():
    status = social_feed_refresh_service.get_status()
    return _serialize_status(status)


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
    cmd = ["python3", str(INGEST_SCRIPT), "--priority-lane", payload.priority_lane]
    if payload.url:
        cmd += ["--url", payload.url]
    if payload.text:
        cmd += ["--text", payload.text]
    if payload.title:
        cmd += ["--title", payload.title]
    if payload.run_refresh:
        cmd += ["--run-refresh"]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=exc.stderr.strip() or "Failed to ingest signal.")
    return {
        "message": "Signal ingested",
        "output": result.stdout.strip(),
    }
