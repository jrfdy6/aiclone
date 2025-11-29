"""
Base extractor class for prospect extraction
"""
import re
from typing import List, Optional
from abc import ABC, abstractmethod

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect, ProspectContact


class BaseExtractor(ABC):
    """Base class for all prospect extractors"""
    
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    
    @abstractmethod
    def extract(
        self,
        content: str,
        url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """Extract prospects from content"""
        pass
    
    def extract_emails(self, content: str) -> List[str]:
        """Extract email addresses from content"""
        emails = re.findall(self.EMAIL_PATTERN, content)
        # Filter out common false positives
        filtered = [
            email for email in emails
            if not email.startswith('example@') and 'noreply' not in email.lower()
        ]
        return list(set(filtered))  # Deduplicate
    
    def extract_phones(self, content: str) -> List[str]:
        """Extract phone numbers from content"""
        phones = re.findall(self.PHONE_PATTERN, content)
        return list(set(phones))  # Deduplicate

