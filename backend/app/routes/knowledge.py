from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.embedders import embed_text
from app.services.retrieval import retrieve_similar


router = APIRouter()


class KnowledgeSearchRequest(BaseModel):
    user_id: str = Field(..., description="User identifier for scoped memory")
    search_query: str = Field(..., description="Search query across knowledge base")
    top_k: int = Field(10, ge=1, le=50, description="Number of chunks to return")


@router.post("/")
async def knowledge_search(req: KnowledgeSearchRequest):
    if not req.search_query.strip():
        raise HTTPException(status_code=400, detail="search_query cannot be empty.")

    query_embedding = embed_text(req.search_query)
    results = retrieve_similar(
        user_id=req.user_id,
        query_embedding=query_embedding,
        top_k=req.top_k,
    )

    return {
        "success": True,
        "query": req.search_query,
        "results": results,
    }
