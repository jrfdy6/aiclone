from typing import Any, Dict, List, Optional
import concurrent.futures
import signal

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
    max_documents: int = 1000,  # Limit to prevent timeouts
) -> List[Dict[str, Any]]:
    print(f"  [retrieval] Fetching embeddings for user {user_id}...", flush=True)
    try:
        collection = db.collection("users").document(user_id).collection("memory_chunks")
        query = collection.limit(max_documents)  # Add limit to prevent fetching too many
        if source_filter:
            query = query.where("source", "==", source_filter)

        print(f"  [retrieval] Executing Firestore query...", flush=True)
        # Use get() with timeout to prevent hanging
        try:
            # Wrap Firestore query in a timeout (5 seconds)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(query.get)
                documents = future.result(timeout=5.0)
            print(f"  [retrieval] Query returned {len(documents)} documents", flush=True)
        except concurrent.futures.TimeoutError:
            print(f"  [retrieval] ❌ Firestore query timed out after 5 seconds", flush=True)
            return []  # Return empty list on timeout
        except Exception as e:
            print(f"  [retrieval] ❌ Firestore query error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return []  # Return empty list on error
        items: List[Dict[str, Any]] = []
        count = 0
        for document in documents:
            count += 1
            if count % 100 == 0:
                print(f"  [retrieval] Processed {count} documents so far...", flush=True)
            try:
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
            except Exception as e:
                print(f"  [retrieval] Error processing document {document.id}: {e}", flush=True)
                continue
        print(f"  [retrieval] Processed {count} documents, returning {len(items)} valid items", flush=True)
        return items
    except Exception as e:
        import traceback
        print(f"  [retrieval] ❌ Error fetching embeddings: {e}", flush=True)
        traceback.print_exc()
        # Return empty list on error rather than crashing
        return []


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
