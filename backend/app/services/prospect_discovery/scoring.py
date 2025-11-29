"""
Prospect scoring/influence calculation
"""
from typing import List, Optional

from app.models.prospect_discovery import DiscoveredProspect
from .constants import PROSPECT_CATEGORIES


def calculate_influence_score(
    prospect: DiscoveredProspect,
    target_specialty: Optional[str] = None,
    target_location: Optional[str] = None,
    categories: Optional[List[str]] = None
) -> int:
    """
    Calculate influence score for a prospect (0-100)
    
    Scoring:
    - Direct influence on schooling: +40
    - Has contact info (email/phone): +20
    - DC/DMV location match: +20
    - Works with ages 10-18: +10
    - High socioeconomic clientele: +10
    - Group leadership role: +10
    """
    score = 0
    content_to_check = f"{prospect.bio_snippet or ''} {prospect.title or ''} {' '.join(prospect.specialty or [])}".lower()
    
    # =================================================================
    # DIRECT INFLUENCE ON K-12 DECISIONS (+40)
    # =================================================================
    
    high_influence_keywords = [
        'pediatrician', 'psychologist', 'psychiatrist', 'therapist',
        'educational consultant', 'school counselor', 'admissions',
        'treatment center', 'embassy', 'education officer', 'cultural officer',
        'athletic director', 'sports academy', 'coach',
        'mom group', 'parent network', 'pta', 'family services'
    ]
    
    if any(kw in content_to_check for kw in high_influence_keywords):
        score += 40
    elif prospect.title:
        # Check title for influence indicators
        title_lower = prospect.title.lower()
        if any(kw in title_lower for kw in ['director', 'founder', 'president', 'lead', 'chief', 'head']):
            score += 30
        else:
            score += 10  # Base for having any title
    
    # =================================================================
    # CONTACT INFO (+20)
    # =================================================================
    
    if prospect.contact.email:
        score += 15
    if prospect.contact.phone:
        score += 5
    
    # =================================================================
    # DC/DMV LOCATION MATCH (+20)
    # =================================================================
    
    location_content = f"{prospect.location or ''} {prospect.bio_snippet or ''} {prospect.source_url or ''}".lower()
    
    dc_keywords = ['washington dc', 'dc', 'd.c.', 'dmv', 'nova', 'northern virginia',
                  'montgomery county', 'fairfax', 'arlington', 'bethesda', 'silver spring',
                  'alexandria', 'chevy chase', 'georgetown', 'potomac', 'mclean', 'rockville']
    
    if target_location:
        target_lower = target_location.lower()
        is_dc_search = any(v in target_lower for v in ['dc', 'washington', 'dmv'])
        
        if is_dc_search:
            if any(kw in location_content for kw in dc_keywords):
                score += 20
        elif target_lower in location_content:
            score += 20
    
    # =================================================================
    # WORKS WITH AGES 10-18 (+10)
    # =================================================================
    
    age_keywords = ['adolescent', 'teen', 'teenager', 'youth', 'k-12', 'k12',
                   'middle school', 'high school', 'ages 10', 'ages 11', 'ages 12',
                   'ages 13', 'ages 14', 'ages 15', 'ages 16', 'ages 17', 'ages 18',
                   'child', 'children', 'young', 'student']
    
    if any(kw in content_to_check for kw in age_keywords):
        score += 10
    
    # =================================================================
    # HIGH SOCIOECONOMIC CLIENTELE (+10)
    # =================================================================
    
    affluent_keywords = ['private school', 'boarding school', 'prep school', 'independent school',
                        'embassy', 'diplomat', 'elite', 'premier', 'exclusive', 'luxury',
                        'concierge', 'executive', 'professional']
    
    if any(kw in content_to_check for kw in affluent_keywords):
        score += 10
    
    # =================================================================
    # GROUP LEADERSHIP (+10)
    # =================================================================
    
    leadership_keywords = ['founder', 'director', 'president', 'chair', 'leader',
                          'organizer', 'coordinator', 'head of', 'chief']
    
    if any(kw in content_to_check for kw in leadership_keywords):
        score += 10
    
    # =================================================================
    # CATEGORY MATCH BONUS
    # =================================================================
    
    if categories:
        for cat_id in categories:
            cat_info = PROSPECT_CATEGORIES.get(cat_id, {})
            cat_keywords = cat_info.get("keywords", [])
            if any(kw.lower() in content_to_check for kw in cat_keywords):
                score += 5
                break
    
    return min(score, 100)

