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

# Weight profiles for Chris Do content categories
# Scale: 1-5 (1=low priority, 5=high priority)
CATEGORY_WEIGHT_PROFILES = {
    "value": {
        "VOICE_PATTERNS": 5,
        "LINKEDIN_EXAMPLES": 3,
        "EXPERIENCES": 5,
        "PHILOSOPHY": 4,
        "VENTURES": 2,
        "BIO_FACTS": 2,
        "STRUGGLES": 1,
    },
    "sales": {
        "VOICE_PATTERNS": 5,
        "LINKEDIN_EXAMPLES": 2,
        "EXPERIENCES": 3,
        "PHILOSOPHY": 2,
        "VENTURES": 5,
        "BIO_FACTS": 4,
        "STRUGGLES": 3,
    },
    "personal": {
        "VOICE_PATTERNS": 5,
        "LINKEDIN_EXAMPLES": 4,
        "EXPERIENCES": 4,
        "PHILOSOPHY": 3,
        "VENTURES": 2,
        "BIO_FACTS": 1,
        "STRUGGLES": 5,
    },
}

# Channel modifiers (applied to base category weights)
CHANNEL_MODIFIERS = {
    "linkedin_post": {
        "VOICE_PATTERNS": 0,
        "LINKEDIN_EXAMPLES": 1,
        "EXPERIENCES": 0,
        "PHILOSOPHY": 0,
        "VENTURES": 0,
        "BIO_FACTS": 0,
        "STRUGGLES": 0,
    },
    "linkedin_dm": {
        "VOICE_PATTERNS": 1,
        "LINKEDIN_EXAMPLES": 0,
        "EXPERIENCES": 0,
        "PHILOSOPHY": -1,
        "VENTURES": 0,
        "BIO_FACTS": -1,
        "STRUGGLES": 1,
    },
    "cold_email": {
        "VOICE_PATTERNS": 0,
        "LINKEDIN_EXAMPLES": -1,
        "EXPERIENCES": 0,
        "PHILOSOPHY": 0,
        "VENTURES": 1,
        "BIO_FACTS": 1,
        "STRUGGLES": -1,
    },
    "instagram_post": {
        "VOICE_PATTERNS": 1,
        "LINKEDIN_EXAMPLES": -2,
        "EXPERIENCES": 0,
        "PHILOSOPHY": -1,
        "VENTURES": 0,
        "BIO_FACTS": -2,
        "STRUGGLES": 1,
    },
}


def get_combined_weights(category: str, channel: str) -> Dict[str, float]:
    """
    Combine base category weights with channel modifiers.
    Returns normalized weight multipliers for each tag.
    """
    base_weights = CATEGORY_WEIGHT_PROFILES.get(category, CATEGORY_WEIGHT_PROFILES["value"])
    modifiers = CHANNEL_MODIFIERS.get(channel, CHANNEL_MODIFIERS["linkedin_post"])
    
    combined = {}
    for tag in base_weights:
        # Apply modifier, clamp to 1-6 range
        weight = base_weights[tag] + modifiers.get(tag, 0)
        weight = max(1, min(6, weight))
        # Normalize to multiplier (1.0 = base, higher = boost)
        combined[tag] = weight / 3.0  # 3 is middle of 1-5 scale
    
    return combined


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
        
        # Test with a small query first to verify connectivity
        print(f"  [retrieval] Testing Firestore connectivity with small query...", flush=True)
        test_query = collection.limit(1)
        
        import concurrent.futures
        try:
            # Use timeout to prevent hanging
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(test_query.get)
                test_docs = future.result(timeout=3.0)
            print(f"  [retrieval] ✅ Firestore connectivity OK, found {len(test_docs)} test docs", flush=True)
        except concurrent.futures.TimeoutError:
            print(f"  [retrieval] ⚠️ Firestore query timed out (3s) - returning empty results", flush=True)
            return []
        except Exception as e:
            print(f"  [retrieval] ❌ Firestore query error: {e}", flush=True)
            return []
        
        # If test passed but returned 0 docs, collection is empty
        if len(test_docs) == 0:
            print(f"  [retrieval] Collection is empty, returning early", flush=True)
            return []
        
        # Now do the full query
        query = collection.limit(max_documents)
        if source_filter:
            query = query.where("source", "==", source_filter)

        print(f"  [retrieval] Executing full Firestore query...", flush=True)
        documents = query.get()
        print(f"  [retrieval] Query returned {len(documents)} documents", flush=True)
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


def retrieve_weighted(
    user_id: str,
    query_embedding: List[float],
    category: str = "value",
    channel: str = "linkedin_post",
    top_k: int = 7,
    tag_filter: Optional[List[str]] = None,
    source_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve chunks with tag-based weight boosting.
    
    Args:
        user_id: User ID for knowledge base lookup
        query_embedding: Query vector
        category: Chris Do category (value, sales, personal)
        channel: Content channel (linkedin_post, linkedin_dm, cold_email, instagram_post)
        top_k: Number of results to return
        tag_filter: Optional list of tags to filter by
        source_filter: Optional source file filter
    
    Returns:
        List of chunks sorted by weighted similarity score
    """
    items = get_all_embeddings_for_user(user_id, tag_filter=tag_filter, source_filter=source_filter)
    if not items:
        return []

    # Get weight multipliers for this category + channel combo
    weights = get_combined_weights(category, channel)
    print(f"  [retrieval] Using weights for {category}/{channel}: {weights}", flush=True)

    try:
        query_dim = len(query_embedding)
        embeddings_list = []
        valid_items = []
        item_tags = []
        
        for item in items:
            emb = item["embedding"]
            if isinstance(emb, np.ndarray):
                emb_array = emb
            else:
                emb_array = np.array(emb, dtype=np.float32)
            
            if emb_array.shape[0] == query_dim:
                embeddings_list.append(emb_array)
                valid_items.append(item)
                # Get persona_tag from metadata
                metadata = item["data"].get("metadata", {})
                tag = metadata.get("persona_tag", "UNTAGGED")
                item_tags.append(tag)
        
        if not embeddings_list:
            return []
        
        matrix = np.vstack(embeddings_list)
        query_vector = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        similarities = cosine_similarity(query_vector, matrix)[0]
        
        # Apply tag-based weight multipliers
        weighted_scores = []
        for i, (sim, tag) in enumerate(zip(similarities, item_tags)):
            multiplier = weights.get(tag, 1.0)
            weighted_score = sim * multiplier
            weighted_scores.append(weighted_score)
        
        weighted_scores = np.array(weighted_scores)
        
    except Exception as e:
        import traceback
        print(f"❌ Error in retrieve_weighted: {e}", flush=True)
        traceback.print_exc()
        raise

    # Sort by weighted score
    paired = sorted(zip(valid_items, weighted_scores, similarities, item_tags), 
                    key=lambda x: x[1], reverse=True)
    
    # Debug logging
    print(f"\n[RETRIEVAL DEBUG] {category}/{channel}", flush=True)
    print(f"Top {min(top_k, len(paired))} Results:", flush=True)
    for i, (item, w_score, raw_score, tag) in enumerate(paired[:top_k]):
        multiplier = weights.get(tag, 1.0)
        preview = item["data"].get("text", "")[:50].replace("\n", " ")
        print(f"  {i+1}. {tag:20} — sim: {raw_score:.3f} — weight: {multiplier:.2f} — final: {w_score:.3f} — \"{preview}...\"", flush=True)
    
    results: List[Dict[str, Any]] = []
    tag_distribution = {}
    
    for item, weighted_score, raw_score, tag in paired[:top_k]:
        data = item["data"]
        metadata = _format_metadata(item["id"], data)
        
        # Track tag distribution in results
        tag_distribution[tag] = tag_distribution.get(tag, 0) + 1
        
        results.append(
            {
                "source_id": data.get("source_id") or data.get("source") or item["id"],
                "source_file_id": metadata.get("source_file_id"),
                "chunk_index": data.get("chunk_index"),
                "chunk": data.get("text"),
                "similarity_score": float(raw_score),
                "weighted_score": float(weighted_score),
                "persona_tag": tag,
                "metadata": metadata,
            }
        )
    
    print(f"  [retrieval] Result tag distribution: {tag_distribution}", flush=True)
    return results
