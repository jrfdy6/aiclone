"""
Treatment center extractor for RTC/PHP/IOP programs
"""
import re
import logging
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect

from .base import BaseExtractor
from .. import scraping_utils, organization_extractor, validators, constants

logger = logging.getLogger(__name__)

ROLE_KEYWORDS = [
    "admissions director", "intake coordinator", "clinical director", "program director",
    "executive director", "chief clinical officer", "director of admissions", "intake manager"
]


class TreatmentCenterExtractor(BaseExtractor):
    """Extractor for treatment center websites"""
    
    domain_keywords = ["treatment", "rehab", "residential", "php", "iop", "wilderness"]
    
    def can_handle(self, url: str) -> bool:
        return any(k in url.lower() for k in self.domain_keywords) or "/treatment" in url.lower()
    
    def extract_prospects(self, html: str, url: str, meta: Optional[Dict[str, Any]] = None) -> List[DiscoveredProspect]:
        """Extract prospects from treatment center HTML"""
        if not meta:
            meta = {}
        source = meta.get("source", ProspectSource.GENERAL_SEARCH)
        category = meta.get("category")
        
        soup = BeautifulSoup(html, "html.parser")
        prospects = []
        
        # Detect team pages by path or by keywords
        if any(p in url.lower() for p in ["/team", "/staff", "/leadership", "/admissions", "/meet-the-team"]):
            prospects.extend(self._extract_from_team_page(soup, url, source, category))
            return prospects
        
        # Otherwise try to find links to team pages
        links = scraping_utils.find_likely_team_pages(soup, url)
        if links:
            for l in links:
                prospects.append(self.make_partial_prospect(source_url=l))
            return prospects
        
        # Fallback: try to extract single-contact info from main page
        name_candidates = validators.find_names_in_document(soup.get_text(" ", strip=True))
        org = organization_extractor.extract_from_html(soup, url)
        
        # Get specialty from category
        specialty = []
        if category and category in constants.PROSPECT_CATEGORIES:
            specialty = [constants.PROSPECT_CATEGORIES[category]["name"]]
        
        for name in name_candidates[:6]:
            if not validators.is_valid_person_name(name):
                continue
            
            # Search text region around name
            nearby = scraping_utils.find_text_block_near(soup, name)
            title = scraping_utils.extract_role_from_text(nearby, ROLE_KEYWORDS)
            phone = validators.find_phone_in_text(nearby)
            emails = validators.find_emails_in_text(nearby)
            
            prospect = self.build_prospect(
                name=name,
                title=title,
                org=org,
                contact={"email": emails[0] if emails else None, "phone": phone},
                source_url=url,
                source=source,
                specialty=specialty,
                bio_snippet=nearby[:400]
            )
            prospects.append(prospect)
        
        return prospects
    
    def _extract_from_team_page(
        self,
        soup: BeautifulSoup,
        url: str,
        source: ProspectSource,
        category: Optional[str]
    ) -> List[DiscoveredProspect]:
        """Extract prospects from team/staff page"""
        prospects = []
        
        # Common patterns: cards, rows
        card_selectors = [
            ".team-member", ".staff-member", ".staff .member", ".leadership .person", ".team-card"
        ]
        
        members = []
        for sel in card_selectors:
            members = soup.select(sel)
            if members:
                break
        
        # Fallback to heading-based extraction
        if not members:
            name_tags = soup.select("h3, h4, .member-name, .staff-name")
            for t in name_tags:
                members.append(t.parent if t.parent else t)
        
        org = organization_extractor.extract_from_html(soup, url)
        
        # Get specialty from category
        specialty = []
        if category and category in constants.PROSPECT_CATEGORIES:
            specialty = [constants.PROSPECT_CATEGORIES[category]["name"]]
        
        for m in members:
            text = m.get_text(" ", strip=True)
            name = validators.find_name_in_text(text)
            if not name or not validators.is_valid_person_name(name):
                continue
            
            title = scraping_utils.extract_role_from_element(m, ROLE_KEYWORDS)
            phone = validators.find_phone_in_text(text)
            emails = validators.find_emails_in_text(text)
            
            prospect = self.build_prospect(
                name=name,
                title=title,
                org=org,
                contact={"email": emails[0] if emails else None, "phone": phone},
                source_url=url,
                source=source,
                specialty=specialty,
                bio_snippet=text[:400]
            )
            prospects.append(prospect)
        
        return prospects

