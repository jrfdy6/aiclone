"""
Base extractor class with common functionality
"""
import re
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect, ProspectContact

from ..constants import CRED_PATTERN, GENERIC_EMAIL_PREFIXES, PROSPECT_CATEGORIES
from ..validators import is_valid_person_name
from ..organization_extractor import extract_organization
from ..scraping_utils import free_scrape

logger = logging.getLogger(__name__)


class BaseExtractor:
    """Base class for all prospect extractors"""
    
    def __init__(self):
        pass
    
    def extract(
        self,
        content: str,
        url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Main extraction method - subclasses must implement.
        
        This is a convenience wrapper that calls extract_prospects() which
        subclasses should implement with their specific logic.
        """
        return self.extract_prospects(content, url, {"source": source, "category": category})
    
    def extract_prospects(
        self,
        html: str,
        url: str,
        meta: Optional[Dict[str, Any]] = None
    ) -> List[DiscoveredProspect]:
        """
        Extract prospects from HTML content.
        Subclasses should override this method.
        """
        raise NotImplementedError("Subclasses must implement extract_prospects()")
    
    def can_handle(self, url: str) -> bool:
        """
        Check if this extractor can handle the given URL.
        Subclasses should override this method.
        """
        return False
    
    def extract_emails(self, content: str) -> List[str]:
        """Extract emails from content, including obfuscated ones"""
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        
        # Also find obfuscated emails
        obfuscated_pattern = r'([a-zA-Z0-9._%+-]+)\s*\[at\]\s*([a-zA-Z0-9.-]+)\s*\[dot\]\s*([a-zA-Z]{2,})'
        for match in re.findall(obfuscated_pattern, content, re.IGNORECASE):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
        
        obfuscated_pattern2 = r'([a-zA-Z0-9._%+-]+)\s*\(at\)\s*([a-zA-Z0-9.-]+)\s*\(dot\)\s*([a-zA-Z]{2,})'
        for match in re.findall(obfuscated_pattern2, content, re.IGNORECASE):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
        
        obfuscated_pattern3 = r'([a-zA-Z0-9._%+-]+)\s+AT\s+([a-zA-Z0-9.-]+)\s+DOT\s+([a-zA-Z]{2,})'
        for match in re.findall(obfuscated_pattern3, content):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
        
        # Filter invalid emails
        emails = [e for e in emails 
                  if not e.endswith(('.png', '.jpg', '.gif'))
                  and '@sentry' not in e.lower()
                  and not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
        return list(set(emails))  # Dedupe
    
    def extract_phones(self, content: str) -> List[str]:
        """Extract phone numbers from content"""
        phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content)
        return list(set(phones))  # Dedupe
    
    def validate_and_tag_prospect(
        self,
        name: str,
        category: Optional[str],
        default_specialty: Optional[str] = None
    ) -> Optional[List[str]]:
        """Validate name and return specialty tags"""
        if not is_valid_person_name(name):
            return None
        
        if category and category in PROSPECT_CATEGORIES:
            return [PROSPECT_CATEGORIES[category]["name"]]
        
        if default_specialty:
            return [default_specialty]
        
        return []
    
    def build_prospect(
        self,
        name: str,
        title: Optional[str] = None,
        org: Optional[str] = None,
        contact: Optional[Dict[str, Optional[str]]] = None,
        source_url: str = "",
        bio_snippet: Optional[str] = None,
        source: Optional[ProspectSource] = None,
        specialty: Optional[List[str]] = None,
        location: Optional[str] = None
    ) -> DiscoveredProspect:
        """
        Build a DiscoveredProspect from extracted data.
        Helper method for extractors to create prospect objects.
        """
        if not contact:
            contact = {"email": None, "phone": None, "website": None}
        
        if not source:
            source = ProspectSource.GENERAL_SEARCH
        
        return DiscoveredProspect(
            name=name,
            title=title,
            organization=org,
            specialty=specialty or [],
            location=location,
            source_url=source_url or "",
            source=source,
            contact=ProspectContact(
                email=contact.get("email"),
                phone=contact.get("phone"),
                website=contact.get("website"),
            ),
            bio_snippet=bio_snippet,
        )
    
    def make_partial_prospect(
        self,
        source_url: str,
        name: Optional[str] = None
    ) -> DiscoveredProspect:
        """
        Create a partial prospect with just source_url.
        Used when extractor finds a URL that needs to be scraped separately.
        """
        return DiscoveredProspect(
            name=name or "Unknown",
            title=None,
            organization=None,
            specialty=[],
            location=None,
            source_url=source_url,
            source=ProspectSource.GENERAL_SEARCH,
            contact=ProspectContact(),
            bio_snippet=None,
        )

