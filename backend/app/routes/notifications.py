from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.models import LogEntry, NotificationRequest, NotificationResponse
from app.routes.system_logs import persist_log

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/send", response_model=NotificationResponse)
async def send_notification(request: NotificationRequest):
    log = LogEntry(
        id=str(uuid.uuid4()),
        component="notifications",
        message=f"Dispatch {request.channel} notification via template {request.template}",
        context=request.payload,
    )
    persist_log(log)
    return NotificationResponse(status="queued", detail="Notification recorded for dispatch")
