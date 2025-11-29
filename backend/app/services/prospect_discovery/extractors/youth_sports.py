"""
Youth sports extractor for coaches and program directors
"""
import re
import logging
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect

from .base import BaseExtractor
from .. import scraping_utils, validators, organization_extractor, constants

logger = logging.getLogger(__name__)

SPORTS_PATHS = ["/coaches", "/staff", "/team", "/programs", "/coaching-staff"]

ROLE_KEYWORDS = [
    "director", "head coach", "coach", "director of coaching",
    "athletic director", "operations director", "program manager"
]


class YouthSportsExtractor(BaseExtractor):
    """Extractor for youth sports organizations"""
    
    domain_keywords = ["academy", "sports", "club", "soccer", "basketball", "elite"]
    
    def can_handle(self, url: str) -> bool:
        return (any(k in url.lower() for k in self.domain_keywords) or 
                any(p in url.lower() for p in SPORTS_PATHS))
    
    def extract_prospects(self, html: str, url: str, meta: Optional[Dict[str, Any]] = None) -> List[DiscoveredProspect]:
        """Extract prospects from youth sports HTML"""
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
        
        # If it's a team/coaches page, parse cards
        cards = soup.select(".coach, .coach-card, .staff-member, .coach-list, .team-member")
        if cards:
            org = organization_extractor.extract_from_html(soup, url) or scraping_utils.domain_to_org(url)
            
            for c in cards:
                text = c.get_text(" ", strip=True)
                name = validators.find_name_in_text(text)
                
                if not name:
                    # Sometimes name in h3/h4 inside card
                    tag = c.select_one("h3, h4, .name")
                    if tag:
                        name = validators.find_name_in_text(tag.get_text(" ", strip=True))
                
                if not name or not validators.is_valid_person_name(name):
                    continue
                
                title = scraping_utils.extract_role_from_element(c, ROLE_KEYWORDS)
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
        
        # Fallback: search for coaching staff links
        links = scraping_utils.find_likely_team_pages(
            soup, url, extra_keywords=["coach", "coaching", "team", "programs"]
        )
        for l in links:
            prospects.append(self.make_partial_prospect(source_url=l))
        
        return prospects

