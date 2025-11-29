"""
Extractor factory - automatically selects the right extractor based on URL/category
"""
import re
import logging
from typing import Optional, List

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect
from .base import BaseExtractor

logger = logging.getLogger(__name__)


def get_extractor_for_url(
    url: str,
    content: str,
    source: ProspectSource,
    category: Optional[str] = None
) -> Optional[BaseExtractor]:
    """
    Factory function to select the appropriate extractor based on URL patterns.
    
    Returns the extractor class or None if generic extractor should be used.
    """
    url_lower = url.lower()
    
    # Psychology Today listings/directories
    is_psychology_today_listing = (
        'psychologytoday.com' in url_lower and 
        any(path in url_lower for path in ['/us/therapists/', '/therapists/', '/find-a-therapist'])
    )
    if is_psychology_today_listing:
        from .psychology_today import PsychologyTodayExtractor
        return PsychologyTodayExtractor()
    
    # Psychology Today individual profiles
    if source == ProspectSource.PSYCHOLOGY_TODAY or 'psychologytoday.com' in url_lower:
        from .psychology_today import PsychologyTodayExtractor
        return PsychologyTodayExtractor()
    
    # Doctor directories (Healthgrades, Zocdoc, etc.)
    is_doctor_directory = any(domain in url_lower for domain in [
        'healthgrades.com', 'zocdoc.com', 'vitals.com', 'webmd.com',
        'doctor.com', 'ratemds.com', 'health.usnews.com'
    ])
    if is_doctor_directory:
        from .doctor_directory import DoctorDirectoryExtractor
        return DoctorDirectoryExtractor()
    
    # Treatment centers
    is_treatment_center = (
        any(keyword in url_lower for keyword in [
            'treatment', 'rehab', 'recovery', 'residential', 'php', 'iop', 
            'therapeutic', 'wilderness', 'boarding'
        ]) or 
        any(path in url_lower for path in ['/team', '/staff', '/leadership', '/admissions', '/about'])
    )
    if is_treatment_center:
        from .treatment_center import TreatmentCenterExtractor
        return TreatmentCenterExtractor()
    
    # Embassies/Consulates
    is_embassy = (
        any(keyword in url_lower for keyword in [
            'embassy', 'consulate', 'diplomatic', 'diplomatic-mission'
        ]) or 
        any(domain in url_lower for domain in ['.embassy.', '.consulate.']) or
        '/embassy/' in url_lower or '/consulate/' in url_lower
    )
    if is_embassy:
        from .embassy import EmbassyExtractor
        return EmbassyExtractor()
    
    # Youth sports organizations
    is_youth_sports = (
        any(keyword in url_lower for keyword in [
            'sports academy', 'athletic academy', 'youth sports', 'elite sports',
            'travel team', 'club soccer', 'club basketball', 'premier soccer',
            'academy soccer', 'academy basketball', 'youth soccer', 'youth basketball'
        ]) or 
        (any(path in url_lower for path in ['/coaches', '/staff', '/team', '/about', '/programs']) and
         any(sport in url_lower for sport in [
             'soccer', 'basketball', 'football', 'baseball', 'lacrosse', 'tennis',
             'volleyball', 'swimming', 'athletic', 'sports'
         ]))
    )
    if is_youth_sports:
        from .youth_sports import YouthSportsExtractor
        return YouthSportsExtractor()
    
    # No specific extractor - use generic
    return None


def extract_prospects_with_factory(
    content: str,
    url: str,
    source: ProspectSource,
    category: Optional[str] = None
) -> List[DiscoveredProspect]:
    """
    Extract prospects using the factory pattern.
    Automatically selects the right extractor based on URL patterns.
    """
    extractor = get_extractor_for_url(url, content, source, category)
    
    if extractor:
        logger.info(f"Using {extractor.__class__.__name__} for {url}")
        return extractor.extract(content, url, source, category)
    else:
        # Use generic extractor
        from .generic import GenericExtractor
        logger.info(f"Using GenericExtractor for {url}")
        generic = GenericExtractor()
        return generic.extract(content, url, source, category)

