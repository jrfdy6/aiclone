from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter

from app.models import LogEntry
from app.services import firestore_client
from app.services.local_store import append_log, load_logs

router = APIRouter(tags=["System Logs"])


def persist_log(entry: LogEntry) -> None:
    if firestore_client.get_firestore_client() is not None:
        firestore_client.write_document("system_logs", entry.id, entry.model_dump())
    else:
        append_log(entry)


def _load(limit: int) -> List[LogEntry]:
    payload = firestore_client.list_documents("system_logs")
    if payload:
        entries = [LogEntry(**item) for item in payload]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]
    return load_logs(limit)


@router.get("/", response_model=List[LogEntry])
async def list_logs(limit: int = 100, component: Optional[str] = None, level: Optional[str] = None):
    entries = _load(limit)
    if component:
        entries = [entry for entry in entries if entry.component == component]
    if level:
        entries = [entry for entry in entries if entry.level == level]
    return entries


@router.post("/", response_model=LogEntry)
async def create_log(entry: LogEntry):
    if not entry.id:
        entry.id = str(uuid.uuid4())
    persist_log(entry)
    return entry
