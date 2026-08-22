from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Response

from app.services import firestore_client, open_brain_metrics, session_metrics_service
from app.services.firestore_prospect_authority_service import read_prospects
from app.services.local_store import load_cached_prospects, load_logs

router = APIRouter(tags=["Analytics"])


@router.get("/compliance")
async def compliance_metrics(response: Response) -> Dict[str, int]:
    now = datetime.utcnow()
    window_start = now - timedelta(days=1)

    log_result = firestore_client.list_documents_with_status("system_logs")
    logs = log_result.value
    if logs:
        approvals = sum(1 for log in logs if log.get("component") == "approvals" and log.get("level") == "INFO")
    else:
        approvals = sum(1 for log in load_logs(200) if log.component == "approvals" and log.timestamp >= window_start)

    prospect_result = read_prospects(os.getenv("DEFAULT_USER_ID", "default-user"))
    prospects = list(prospect_result.documents)
    if prospects:
        ready = sum(1 for prospect in prospects if prospect.get("contact", {}).get("email"))
    else:
        ready = sum(1 for prospect in load_cached_prospects() if prospect.contact.email)

    states = {log_result.state, prospect_result.state}
    response.headers["X-AI-Clone-Firestore-State"] = (
        "degraded" if "degraded" in states else "compatibility" if "compatibility" in states else "ready"
    )
    reason_codes = tuple(dict.fromkeys((*log_result.reason_codes, *prospect_result.reason_codes)))
    if reason_codes:
        response.headers["X-AI-Clone-Degraded-Reasons"] = ",".join(reason_codes)
    response.headers["X-AI-Clone-Data-Source"] = "firestore_with_local_read_only_fallback"
    response.headers["Cache-Control"] = "no-store, max-age=0"

    return {
        "approvals_last_24h": approvals,
        "prospects_with_email": ready,
    }


@router.get("/open-brain")
async def open_brain_summary():
    return open_brain_metrics.fetch_metrics()


@router.get("/sessions")
async def session_metrics():
    """Aggregated session + token telemetry for Mission Control."""
    result = session_metrics_service.fetch_metrics()
    return result.model_dump()
