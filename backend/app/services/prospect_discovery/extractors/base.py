"""
Base extractor class with common functionality
"""
import re
import logging
from typing import List, Optional

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

