from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Response, status

from app.models import KnowledgeDoc
from app.services import firestore_client
from app.services.local_store import load_local_knowledge

router = APIRouter(tags=["Knowledge"])


def _set_read_headers(response: Response, *, state: str, source: str, reason_codes: tuple[str, ...] = ()) -> None:
    response.headers["X-AI-Clone-Firestore-State"] = state
    response.headers["X-AI-Clone-Data-Source"] = source
    if reason_codes:
        response.headers["X-AI-Clone-Degraded-Reasons"] = ",".join(reason_codes)


def _load_from_firestore() -> tuple[List[KnowledgeDoc], firestore_client.FirestoreReadResult]:
    result = firestore_client.list_documents_with_status("knowledge_docs")
    return [KnowledgeDoc(**item) for item in result.value], result


def _filter_docs(docs: List[KnowledgeDoc], tag: Optional[str], search: Optional[str]) -> List[KnowledgeDoc]:
    results = docs
    if tag:
        results = [doc for doc in results if tag.lower() in [t.lower() for t in doc.tags]]
    if search:
        needle = search.lower()
        results = [doc for doc in results if needle in doc.title.lower() or needle in (doc.summary or "").lower()]
    return results


@router.get("/", response_model=List[KnowledgeDoc])
async def list_knowledge(response: Response, tag: Optional[str] = None, search: Optional[str] = None):
    docs, read_result = _load_from_firestore()
    if docs:
        _set_read_headers(response, state=read_result.state, source="firestore:knowledge_docs", reason_codes=read_result.reason_codes)
    else:
        docs = load_local_knowledge()
        state = read_result.state if read_result.state == "degraded" else "compatibility"
        _set_read_headers(
            response,
            state=state,
            source="local_read_only_compatibility" if docs else "firestore:knowledge_docs",
            reason_codes=read_result.reason_codes,
        )
    return _filter_docs(docs, tag, search)


@router.get("/{doc_id}", response_model=KnowledgeDoc)
async def get_knowledge_doc(doc_id: str, response: Response):
    read_result = firestore_client.get_document_with_status("knowledge_docs", doc_id)
    if read_result.value:
        _set_read_headers(response, state="ready", source="firestore:knowledge_docs")
        return KnowledgeDoc(**read_result.value)
    for item in load_local_knowledge():
        if item.id == doc_id:
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
                "message": "Knowledge lookup is temporarily unavailable.",
            },
        )
    raise HTTPException(status_code=404, detail="Knowledge doc not found")
