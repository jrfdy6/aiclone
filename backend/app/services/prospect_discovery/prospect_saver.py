"""
Prospect saving and storage utilities
"""
import time
import logging
from typing import List

from app.models.prospect_discovery import DiscoveredProspect, ProspectDiscoveryRequest
from app.services.firestore_client import db
from .validators import is_valid_prospect_for_saving

logger = logging.getLogger(__name__)


def store_discovery(
    user_id: str,
    discovery_id: str,
    request: ProspectDiscoveryRequest,
    prospects: List[DiscoveredProspect],
    search_query: str
):
    """Store discovery results in Firestore"""
    doc_data = {
        "discovery_id": discovery_id,
        "source": request.source.value,
        "specialty": request.specialty,
        "location": request.location,
        "keywords": request.keywords,
        "search_query": search_query,
        "total_found": len(prospects),
        "prospects": [p.dict() for p in prospects],
        "created_at": time.time(),
    }
    
    doc_ref = db.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
    doc_ref.set(doc_data)
    
    logger.info(f"Stored discovery: {discovery_id} with {len(prospects)} prospects")


def save_prospects_to_database(user_id: str, prospects: List[DiscoveredProspect]) -> int:
    """
    Save discovered prospects to the main prospects collection (skip duplicates).
    Returns the number of prospects successfully saved.
    """
    saved_count = 0
    
    # Filter prospects before saving using validator
    valid_prospects = [p for p in prospects if is_valid_prospect_for_saving(p)]
    filtered_count = len(prospects) - len(valid_prospects)
    if filtered_count > 0:
        logger.info(f"Filtered out {filtered_count} invalid prospects before saving (from {len(prospects)} total)")
    
    logger.info(f"Attempting to save {len(valid_prospects)} valid prospects (filtered {filtered_count} invalid)")
    
    # Track categories for summary
    category_counts = {}
    
    for prospect in valid_prospects:
        # Create unique doc ID from email or name
        if prospect.contact.email:
            doc_id = prospect.contact.email.replace("@", "_at_").replace(".", "_")
        else:
            # Use name-based ID to prevent duplicates
            doc_id = prospect.name.lower().replace(" ", "_").replace(".", "")
        
        doc_ref = db.collection("users").document(user_id).collection("prospects").document(doc_id)
        
        # Check if already exists - skip if so
        if doc_ref.get().exists:
            logger.debug(f"Skipping duplicate prospect: {prospect.name}")
            continue
        
        prospect_doc = {
            "name": prospect.name,
            "title": prospect.title,
            "company": prospect.organization,
            "email": prospect.contact.email,
            "phone": prospect.contact.phone,
            "website": prospect.contact.website,
            "location": prospect.location,
            "source": f"discovery:{prospect.source.value}",
            "source_url": prospect.source_url,
            "fit_score": prospect.fit_score,
            "status": "new",
            "tags": prospect.specialty or [],
            "bio_snippet": prospect.bio_snippet,
            "created_at": time.time(),
        }
        
        # Track category
        category_tag = prospect.specialty[0] if prospect.specialty else "Unknown"
        category_counts[category_tag] = category_counts.get(category_tag, 0) + 1
        
        logger.info(f"[SAVE] {prospect.name} | Category: {category_tag} | Org: {prospect.organization} | Email: {prospect.contact.email or 'N/A'} | Phone: {prospect.contact.phone or 'N/A'}")
        doc_ref.set(prospect_doc)
        saved_count += 1
    
    duplicate_count = len(valid_prospects) - saved_count
    logger.info(f"=== SAVE SUMMARY ===")
    logger.info(f"Total prospects found: {len(prospects)}")
    logger.info(f"Filtered (invalid): {filtered_count}")
    logger.info(f"Valid prospects: {len(valid_prospects)}")
    logger.info(f"Duplicates skipped: {duplicate_count}")
    logger.info(f"Successfully saved: {saved_count}")
    logger.info(f"=== CATEGORY BREAKDOWN ===")
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {cat}: {count} prospects")
    
    return saved_count

