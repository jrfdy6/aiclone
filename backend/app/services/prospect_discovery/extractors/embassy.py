"""
Embassy extractor for education officers and cultural attachés
"""
import re
import logging
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect

from .base import BaseExtractor
from .. import scraping_utils, validators, organization_extractor, constants

logger = logging.getLogger(__name__)

EMB_PATHS = ["/education", "/cultural", "/culture", "/contact", "/staff", "/officers"]


class EmbassyExtractor(BaseExtractor):
    """Extractor for embassy/consulate websites"""
    
    domain_keywords = ["embassy", "consulate", ".gov", ".embassy."]
    
    def can_handle(self, url: str) -> bool:
        return any(k in url.lower() for k in self.domain_keywords) or ".embassy." in url.lower()
    
    def extract_prospects(self, html: str, url: str, meta: Optional[Dict[str, Any]] = None) -> List[DiscoveredProspect]:
        """Extract prospects from embassy HTML"""
        if not meta:
            meta = {}
        source = meta.get("source", ProspectSource.GENERAL_SEARCH)
        category = meta.get("category")
        
        soup = BeautifulSoup(html, "html.parser")
        prospects = []
        
        # Get specialty from category
        specialty = []
        if category and category in constants.PROSPECT_CATEGORIES:
            specialty = [constants.PROSPECT_CATEGORIES[category]["name"]]
        
        # Try structured table of officers
        for row in soup.select("table tr"):
            cells = [c.get_text(" ", strip=True) for c in row.select("td,th")]
            if not cells or len(cells) < 2:
                continue
            
            role_text = " ".join(cells[0:2]).lower()
            if any(k in role_text for k in ["education", "attach", "cultural", "public affairs", "education officer"]):
                name = validators.find_name_in_text(" ".join(cells))
                if not name or not validators.is_valid_person_name(name):
                    continue
                
                emails = validators.find_emails_in_text(" ".join(cells))
                phone = validators.find_phone_in_text(" ".join(cells))
                org = organization_extractor.extract_from_html(soup, url) or scraping_utils.domain_to_org(url)
                
                prospect = self.build_prospect(
                    name=name,
                    title=role_text.title(),
                    org=org,
                    contact={"email": emails[0] if emails else None, "phone": phone},
                    source_url=url,
                    source=source,
                    specialty=specialty,
                    bio_snippet=" ".join(cells)[:400]
                )
                prospects.append(prospect)
        
        # Try list / staff panels
        panels = soup.select(".staff, .officers, .team, .contact-list, .cultural-officers")
        for p in panels:
            for li in p.select("li, .officer, .person"):
                text = li.get_text(" ", strip=True)
                if not text:
                    continue
                
                if any(k in text.lower() for k in ["education", "attach", "cultural", "education officer", "cultural affairs"]):
                    name = validators.find_name_in_text(text)
                    if not name or not validators.is_valid_person_name(name):
                        continue
                    
                    emails = validators.find_emails_in_text(text)
                    phone = validators.find_phone_in_text(text)
                    org = organization_extractor.extract_from_html(soup, url) or scraping_utils.domain_to_org(url)
                    
                    prospect = self.build_prospect(
                        name=name,
                        title=None,
                        org=org,
                        contact={"email": emails[0] if emails else None, "phone": phone},
                        source_url=url,
                        source=source,
                        specialty=specialty,
                        bio_snippet=text[:400]
                    )
                    prospects.append(prospect)
        
        # Fallback: if no panels found, try contact page parsing
        if not prospects:
            contact_links = scraping_utils.find_contact_pages(soup, url)
            for link in contact_links:
                prospects.append(self.make_partial_prospect(source_url=link))
        
        return prospects

