from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.services.firestore_client import db


DEFAULT_METADATA_KEYS = {
    "file_name": None,
    "file_type": None,
    "upload_timestamp": None,
    "topic": None,
    "extra_tags": [],
    "folder_id": None,
    "source_file_id": None,
}


def _matches_tag_filter(doc_tags: Optional[List[str]], tag_filter: Optional[List[str]]) -> bool:
    if not tag_filter:
        return True
    doc_tags = doc_tags or []
    return any(tag in doc_tags for tag in tag_filter)


def _format_metadata(doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(DEFAULT_METADATA_KEYS)
    metadata.update(data.get("metadata") or {})

    metadata.setdefault("file_name", data.get("source"))
    metadata.setdefault("file_type", data.get("source_type"))
    metadata.setdefault("upload_timestamp", data.get("created_at"))
    metadata.setdefault("extra_tags", data.get("tags") or [])
    metadata.setdefault("source_file_id", data.get("source_id") or doc_id)

    return metadata


def get_all_embeddings_for_user(
    user_id: str,
    tag_filter: Optional[List[str]] = None,
    source_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    collection = db.collection("users").document(user_id).collection("memory_chunks")
    query = collection
    if source_filter:
        query = query.where("source", "==", source_filter)

    documents = query.stream()
    items: List[Dict[str, Any]] = []
    for document in documents:
        data = document.to_dict()
        embedding = data.get("embedding")
        if not embedding or not _matches_tag_filter(data.get("tags"), tag_filter):
            continue
        items.append(
            {
                "id": document.id,
                "embedding": np.array(embedding, dtype=np.float32),
                "data": data,
            }
        )
    return items


def retrieve_similar(
    user_id: str,
    query_embedding: List[float],
    top_k: int = 5,
    tag_filter: Optional[List[str]] = None,
    source_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    items = get_all_embeddings_for_user(user_id, tag_filter=tag_filter, source_filter=source_filter)
    if not items:
        return []

    try:
        # Filter embeddings to match query dimension and ensure all have the same shape
        query_dim = len(query_embedding)
        embeddings_list = []
        valid_items = []
        
        for item in items:
            emb = item["embedding"]
            if isinstance(emb, np.ndarray):
                emb_array = emb
            else:
                emb_array = np.array(emb, dtype=np.float32)
            
            # Only include embeddings that match the query dimension
            if emb_array.shape[0] == query_dim:
                embeddings_list.append(emb_array)
                valid_items.append(item)
        
        if not embeddings_list:
            return []
        
        matrix = np.vstack(embeddings_list)
        query_vector = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        similarities = cosine_similarity(query_vector, matrix)[0]
    except Exception as e:
        import traceback
        print(f"❌ Error in retrieve_similar: {e}", flush=True)
        traceback.print_exc()
        raise

    paired = sorted(zip(valid_items, similarities), key=lambda pair: pair[1], reverse=True)
    results: List[Dict[str, Any]] = []
    for item, score in paired[:top_k]:
        data = item["data"]
        metadata = _format_metadata(item["id"], data)
        results.append(
            {
                "source_id": data.get("source_id") or data.get("source") or item["id"],
                "source_file_id": metadata.get("source_file_id"),
                "chunk_index": data.get("chunk_index"),
                "chunk": data.get("text"),
                "similarity_score": float(score),
                "metadata": metadata,
            }
        )
    return results
