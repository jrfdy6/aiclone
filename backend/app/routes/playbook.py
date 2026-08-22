from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response, status

from app.models import Playbook
from app.services import firestore_client
from app.services.local_store import load_local_playbooks

router = APIRouter(tags=["Playbooks"])


def _set_read_headers(response: Response, *, state: str, source: str, reason_codes: tuple[str, ...] = ()) -> None:
    response.headers["X-AI-Clone-Firestore-State"] = state
    response.headers["X-AI-Clone-Data-Source"] = source
    if reason_codes:
        response.headers["X-AI-Clone-Degraded-Reasons"] = ",".join(reason_codes)


def _load_from_firestore() -> tuple[List[Playbook], firestore_client.FirestoreReadResult]:
    result = firestore_client.list_documents_with_status("playbooks")
    return [Playbook(**item) for item in result.value], result


@router.get("/", response_model=List[Playbook])
async def list_playbooks(response: Response, category: Optional[str] = None):
    playbooks, read_result = _load_from_firestore()
    if playbooks:
        _set_read_headers(response, state=read_result.state, source="firestore:playbooks", reason_codes=read_result.reason_codes)
    else:
        playbooks = load_local_playbooks()
        state = read_result.state if read_result.state == "degraded" else "compatibility"
        _set_read_headers(
            response,
            state=state,
            source="local_read_only_compatibility" if playbooks else "firestore:playbooks",
            reason_codes=read_result.reason_codes,
        )
    if category:
        playbooks = [p for p in playbooks if p.category.lower() == category.lower()]
    return playbooks


@router.get("/{playbook_id}", response_model=Playbook)
async def get_playbook(playbook_id: str, response: Response):
    read_result = firestore_client.get_document_with_status("playbooks", playbook_id)
    if read_result.value:
        _set_read_headers(response, state="ready", source="firestore:playbooks")
        return Playbook(**read_result.value)
    for item in load_local_playbooks():
        if item.id == playbook_id:
            _set_read_headers(
                response,
                state="degraded" if read_result.state == "degraded" else "compatibility",
                source="local_read_only_compatibility",
                reason_codes=read_result.reason_codes,
            )
            return item
    if read_result.state == "degraded":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": list(read_result.reason_codes),
                "message": "Playbook lookup is temporarily unavailable.",
            },
        )
    raise HTTPException(status_code=404, detail="Playbook not found")
