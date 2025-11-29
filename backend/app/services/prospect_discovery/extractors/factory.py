"""
Factory for selecting the appropriate extractor based on source and category
"""
from typing import List, Optional

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect
from .generic import GenericExtractor


# Map of sources to their specific extractors (if they exist)
SOURCE_EXTRACTOR_MAP = {
    # Add specific extractors here as they are implemented
    # ProspectSource.PSYCHOLOGY_TODAY: PsychologyTodayExtractor,
    # ProspectSource.TREATMENT_CENTERS: TreatmentCenterExtractor,
}


def extract_prospects_with_factory(
    content: str,
    url: str,
    source: ProspectSource,
    category: Optional[str] = None
) -> List[DiscoveredProspect]:
    """
    Factory function to select and use the appropriate extractor.
    
    Args:
        content: HTML/text content to extract from
        url: Source URL
        source: Type of source
        category: Optional category to help with extraction
        
    Returns:
        List of discovered prospects
    """
    # Try to get a specific extractor for this source
    extractor_class = SOURCE_EXTRACTOR_MAP.get(source)
    
    # If no specific extractor, use the generic one
    if extractor_class is None:
        extractor_class = GenericExtractor
    
    # Instantiate and use the extractor
    extractor = extractor_class()
    prospects = extractor.extract(
        content=content,
        url=url,
        source=source,
        category=category
    )
    
    return prospects

