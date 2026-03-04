from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models import KnowledgeDoc
from app.services import firestore_client
from app.services.local_store import load_local_knowledge

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


def _load_from_firestore() -> List[KnowledgeDoc]:
    payload = firestore_client.list_documents("knowledge_docs")
    if not payload:
        return []
    return [KnowledgeDoc(**item) for item in payload]


def _filter_docs(docs: List[KnowledgeDoc], tag: Optional[str], search: Optional[str]) -> List[KnowledgeDoc]:
    results = docs
    if tag:
        results = [doc for doc in results if tag.lower() in [t.lower() for t in doc.tags]]
    if search:
        needle = search.lower()
        results = [doc for doc in results if needle in doc.title.lower() or needle in (doc.summary or "").lower()]
    return results


@router.get("/", response_model=List[KnowledgeDoc])
async def list_knowledge(tag: Optional[str] = None, search: Optional[str] = None):
    docs = _load_from_firestore() or load_local_knowledge()
    return _filter_docs(docs, tag, search)


@router.get("/{doc_id}", response_model=KnowledgeDoc)
async def get_knowledge_doc(doc_id: str):
    doc = firestore_client.get_document("knowledge_docs", doc_id)
    if doc:
        return KnowledgeDoc(**doc)
    for item in load_local_knowledge():
        if item.id == doc_id:
            return item
    raise HTTPException(status_code=404, detail="Knowledge doc not found")
