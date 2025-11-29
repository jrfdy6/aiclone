"""
Doctor directory extractor (Healthgrades, Vitals, Zocdoc, etc.)
"""
import re
import logging
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect

from .base import BaseExtractor
from .. import scraping_utils, organization_extractor, validators, constants

logger = logging.getLogger(__name__)

PROFILE_RE = re.compile(r'/providers/[^/]+/\w+', re.I)
PHONE_ATTRS = ["data-qa-target", "itemprop"]


class DoctorDirectoryExtractor(BaseExtractor):
    """Extractor for doctor directory sites"""
    
    domain_keywords = ["healthgrades.com", "vitals.com", "zocdoc.com", "docspot.org"]
    
    def can_handle(self, url: str) -> bool:
        return any(k in url.lower() for k in self.domain_keywords)
    
    def extract_prospects(self, html: str, url: str, meta: Optional[Dict[str, Any]] = None) -> List[DiscoveredProspect]:
        """Extract prospects from doctor directory HTML"""
        if not meta:
            meta = {}
        source = meta.get("source", ProspectSource.GENERAL_SEARCH)
        category = meta.get("category")
        
        soup = BeautifulSoup(html, "html.parser")
        prospects = []
        
        # Directory listing: try JSON first (Next.js __NEXT_DATA__)
        json_profs = scraping_utils.extract_next_data_profile_urls(html, url)
        if json_profs:
            for p in json_profs:
                prospects.append(self.make_partial_prospect(source_url=p))
            return prospects
        
        # If directory listing, find relative profile links (fallback)
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if PROFILE_RE.search(href):
                prospects.append(self.make_partial_prospect(source_url=scraping_utils.absolute_url(url, href)))
        
        # If profile page: extract phone from data-qa-target or tel: link
        if not prospects:
            name = validators.find_name_in_text(soup.get_text(" ", strip=True))
            if not name or not validators.is_valid_person_name(name):
                return prospects
            
            phone = None
            # Common Healthgrades pattern: data-qa-target provider-phone
            phone_tag = soup.select_one('[data-qa-target="provider-phone"]') or soup.select_one("a[href^='tel:']")
            if phone_tag:
                if phone_tag.name == "a" and phone_tag.get("href", "").startswith("tel:"):
                    phone = validators.normalize_phone(phone_tag.get("href").replace("tel:", ""))
                else:
                    phone = validators.find_phone_in_text(phone_tag.get_text(" ", strip=True))
            
            org = organization_extractor.extract_from_profile(soup, url)
            
            # Get specialty from category
            specialty = []
            if category and category in constants.PROSPECT_CATEGORIES:
                specialty = [constants.PROSPECT_CATEGORIES[category]["name"]]
            else:
                specialty = ["Doctor"]  # Default
            
            prospect = self.build_prospect(
                name=name,
                title=None,
                org=org,
                contact={"email": None, "phone": phone},
                source_url=url,
                source=source,
                specialty=specialty,
                bio_snippet=soup.get_text(" ", strip=True)[:400]
            )
            prospects.append(prospect)
        
        return prospects

