from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Response

from app.models import LogEntry
from app.services import firestore_client
from app.services.local_store import append_log, load_logs

router = APIRouter(tags=["System Logs"])


def persist_log(entry: LogEntry) -> tuple[str, str, tuple[str, ...]]:
    if firestore_client.get_firestore_client() is not None:
        try:
            firestore_client.write_document("system_logs", entry.id, entry.model_dump())
            return "ready", "firestore:system_logs", ()
        except Exception as exc:
            print(f"⚠️ persist_log: falling back to local log cache after Firestore error [{type(exc).__name__}]", flush=True)
            reason_codes = ("firestore_write_failed",)
    else:
        reason_codes = ("firestore_unavailable",)
    append_log(entry)
    return "degraded", "local_compatibility", reason_codes


def _load_firestore_logs() -> firestore_client.FirestoreReadResult:
    return firestore_client.list_documents_with_status("system_logs")


def _load(limit: int) -> tuple[List[LogEntry], str, str, tuple[str, ...]]:
    result = _load_firestore_logs()
    if result.value:
        entries = [LogEntry(**item) for item in result.value]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit], result.state, "firestore:system_logs", result.reason_codes
    local_entries = load_logs(limit)
    state = result.state if result.state == "degraded" else "compatibility"
    return local_entries, state, "local_read_only_compatibility" if local_entries else "firestore:system_logs", result.reason_codes


def _set_headers(response: Response, state: str, source: str, reason_codes: tuple[str, ...]) -> None:
    response.headers["X-AI-Clone-Firestore-State"] = state
    response.headers["X-AI-Clone-Data-Source"] = source
    if reason_codes:
        response.headers["X-AI-Clone-Degraded-Reasons"] = ",".join(reason_codes)
    response.headers["Cache-Control"] = "no-store, max-age=0"


@router.get("/", response_model=List[LogEntry])
async def list_logs(response: Response, limit: int = 100, component: Optional[str] = None, level: Optional[str] = None):
    entries, state, source, reason_codes = _load(limit)
    _set_headers(response, state, source, reason_codes)
    if component:
        entries = [entry for entry in entries if entry.component == component]
    if level:
        entries = [entry for entry in entries if entry.level == level]
    return entries


@router.post("/", response_model=LogEntry)
async def create_log(entry: LogEntry, response: Response):
    if not entry.id:
        entry.id = str(uuid.uuid4())
    state, source, reason_codes = persist_log(entry)
    _set_headers(response, state, source, reason_codes)
    return entry
