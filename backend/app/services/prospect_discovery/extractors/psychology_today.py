"""
Psychology Today extractor for therapist profiles and listings
"""
import re
import logging
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect

from .base import BaseExtractor
from .. import organization_extractor, scraping_utils, validators, constants

logger = logging.getLogger(__name__)

TEL_RE = re.compile(r'tel:\+?([\d\-\s().]+)', re.I)
PROFILE_PATH_RE = re.compile(r'/us/(therapists|psychiatrists)/[^/]+/\d+', re.I)


class PsychologyTodayExtractor(BaseExtractor):
    """Extractor for psychologytoday.com listing pages and profile pages."""
    
    domain = "psychologytoday.com"
    
    def can_handle(self, url: str) -> bool:
        return "psychologytoday.com" in url.lower()
    
    def extract_prospects(self, html: str, url: str, meta: Optional[Dict[str, Any]] = None) -> List[DiscoveredProspect]:
        """Extract prospects from Psychology Today HTML"""
        if not meta:
            meta = {}
        source = meta.get("source", ProspectSource.PSYCHOLOGY_TODAY)
        category = meta.get("category")
        
        soup = BeautifulSoup(html, "html.parser")
        prospects = []
        
        # If listing page, gather profile URLs
        if "/therapists/" in url.lower() or "/psychiatrists/" in url.lower():
            profile_links = set()
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if PROFILE_PATH_RE.search(href):
                    profile_links.add(scraping_utils.absolute_url(url, href))
            
            # If we found profile links, return partial prospects for orchestrator to scrape
            if profile_links:
                for purl in profile_links:
                    prospects.append(self.make_partial_prospect(source_url=purl))
                return prospects
        
        # If profile page, extract name, phone, website, creds
        # Name
        name_tag = soup.select_one("h1.provider-name, h1.profile-name, h1")
        name = None
        if name_tag:
            name = name_tag.get_text(strip=True)
        else:
            name = validators.find_name_in_text(soup.get_text(" ", strip=True))
        
        if not name:
            return prospects
        
        # Validate name
        if not validators.is_valid_person_name(name):
            logger.debug(f"Invalid name extracted from Psychology Today: {name}")
            return prospects
        
        # Credentials / title
        credentials = None
        cred_tag = soup.find(lambda t: t.name in ["p", "span", "div"] and t.get("class") and "credentials" in " ".join(t.get("class", [])).lower())
        if cred_tag:
            credentials = cred_tag.get_text(strip=True)
        else:
            sp = soup.select_one("span.credentials, span.title")
            if sp:
                credentials = sp.get_text(strip=True)
        
        # Phone - psychologytoday uses tel: links frequently
        phone = None
        tel = soup.select_one("a[href^='tel:']")
        if tel:
            phone_raw = tel.get("href", "")
            m = TEL_RE.search(phone_raw)
            if m:
                phone = validators.normalize_phone(m.group(1))
        
        # Website / practice
        website_url = None
        site_link = soup.select_one("a[href][data-qa='profile-website'], a[href].profile-website")
        if site_link:
            website_url = scraping_utils.absolute_url(url, site_link.get("href"))
        
        org = organization_extractor.extract_from_profile(soup, url)
        
        # Get specialty from category
        specialty = []
        if category and category in constants.PROSPECT_CATEGORIES:
            specialty = [constants.PROSPECT_CATEGORIES[category]["name"]]
        else:
            specialty = ["Psychologist"]  # Default
        
        prospect = self.build_prospect(
            name=name,
            title=credentials,
            org=org,
            contact={"email": None, "phone": phone, "website": website_url},
            source_url=url,
            source=source,
            specialty=specialty,
            bio_snippet=soup.get_text(" ", strip=True)[:400]
        )
        
        prospects.append(prospect)
        return prospects

