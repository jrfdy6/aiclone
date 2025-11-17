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
    print(f"📨 /api/chat/ received request: user_id={req.user_id}, query='{req.query[:50]}...'", flush=True)
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    print(f"  → Generating embedding for query...", flush=True)
    query_embedding = embed_text(req.query)
    print(f"  → Embedding generated, dimension: {len(query_embedding)}", flush=True)
    
    print(f"  → Retrieving similar chunks...", flush=True)
    results = retrieve_similar(
        user_id=req.user_id,
        query_embedding=query_embedding,
        top_k=req.top_k,
    )
    print(f"  → Found {len(results)} results", flush=True)

    return {
        "success": True,
        "query": req.query,
        "results": results,
    }
