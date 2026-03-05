from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter

from app.services import firestore_client
from app.services.local_store import load_cached_prospects, load_logs

router = APIRouter(tags=["Analytics"])


@router.get("/compliance")
async def compliance_metrics() -> Dict[str, int]:
    now = datetime.utcnow()
    window_start = now - timedelta(days=1)

    logs = firestore_client.list_documents("system_logs")
    if logs:
        approvals = sum(1 for log in logs if log.get("component") == "approvals" and log.get("level") == "INFO")
    else:
        approvals = sum(1 for log in load_logs(200) if log.component == "approvals" and log.timestamp >= window_start)

    prospects = firestore_client.list_documents("prospects")
    if prospects:
        ready = sum(1 for prospect in prospects if prospect.get("contact", {}).get("email"))
    else:
        ready = sum(1 for prospect in load_cached_prospects() if prospect.contact.email)

    return {
        "approvals_last_24h": approvals,
        "prospects_with_email": ready,
    }
