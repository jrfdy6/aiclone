from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.embedders import embed_text
from app.services.retrieval import retrieve_similar


router = APIRouter()


class ChatRetrievalRequest(BaseModel):
    user_id: str = Field(..., description="User identifier for scoped memory")
    query: str = Field(..., description="Natural language query to ground")
    top_k: int = Field(5, ge=1, le=50, description="Number of chunks to return")


@router.post("/")
async def chat_retrieve(req: ChatRetrievalRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    query_embedding = embed_text(req.query)
    results = retrieve_similar(
        user_id=req.user_id,
        query_embedding=query_embedding,
        top_k=req.top_k,
    )

    return {
        "success": True,
        "query": req.query,
        "results": results,
    }
