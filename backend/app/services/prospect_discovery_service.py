"""
Prospect Discovery Service - v2.1 (Fixed name filtering)

Universal prospect discovery for K-12 decision influencers:
- Medical: Pediatricians, psychologists, psychiatrists, treatment centers
- Diplomatic: Embassy education officers, cultural attachés  
- Sports: Athletic academy directors, elite youth coaches
- Community: Mom group leaders, parenting coaches, youth program directors
- Education: Consultants, school counselors, admissions staff
"""

import logging
import time
import re
import json
import requests
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from app.models.prospect_discovery import (
    ProspectSource,
    SOURCE_DORKS,
    DiscoveredProspect,
    ProspectContact,
    ProspectDiscoveryRequest,
    ProspectDiscoveryResponse,
)
from app.services.firecrawl_client import get_firecrawl_client
from app.services.perplexity_client import get_perplexity_client
from app.services.search_client import get_search_client
from app.services.firestore_client import db
from app.services.prospect_discovery.extractors.factory import extract_prospects_with_factory
from app.services.prospect_discovery.extractors.factory import extract_prospects_with_factory

logger = logging.getLogger(__name__)

# =============================================================================
# UNIVERSAL CREDENTIALS & TITLES (Layer 1)
# =============================================================================

CREDENTIALS = [
    # Medical
    "MD", "DO", "PhD", "PsyD", "LCSW", "LMFT", "LPC", "NP", "RN", "LMHC", "LCPC",
    "Pediatrician", "Psychiatrist", "Psychologist", "Neuropsychologist",
    # Treatment/Admin
    "Director", "Admin", "Admissions", "Clinical Director", "Program Director",
    "Executive Director", "Administrator", "Manager", "Coordinator",
    # Education
    "CEP", "IEC", "IECA", "MEd", "EdD", "MA", "MS", "MBA", "MSW",
    "Counselor", "Consultant", "Advisor", "Coach", "Specialist",
    # Leadership
    "Founder", "President", "Chair", "Owner", "Principal", "Leader",
    # Embassy/Diplomatic
    "Ambassador", "Attaché", "Consul", "Officer", "Diplomat",
]

CRED_PATTERN = "|".join(re.escape(c) for c in CREDENTIALS)

# =============================================================================
# PROSPECT CATEGORIES
# =============================================================================

PROSPECT_CATEGORIES = {
    "education_consultants": {
        "name": "Education Consultants",
        "keywords": ["educational consultant", "college counselor", "IEC", "IECA", "CEP", "school placement"],
        "search_terms": ["educational consultant", "independent education consultant", "college counselor"],
    },
    "pediatricians": {
        "name": "Pediatricians",
        "keywords": ["pediatrician", "pediatric", "child doctor", "adolescent medicine"],
        "search_terms": ["pediatrician adolescent", "pediatric practice", "child doctor"],
    },
    "psychologists": {
        "name": "Psychologists & Psychiatrists",
        "keywords": ["psychologist", "psychiatrist", "therapist", "mental health", "child psychology"],
        "search_terms": ["child psychologist", "adolescent psychiatrist", "family therapist"],
    },
    "psychologists_psychiatrists": {
        "name": "Psychologists & Psychiatrists",
        "keywords": ["psychologist", "psychiatrist", "therapist", "mental health", "child psychology"],
        "search_terms": ["child psychologist", "adolescent psychiatrist", "family therapist"],
    },
    "treatment_centers": {
        "name": "Treatment Centers",
        "keywords": ["treatment center", "residential treatment", "therapeutic", "rehab", "admissions"],
        "search_terms": ["treatment center admissions", "residential treatment adolescent", "therapeutic boarding"],
    },
    "embassies": {
        "name": "Embassies & Diplomats",
        "keywords": ["embassy", "diplomat", "cultural officer", "education attaché", "consulate"],
        "search_terms": ["embassy education officer", "cultural affairs", "diplomatic family services"],
    },
    "youth_sports": {
        "name": "Youth Sports Programs",
        "keywords": ["athletic academy", "sports academy", "elite athlete", "youth sports", "travel team"],
        "search_terms": ["athletic academy director", "elite youth sports", "sports academy high school"],
    },
    "mom_groups": {
        "name": "Mom Groups & Parent Networks",
        "keywords": ["mom group", "parent network", "PTA", "family", "parenting coach"],
        "search_terms": ["mom group leader", "parent network", "family services"],
    },
    "international_students": {
        "name": "International Student Services",
        "keywords": ["international student", "ESL", "foreign student", "visa", "host family"],
        "search_terms": ["international student services", "foreign student placement", "host family coordinator"],
    },
    # Category name variations (for frontend compatibility - these map to base categories)
    "embassies_diplomats": {
        "name": "Embassies & Diplomats",
        "keywords": ["embassy", "diplomat", "cultural officer", "education attaché", "consulate"],
        "search_terms": ["embassy education officer", "cultural affairs", "diplomatic family services"],
    },
    "youth_sports_programs": {
        "name": "Youth Sports Programs",
        "keywords": ["athletic academy", "sports academy", "elite athlete", "youth sports", "travel team"],
        "search_terms": ["athletic academy director", "elite youth sports", "sports academy high school"],
    },
    "mom_groups_parent_networks": {
        "name": "Mom Groups & Parent Networks",
        "keywords": ["mom group", "parent network", "PTA", "family", "parenting coach"],
        "search_terms": ["mom group leader", "parent network", "family services"],
    },
    "international_student_services": {
        "name": "International Student Services",
        "keywords": ["international student", "ESL", "foreign student", "visa", "host family"],
        "search_terms": ["international student services", "foreign student placement", "host family coordinator"],
    },
}

# =============================================================================
# DC AREA LOCATION VARIATIONS
# =============================================================================

DC_AREA_VARIATIONS = [
    "Washington DC", "DC", "D.C.", "DMV", "NOVA", "Northern Virginia",
    "Montgomery County", "Fairfax", "Arlington", "Bethesda", "Silver Spring",
    "Alexandria", "Chevy Chase", "Georgetown", "Capitol Hill", "Potomac",
    "McLean", "Tysons", "Rockville", "College Park", "Prince George"
]

# DC Neighborhoods - These are valid location names that should NOT be filtered
# Even though they contain location words, they are legitimate place names
DC_NEIGHBORHOODS = [
    "Capitol Heights", "Adams Morgan", "Anacostia", "Barry Farm", "Bellevue",
    "Benning", "Bloomingdale", "Brightwood", "Brookland", "Burleith",
    "Capitol Hill", "Chevy Chase", "Chinatown", "Columbia Heights", "Congress Heights",
    "Crestwood", "Deanwood", "Dupont Circle", "Eckington", "Edgewood",
    "Foggy Bottom", "Fort Totten", "Foxhall", "Friendship Heights", "Garfield Heights",
    "Georgetown", "Glover Park", "H Street", "Hillcrest", "Ivy City",
    "Kalorama", "Kenilworth", "Kingman Park", "Lamond Riggs", "LeDroit Park",
    "Logan Circle", "Manor Park", "Marshall Heights", "Massachusetts Heights", "Mayfair",
    "Mount Pleasant", "Navy Yard", "NoMa", "North Cleveland Park", "Northwest",
    "Palisades", "Park View", "Penn Branch", "Petworth", "Potomac Heights",
    "Randall Heights", "River Terrace", "Shaw", "Shepherd Park", "Southeast",
    "Southwest", "Stanton Park", "Takoma", "Tenleytown", "The Palisades",
    "Trinidad", "Truxton Circle", "Twining", "Union Heights", "Union Station",
    "U Street", "Washington Heights", "Wesley Heights", "West End", "Woodley Park",
    "Woodridge", "Woodland", "Woodland Terrace"
]

DC_LOCATION_QUERY = '("Washington DC" OR "DC" OR "DMV" OR "NOVA" OR "Montgomery County" OR "Fairfax" OR "Arlington" OR "Bethesda")'

# Generic email prefixes to filter out
GENERIC_EMAIL_PREFIXES = ['info', 'contact', 'support', 'hello', 'admin', 'sales', 
                          'help', 'office', 'mail', 'enquiries', 'inquiries', 'noreply',
                          'webmaster', 'newsletter', 'team', 'careers', 'jobs']

# Domains that can't be scraped or block bots
BLOCKED_DOMAINS = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com', 
                   'youtube.com', 'tiktok.com', 'pinterest.com', 'glassdoor.com',
                   'indeed.com', 'iecaonline.com']  # These block scraping


class ProspectDiscoveryService:
    """Service for discovering prospects from public directories"""
    
    def __init__(self):
        self.firecrawl = None
        self.perplexity = None
        self.google_search = None
    
    def _init_clients(self):
        """Lazy init clients"""
        if self.firecrawl is None:
            try:
                self.firecrawl = get_firecrawl_client()
            except Exception as e:
                logger.warning(f"Firecrawl client not available: {e}")
                self.firecrawl = None
        if self.perplexity is None:
            try:
                self.perplexity = get_perplexity_client()
            except:
                self.perplexity = None
        if self.google_search is None:
            try:
                self.google_search = get_search_client()
            except:
                self.google_search = None
    
    def _is_valid_person_name(self, name: str) -> bool:
        """Check if name looks like a real person name. Used during extraction to filter garbage names."""
        name_lower = name.lower()
        words = name.split()
        
        # Must be exactly 2-3 words
        if len(words) < 2 or len(words) > 3:
            return False
        
        # Bad name words (from extract_prospects_from_content)
        bad_name_words = [
            'educational', 'administrative', 'outreach', 'experience', 'engagement',
            'customer', 'patient', 'human', 'service', 'services', 'standardized',
            'test', 'prep', 'head', 'start', 'reviewer', 'board', 'college',
            'resources', 'featured', 'guidance', 'admissions', 'tutoring', 'academic',
            'available', 'advising', 'member', 'independent', 'county', 'montgomery',
            'tedeschi', 'marks', 'education', 'consultant', 'consulting', 'group',
            'center', 'institute', 'foundation', 'association', 'program', 'school',
            'academy', 'learning', 'development', 'training', 'coaching', 'support',
            'help', 'how', 'can', 'you', 'your', 'child', 'contact', 'phone', 'number',
            'email', 'address', 'click', 'here', 'read', 'more', 'learn', 'about',
            'options', 'certified', 'planner', 'risk', 'lines', 'personal', 'day',
            'schools', 'what', 'why', 'when', 'where', 'our', 'the', 'and', 'for',
            'with', 'this', 'that', 'from', 'have', 'been', 'will', 'would', 'could',
            'should', 'their', 'there', 'which', 'other', 'some', 'many', 'most',
            'free', 'best', 'top', 'new', 'first', 'last', 'next', 'back', 'home',
            'page', 'site', 'web', 'online', 'info', 'information', 'details',
            'submit', 'send', 'get', 'find', 'search', 'browse', 'view', 'see',
            'call', 'today', 'now', 'schedule', 'book', 'appointment', 'meeting',
            'areas', 'cities', 'bethesda', 'north', 'south', 'east', 'west',
            'endorsed', 'endorsement', 'good', 'afternoon', 'morning', 'evening',
            'afternoon', 'royalty', 'institute', 'where', 'children', 'come', 'first',
            'powered', 'by', 'engineers', 'united', 'states', 'janak'
        ]
        
        # No bad words (check each word individually)
        for word in words:
            if word.lower() in bad_name_words:
                return False
        
        # Each word should be 2-12 chars
        if not all(2 <= len(w.replace('.', '')) <= 12 for w in words):
            return False
        
        # Additional non-name words
        common_non_names = ['internet', 'licensed', 'professional', 'clinical', 'certified',
                            'registered', 'national', 'american', 'eclectic', 'compassion',
                            'focused', 'cognitive', 'behavioral', 'mental', 'health',
                            'therapists', 'therapist', 'family', 'adult', 'couples',
                            'marriage', 'anxiety', 'depression', 'trauma', 'addiction']
        
        # First word shouldn't be a common non-name
        if words[0].lower() in common_non_names:
            return False
        
        # Role words
        role_words = ['therapist', 'counselor', 'psychologist', 'psychiatrist', 'coach',
                      'specialist', 'consultant', 'advisor', 'director', 'manager', 'worker',
                      'nurse', 'practitioner', 'physician', 'doctor', 'md', 'np']
        
        # Last word shouldn't be a role
        if words[-1].lower() in role_words:
            return False
        
        # Filter famous people (quotes/testimonials)
        famous_names = ['maya angelou', 'martin luther', 'oprah winfrey', 'barack obama']
        if name_lower in famous_names:
            return False
        
        # Filter job titles that look like names
        job_titles = ['social worker', 'case manager', 'program director', 'clinical director',
                     'nurse practitioner', 'nurse', 'practitioner', 'physician assistant']
        if name_lower in job_titles:
            return False
        
        # Filter location/direction words that aren't names
        location_direction_words = ['north', 'south', 'east', 'west', 'areas', 'cities', 
                                   'county', 'montgomery', 'bethesda', 'arlington']
        if any(w.lower() in location_direction_words for w in words):
            return False
        
        # Filter common phrases
        common_phrases = ['good afternoon', 'good morning', 'good evening', 'thank you',
                         'click here', 'read more', 'learn more', 'contact us']
        if name_lower in common_phrases:
            return False
        
        # Filter names that look like sentences/phrases
        phrase_words = ['good', 'afternoon', 'morning', 'evening', 'endorsed', 
                       'endorsement', 'powered', 'by', 'engineers', 'where', 
                       'children', 'come', 'first']
        if any(w.lower() in phrase_words for w in words):
            return False
        
        # First and last words should start with capital letters (proper names)
        if not (words[0] and words[0][0].isupper() and words[-1] and words[-1][0].isupper()):
            return False
        
        return True
    
    def _free_scrape(self, url: str) -> Optional[str]:
        """Free scraping fallback using requests + BeautifulSoup"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            
            return text[:50000]  # Limit to 50k chars
        except Exception as e:
            logger.warning(f"Free scrape failed for {url}: {e}")
            return None
    
    def _extract_organization(self, content: str, url: str) -> Optional[str]:
        """
        Extract organization name from multiple sources (comprehensive extraction).
        
        Sources checked (in order of priority):
        1. Meta tags (og:site_name, organization)
        2. Page title (with cleanup)
        3. Header sections (h1, h2)
        4. Breadcrumbs
        5. Domain name (as fallback)
        6. Content patterns (Practice Name, Center Name, etc.)
        """
        from urllib.parse import urlparse
        
        # Template/footer phrases to filter out (NOT organization names)
        template_phrases = [
            'powered by', 'built with', 'designed by', 'created by',
            'all rights reserved', 'copyright', 'privacy policy',
            'terms of service', 'cookie policy', 'sitemap',
            'is powered by', 'is built with', 'is designed by',
            'where children come first', 'in the united states',
            'in united states', 'the united states', 'in the us'
        ]
        
        def is_valid_organization(org: str) -> bool:
            """Check if organization name looks valid (not template/footer text)"""
            org_lower = org.lower().strip()
            org_words = org.split()
            
            # Filter template phrases
            if any(phrase in org_lower for phrase in template_phrases):
                return False
            
            # Filter sentence patterns (not organization names)
            sentence_patterns = [
                'may also be', 'are also known', 'can also', 'will also',
                'is also', 'and hospital', 'pediatricians may', 'psychologists may',
                'may also be known', 'are also known as', 'by the following'
            ]
            if any(pattern in org_lower for pattern in sentence_patterns):
                return False
            
            # Filter organizations with too many words (likely sentences)
            if len(org_words) > 6:  # 7+ words is suspicious for an org name
                return False
            
            # Check if organization IS a template phrase (exact match)
            if org_lower in ['where children come first', 'in the united states', 
                            'in united states', 'the united states', 'in the us']:
                return False
            # Filter common website phrases
            if any(phrase in org_lower for phrase in ['click here', 'read more', 'learn more']):
                return False
            # Filter location-only names
            if org_lower in ['bethesda', 'arlington', 'montgomery county', 'north bethesda']:
                return False
            # Filter generic words
            if org_lower in ['areas', 'cities', 'endorsed', 'endorsement']:
                return False
            # Filter directory/aggregator sites (not actual organizations)
            directory_sites = ['psychologytoday', 'psychology today', 'healthgrades', 'webmd', 
                             'zocdoc', 'vitals', 'ratemds', 'doctor.com', 'pmc', 'ncbi',
                             'callsource', 'indeed', 'glassdoor', 'linkedin']
            if org_lower in directory_sites or any(ds in org_lower for ds in directory_sites):
                return False
            return True
        
        # Source 1: Meta tags (most reliable)
        meta_patterns = [
            r'<meta\s+property=["\']og:site_name["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+property=["\']organization["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+name=["\']application-name["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+itemprop=["\']name["\']\s+content=["\']([^"\']+)["\']',
        ]
        
        for pattern in meta_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                org = match.group(1).strip()
                # Clean up
                org = re.sub(r'\s*-\s*(Home|Page|Welcome|Official).*', '', org, flags=re.I)
                if org and len(org) > 2 and len(org) < 100 and is_valid_organization(org):
                    return org[:100]
        
        # Source 2: Page title (with intelligent cleanup)
        title_match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Remove common suffixes
            title = re.sub(r'\s*[-|]\s*(Home|Page|Welcome|Official|About|Contact).*', '', title, flags=re.I)
            # Remove site-specific suffixes
            title = re.sub(r'\s*[-|]\s*(Psychology Today|Healthgrades|WebMD|Zocdoc).*', '', title, flags=re.I)
            # Clean up extra spaces
            title = re.sub(r'\s+', ' ', title).strip()
            
            if title and len(title) > 2 and len(title) < 100:
                # Skip generic titles and validate
                if not re.match(r'^(Home|Page|Welcome|About|Contact|Error|404)$', title, re.I) and is_valid_organization(title):
                    return title[:100]
        
        # Source 3: Header sections (h1, h2) - often contain practice/center names
        header_patterns = [
            r'<h1[^>]*>([^<]{5,80})</h1>',
            r'<h2[^>]*>([^<]{5,80})</h2>',
        ]
        
        for pattern in header_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                text = match.strip()
                # Skip generic headers
                if not re.match(r'^(Home|About|Contact|Services|Team|Welcome|Our|The)$', text, re.I):
                    # Check if it looks like an organization name (2-5 words, capitalized)
                    words = text.split()
                    if 2 <= len(words) <= 5:
                        # Check if mostly capitalized (organization-like) and valid
                        if sum(1 for w in words if w and w[0].isupper()) >= len(words) * 0.6 and is_valid_organization(text):
                            return text[:100]
        
        # Source 4: Content patterns (Practice Name, Center Name, etc.)
        content_patterns = [
            r'Practice Name[:\s]+([A-Z][a-zA-Z\s]{5,60})',
            r'Center Name[:\s]+([A-Z][a-zA-Z\s]{5,60})',
            r'Organization[:\s]+([A-Z][a-zA-Z\s]{5,60})',
            r'Clinic[:\s]+([A-Z][a-zA-Z\s]{5,60})',
            r'Located at[:\s]+([A-Z][a-zA-Z\s]{5,60})',
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                org = match.group(1).strip()
                if org and len(org) > 5 and len(org) < 100 and is_valid_organization(org):
                    return org[:100]
        
        # Source 5: Domain name (fallback)
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            # Extract meaningful part of domain
            domain_parts = domain.split('.')
            if len(domain_parts) >= 2:
                main_part = domain_parts[0]
                # Skip generic domains
                if main_part not in ['site', 'www', 'home', 'main']:
                    # Clean up and capitalize
                    org_name = main_part.replace('-', ' ').title()
                    return org_name
        except:
            pass
        
        return None
    
    def build_search_query(
        self,
        source: ProspectSource,
        specialty: Optional[str] = None,
        location: Optional[str] = None,
        keywords: List[str] = None
    ) -> str:
        """Build a search query for the given source and filters"""
        dorks = SOURCE_DORKS.get(source, SOURCE_DORKS[ProspectSource.GENERAL_SEARCH])
        
        # Use first dork as template
        query = dorks[0] if dorks else '"{specialty}" "{location}"'
        
        # Replace placeholders
        query = query.replace("{specialty}", specialty or "")
        query = query.replace("{location}", location or "")
        
        # Add keywords
        if keywords:
            query += " " + " ".join(f'"{kw}"' for kw in keywords)
        
        # Clean up empty quotes
        query = query.replace('""', "").strip()
        query = re.sub(r'\s+', ' ', query)
        
        return query
    
    def extract_prospects_from_content(
        self,
        content: str,
        url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Extract prospect information from scraped content using the extractor factory.
        
        This method routes to the appropriate extractor based on URL patterns:
        - Psychology Today → PsychologyTodayExtractor
        - Doctor directories → DoctorDirectoryExtractor
        - Treatment centers → TreatmentCenterExtractor
        - Embassies → EmbassyExtractor
        - Youth sports → YouthSportsExtractor
        - All others → GenericExtractor
        
        Args:
            content: HTML content to extract from
            url: Source URL
            source: Prospect source type
            category: Category ID (e.g., 'pediatricians', 'psychologists') - if provided,
                     prospects will be tagged with this category instead of auto-detection
        
        Returns:
            List of DiscoveredProspect objects
        """
        logger.info(f"[EXTRACTION START] URL: {url} | Category: {category} | Source: {source}")
        
        try:
            # Use factory pattern to auto-select the correct extractor
            prospects = extract_prospects_with_factory(
                content=content,
                url=url,
                source=source,
                category=category
            )
            
            logger.info(f"[EXTRACTION COMPLETE] URL: {url} | Found {len(prospects)} prospects")
            
            # Handle partial prospects (for 2-hop scraping)
            # If extractor returns prospects with just source_url, they need further scraping
            partial_prospects = [p for p in prospects if not p.name or p.name == "Unknown"]
            full_prospects = [p for p in prospects if p not in partial_prospects]
            
            if partial_prospects:
                logger.info(f"[EXTRACTION] Found {len(partial_prospects)} partial prospects (profile URLs) for 2-hop scraping")
                # Return both - orchestrator should handle 2-hop scraping if needed
                return prospects
            
            return full_prospects if full_prospects else prospects
            
        except Exception as e:
            logger.error(f"[EXTRACTION ERROR] Failed to extract prospects from {url}: {e}", exc_info=True)
            # Fallback to empty list on error
            return []
    
    def _extract_psychology_today(
        self,
        content: str,
        url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """Extract prospects specifically from Psychology Today pages"""
        prospects = []
        
        # Psychology Today profile pattern: Name, Credentials on one line
        # Example: "John Smith, PhD, LCSW" or "Dr. Jane Doe"
        profile_patterns = [
            # Name with credentials
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s+((?:PhD|PsyD|LCSW|LMFT|LPC|MEd|MA|MS|EdD|MD|NCC|LCPC|LMHC)(?:,?\s*(?:PhD|PsyD|LCSW|LMFT|LPC|MEd|MA|MS|EdD|MD|NCC|LCPC|LMHC))*)',
            # Dr. prefix
            r'Dr\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]
        
        names_with_creds = []
        for pattern in profile_patterns:
            found = re.findall(pattern, content)
            for match in found:
                if isinstance(match, tuple):
                    names_with_creds.append({"name": match[0], "credentials": match[1] if len(match) > 1 else ""})
                else:
                    names_with_creds.append({"name": match, "credentials": ""})
        
        # Phone extraction
        phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content)
        phones = list(set(phones))  # Dedupe
        
        # Extract specialties mentioned
        specialty_keywords = [
            "educational consultant", "school", "learning", "ADHD", "autism",
            "adolescent", "child", "family", "college", "academic"
        ]
        
        # Location from URL or content
        location = None
        if "district-of-columbia" in url or "washington-dc" in url:
            location = "Washington, DC"
        else:
            loc_match = re.search(r'/therapists/([a-z-]+)', url)
            if loc_match:
                location = loc_match.group(1).replace("-", " ").title()
        
        # Filter to likely real names (not navigation elements)
        skip_words = ["marriage", "eating", "career", "life", "couples", "drug", "substance", 
                      "behavioral", "mental", "treatment", "counseling", "therapy", "disorders",
                      "coaching", "health", "care", "network", "center", "abuse"]
        
        seen_names = set()
        for item in names_with_creds:
            name = item["name"].strip()
            name_lower = name.lower()
            
            # Skip if it's a navigation/category term
            if any(skip in name_lower for skip in skip_words):
                continue
            
            # Skip if too short or already seen
            if len(name) < 5 or name in seen_names:
                continue
            
            # Skip if it looks like a title/header
            if name.isupper() or name.count(" ") > 3:
                continue
            
            # Apply strict name validation (same as save-time validation)
            if not self._is_valid_person_name(name):
                logger.debug(f"[CATEGORY: {category}] Filtering invalid name in extraction: {name}")
                continue
                
            seen_names.add(name)
            
            # Use category for tagging if provided, otherwise auto-detect
            specialty = []
            if category and category in PROSPECT_CATEGORIES:
                specialty = [PROSPECT_CATEGORIES[category]["name"]]
                logger.info(f"[CATEGORY: {category}] Tagging prospect '{name}' with category: {specialty[0]}")
            else:
                # Fallback: Find specialties in nearby content
                found_specialties = []
                for kw in specialty_keywords:
                    if kw.lower() in content.lower():
                        found_specialties.append(kw)
                specialty = found_specialties[:3]
            
            # Find phone near this name (within 500 chars)
            phone = None
            name_pos = content.find(name)
            if name_pos != -1:
                nearby_content = content[max(0, name_pos-250):name_pos+250]
                nearby_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby_content)
                if nearby_phones:
                    phone = nearby_phones[0]
            
            # Use first phone if no nearby phone found
            if not phone and phones:
                phone = phones[0]
            
            prospect = DiscoveredProspect(
                name=name,
                title=item.get("credentials") or "Therapist",
                organization=None,
                specialty=specialty,
                location=location,
                source_url=url,
                source=source,
                contact=ProspectContact(
                    phone=phone,
                ),
                bio_snippet=None,
            )
            prospects.append(prospect)
            
            if len(prospects) >= 10:  # Limit per page
                break
        
        return prospects
    
    def _extract_profile_urls_from_json(self, html_content: str, base_url: str) -> List[str]:
        """
        Extract doctor profile URLs from Next.js __NEXT_DATA__ JSON.
        Healthgrades embeds profile data in <script id="__NEXT_DATA__"> tags.
        """
        from urllib.parse import urljoin
        
        profile_urls = []
        
        try:
            # Find the __NEXT_DATA__ script tag
            json_match = re.search(
                r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
                html_content,
                re.DOTALL | re.IGNORECASE
            )
            
            if not json_match:
                return []
            
            json_str = json_match.group(1).strip()
            data = json.loads(json_str)
            
            # Navigate through Next.js data structure
            # Healthgrades structure: props.pageProps.searchResults or similar
            def find_profile_urls(obj, path=""):
                """Recursively search for profile URLs in JSON"""
                urls = []
                
                if isinstance(obj, dict):
                    # Check for profileUrl or profile_url keys
                    if 'profileUrl' in obj:
                        url = obj['profileUrl']
                        if url and isinstance(url, str) and ('/provider/' in url.lower() or '/doctor/' in url.lower()):
                            if not url.startswith('http'):
                                url = urljoin(base_url, url)
                            urls.append(url)
                    elif 'profile_url' in obj:
                        url = obj['profile_url']
                        if url and isinstance(url, str) and ('/provider/' in url.lower() or '/doctor/' in url.lower()):
                            if not url.startswith('http'):
                                url = urljoin(base_url, url)
                            urls.append(url)
                    
                    # Also check searchResults arrays
                    if 'searchResults' in obj and isinstance(obj['searchResults'], list):
                        for item in obj['searchResults']:
                            urls.extend(find_profile_urls(item, path + ".searchResults"))
                    
                    # Recurse into nested objects (limit depth to avoid infinite loops)
                    if len(path.split('.')) < 10:  # Limit recursion depth
                        for key, value in obj.items():
                            if key not in ['profileUrl', 'profile_url']:  # Skip already checked
                                urls.extend(find_profile_urls(value, path + f".{key}"))
                
                elif isinstance(obj, list):
                    for item in obj:
                        urls.extend(find_profile_urls(item, path + "[]"))
                
                return urls
            
            profile_urls = find_profile_urls(data)
            
            # Also try direct path access for common structures
            try:
                if 'props' in data and 'pageProps' in data['props']:
                    page_props = data['props']['pageProps']
                    if 'searchResults' in page_props:
                        for result in page_props['searchResults']:
                            if 'profileUrl' in result:
                                url = result['profileUrl']
                                if not url.startswith('http'):
                                    url = urljoin(base_url, url)
                                profile_urls.append(url)
            except:
                pass
            
            # Dedupe
            profile_urls = list(set(profile_urls))
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse __NEXT_DATA__ JSON: {e}")
        except Exception as e:
            logger.warning(f"Error extracting profile URLs from JSON: {e}")
        
        return profile_urls
    
    def _extract_doctor_directory(
        self,
        directory_content: str,
        directory_url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        2-hop extraction for doctor directories (Healthgrades, Zocdoc, Vitals):
        Step 1: Extract profile URLs from directory page
        Step 2: Scrape each profile page to get contact info
        Step 3: If no email, try practice website
        """
        prospects = []
        
        # Extract profile URLs from directory page
        from urllib.parse import urljoin, urlparse
        parsed = urlparse(directory_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        profile_urls = []
        
        # STEP 1: Try JSON extraction (works for some sites with embedded JSON)
        # Note: Healthgrades directory pages are JS-rendered, so profile URLs may not be in HTML
        # In that case, we'll extract names and use Google contact enrichment (implemented separately)
        url_lower = directory_url.lower()
        if 'healthgrades.com' in url_lower:
            json_urls = self._extract_profile_urls_from_json(directory_content, base_url)
            if json_urls:
                profile_urls.extend(json_urls)
                logger.info(f"Extracted {len(json_urls)} profile URLs from JSON")
        
        # Also try for other sites
        if not profile_urls and any(site in url_lower for site in ['zocdoc.com', 'webmd.com', 'doctor.com']):
            json_urls = self._extract_profile_urls_from_json(directory_content, base_url)
            if json_urls:
                profile_urls.extend(json_urls)
                logger.info(f"Extracted {len(json_urls)} profile URLs from JSON")
        
        # STEP 2: Fallback to regex patterns if JSON didn't work
        if not profile_urls:
            profile_patterns = []
            
            if 'healthgrades.com' in url_lower:
                profile_patterns = [r'href=["\']([^"\']*\/doctor\/[^"\']+)']
            elif 'zocdoc.com' in url_lower:
                profile_patterns = [r'href=["\']([^"\']*\/doctors\/[^"\']+)', r'href=["\']([^"\']*\/doctor\/[^"\']+)']
            elif 'vitals.com' in url_lower:
                profile_patterns = [r'href=["\']([^"\']*\/provider\/[^"\']+)']
            elif 'doctor.com' in url_lower:
                profile_patterns = [r'href=["\']([^"\']*\/doctor\/[^"\']+)', r'href=["\']([^"\']*\/doctors\/[^"\']+)']
            elif 'webmd.com' in url_lower:
                profile_patterns = [r'href=["\']([^"\']*\/doctor\/[^"\']+)', r'href=["\']([^"\']*\/find-a-doctor\/[^"\']+)']
            elif 'ratemds.com' in url_lower:
                profile_patterns = [r'href=["\']([^"\']*\/doctor\/[^"\']+)', r'href=["\']([^"\']*\/ratings\/[^"\']+)']
            else:
                # Generic patterns
                profile_patterns = [
                    r'href=["\']([^"\']*\/doctor\/[^"\']+)',
                    r'href=["\']([^"\']*\/doctors\/[^"\']+)',
                    r'href=["\']([^"\']*\/provider\/[^"\']+)',
                ]
            
            # Extract URLs using regex patterns
            regex_urls = []
            for pattern in profile_patterns:
                matches = re.findall(pattern, directory_content, re.IGNORECASE)
                for match in matches:
                    if match.startswith('http'):
                        regex_urls.append(match)
                    else:
                        regex_urls.append(urljoin(base_url, match))
            
            profile_urls.extend(regex_urls)
        
        # Dedupe and limit
        profile_urls = list(set(profile_urls))[:5]  # Limit to 5 profiles to avoid slow scraping
        
        logger.info(f"Found {len(profile_urls)} doctor profile URLs in directory")
        
        # FALLBACK: If no profile URLs found (JS-rendered page), extract names directly
        # Google contact enrichment will find their contact info
        if not profile_urls:
            logger.info(f"[CATEGORY: {category}] No profile URLs found - falling back to name extraction from directory page")
            # Use generic extraction to get names from directory page
            # The Google contact enrichment step will handle finding phones/emails
            return self._extract_generic(directory_content, directory_url, source, category)
        
        # Step 2: Scrape each profile page
        for profile_url in profile_urls:
            try:
                # Scrape profile page
                profile_content = self._free_scrape(profile_url)
                if not profile_content:
                    continue
                
                # Extract name from profile page (strict pattern)
                name_patterns = [
                    r'<h1[^>]*>([^<]+)</h1>',  # Usually in h1
                    r'"name":\s*"([^"]+)"',  # JSON-LD
                    r'<title>([^<]+)</title>',  # Page title
                ]
                
                name = None
                for pattern in name_patterns:
                    match = re.search(pattern, profile_content, re.IGNORECASE)
                    if match:
                        name_candidate = match.group(1).strip()
                        # Filter to actual names
                        if ',' in name_candidate or 'MD' in name_candidate or 'DO' in name_candidate:
                            # Extract just the name part
                            name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', name_candidate)
                            if name_match:
                                name = name_match.group(1)
                                break
                
                if not name:
                    # Fallback: try generic extraction
                    name_matches = re.findall(r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}),?\s+(?:MD|DO|M\.D\.|D\.O\.)', profile_content)
                    if name_matches:
                        name = name_matches[0]
                
                if not name:
                    continue
                
                # Extract phone from profile page - site-specific patterns
                phones = []
                
                # Healthgrades uses data-qa-target="provider-phone"
                if 'healthgrades.com' in profile_url.lower():
                    phone_match = re.search(r'data-qa-target=["\']provider-phone["\'][^>]*>([^<]+)', profile_content, re.IGNORECASE)
                    if phone_match:
                        phones.append(phone_match.group(1).strip())
                
                # Generic phone patterns (works for most sites)
                phones.extend(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', profile_content))
                phones.extend(re.findall(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', profile_content))
                
                # Clean and dedupe - format as (XXX) XXX-XXXX
                cleaned_phones = []
                for p in phones:
                    digits = re.sub(r'[^\d]', '', p)
                    if len(digits) == 10:
                        cleaned_phones.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
                phones = list(set(cleaned_phones))  # Dedupe
                phone = phones[0] if phones else None
                
                # Extract email (rare on directory pages)
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', profile_content)
                emails = [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                email = emails[0] if emails else None
                
                # Extract practice website if no email
                practice_url = None
                if not email:
                    website_patterns = [
                        r'href=["\'](https?://[^"\']+?)["\']',  # Any website link
                        r'Website[^:]*:\s*(https?://[^\s<]+)',
                        r'Visit[^:]*:\s*(https?://[^\s<]+)',
                    ]
                    for pattern in website_patterns:
                        match = re.search(pattern, profile_content, re.IGNORECASE)
                        if match:
                            practice_url = match.group(1)
                            # Validate it's not a directory site
                            blocked_docs = ['healthgrades.com', 'zocdoc.com', 'vitals.com', 'webmd.com',
                                           'doctor.com', 'ratemds.com', 'health.usnews.com']
                            if not any(d in practice_url.lower() for d in blocked_docs):
                                break
                
                # Step 3: If no email, scrape practice website
                if not email and practice_url:
                    try:
                        practice_content = self._free_scrape(practice_url)
                        if practice_content:
                            practice_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', practice_content)
                            practice_emails = [e for e in practice_emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                            if practice_emails:
                                email = practice_emails[0]
                    except:
                        pass
                
                # Use category for tagging if provided
                specialty = []
                if category and category in PROSPECT_CATEGORIES:
                    specialty = [PROSPECT_CATEGORIES[category]["name"]]
                    logger.info(f"[CATEGORY: {category}] Tagging prospect '{name}' with category: {specialty[0]}")
                
                # Create prospect
                prospect = DiscoveredProspect(
                    name=name,
                    title="MD",
                    organization=None,
                    specialty=specialty,
                    contact=ProspectContact(
                        email=email,
                        phone=phone,
                        website=practice_url if practice_url else profile_url
                    ),
                    source=source,
                    source_url=profile_url,
                    bio_snippet=None,
                )
                prospects.append(prospect)
                
                if len(prospects) >= 5:  # Limit per directory
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to extract from profile {profile_url}: {e}")
                continue
        
        return prospects
    
    def _extract_psychology_today_listing(
        self,
        listing_content: str,
        listing_url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        2-hop extraction for Psychology Today listing pages:
        Step 1: Extract profile URLs from listing page
        Step 2: Scrape each profile page to get contact info
        """
        prospects = []
        
        from urllib.parse import urljoin, urlparse
        parsed = urlparse(listing_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Extract profile URLs from listing page
        # Psychology Today profile URLs: /us/therapists/name-slug-city/ID (e.g., /1234567)
        profile_urls = []
        
        # Pattern 1: Actual therapist profile URLs (have ID number at end)
        profile_pattern = r'href=["\'](/us/therapists/[a-z0-9-]+/\d{4,})'
        matches = re.findall(profile_pattern, listing_content, re.IGNORECASE)
        for match in matches:
            if not any(skip in match.lower() for skip in ['?category', '/find', '/browse']):
                profile_urls.append(urljoin(base_url, match))
        
        # Pattern 2: Full URLs
        profile_pattern2 = r'href=["\'](https://www\.psychologytoday\.com/us/therapists/[a-z0-9-]+/\d{4,})'
        matches2 = re.findall(profile_pattern2, listing_content, re.IGNORECASE)
        profile_urls.extend(matches2)
        
        # Also extract from BeautifulSoup with ID number requirement
        try:
            soup = BeautifulSoup(listing_content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # Look for therapist profile URLs (must have ID number at end)
                if '/therapists/' in href and re.search(r'/\d{5,}', href):
                    if '?category' not in href and '/find' not in href:
                        if href.startswith('http'):
                            profile_urls.append(href)
                        else:
                            profile_urls.append(urljoin(base_url, href))
        except:
            pass
        
        # Dedupe and limit
        profile_urls = list(set(profile_urls))[:5]  # Limit to 5 profiles
        
        logger.info(f"Found {len(profile_urls)} Psychology Today profile URLs in listing")
        
        # If no profile URLs found, fall back to name extraction from listing
        if not profile_urls:
            logger.info(f"[CATEGORY: {category}] No profile URLs found - extracting names directly from listing")
            return self._extract_psychology_today(listing_content, listing_url, source, category)
        
        # Step 2: Scrape each profile page
        for profile_url in profile_urls:
            try:
                profile_content = self._free_scrape(profile_url)
                if not profile_content:
                    continue
                
                # Extract name from profile page
                name = None
                
                # Psychology Today profile pages usually have name in h1 or title
                name_patterns = [
                    r'<h1[^>]*class=["\'][^"\']*name[^"\']*["\'][^>]*>([^<]+)</h1>',
                    r'<h1[^>]*>([^<]+)</h1>',
                    r'<title>([^<]+)\s*-\s*Psychology Today</title>',
                    r'"name":\s*"([^"]+)"',
                ]
                
                for pattern in name_patterns:
                    match = re.search(pattern, profile_content, re.IGNORECASE)
                    if match:
                        name_candidate = match.group(1).strip()
                        # Extract just name (remove credentials/titles)
                        name_match = re.search(r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})(?:,|\s+MD|\s+PhD|\s+LCSW)?', name_candidate)
                        if name_match:
                            name_candidate = name_match.group(1)
                            # Validate name before using it
                            if self._is_valid_person_name(name_candidate):
                                name = name_candidate
                                break
                
                if not name:
                    continue
                
                # Extract phone - Psychology Today profiles usually have phone prominently displayed
                phones = []
                
                # Look for phone in specific elements
                phone_patterns = [
                    r'<a[^>]*href=["\']tel:([^"\']+)["\'][^>]*>([^<]+)</a>',  # tel: links
                    r'Phone[^:]*:\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
                    r'phone["\']?\s*:\s*["\']?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
                ]
                
                for pattern in phone_patterns:
                    matches = re.findall(pattern, profile_content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            phones.append(match[1] if match[1] else match[0])
                        else:
                            phones.append(match)
                
                # Generic phone pattern
                phones.extend(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', profile_content))
                
                # Clean and format - validate area codes
                cleaned_phones = []
                for p in phones:
                    digits = re.sub(r'[^\d]', '', str(p))
                    if len(digits) == 10:
                        area_code = int(digits[:3])
                        exchange = int(digits[3:6])
                        # Validate: area code 200-999, exchange 200-999
                        if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                            cleaned_phones.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
                phones = list(set(cleaned_phones))
                phone = phones[0] if phones else None
                
                # Extract email (filter out image filenames and invalid patterns)
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', profile_content)
                valid_emails = []
                for e in emails:
                    e_lower = e.lower()
                    # Skip image filenames
                    if e_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '@2x', '@3x')):
                        continue
                    # Skip generic prefixes
                    if any(e_lower.startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES):
                        continue
                    # Skip patterns like "account-ro-" (image naming)
                    if 'account-' in e_lower or '-ro-' in e_lower:
                        continue
                    # Must have valid domain extension
                    if '.' in e.split('@')[1] and len(e.split('@')[1].split('.')[-1]) >= 2:
                        valid_emails.append(e)
                email = valid_emails[0] if valid_emails else None
                
                # Extract credentials/title
                title = "Therapist"
                cred_pattern = r'\b(PhD|PsyD|LCSW|LMFT|LPC|MEd|EdD|MD|NCC|LCPC|LMHC)\b'
                cred_match = re.search(cred_pattern, profile_content, re.IGNORECASE)
                if cred_match:
                    title = cred_match.group(1)
                
                # Extract bio snippet
                bio_match = re.search(r'<div[^>]*class=["\'][^"\']*bio[^"\']*["\'][^>]*>([^<]{50,300})</div>', profile_content, re.IGNORECASE | re.DOTALL)
                bio_snippet = bio_match.group(1).strip()[:200] if bio_match else None
                
                # Use category for tagging if provided
                specialty = []
                if category and category in PROSPECT_CATEGORIES:
                    specialty = [PROSPECT_CATEGORIES[category]["name"]]
                    logger.info(f"[CATEGORY: {category}] Tagging prospect '{name}' with category: {specialty[0]}")
                
                prospect = DiscoveredProspect(
                    name=name,
                    title=title,
                    organization=None,
                    specialty=specialty,
                    contact=ProspectContact(
                        email=email,
                        phone=phone,
                        website=profile_url
                    ),
                    source=source,
                    source_url=profile_url,
                    bio_snippet=bio_snippet,
                )
                prospects.append(prospect)
                
                if len(prospects) >= 5:  # Limit per listing
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to extract from Psychology Today profile {profile_url}: {e}")
                continue
        
        return prospects
    
    def _extract_treatment_center(
        self,
        main_content: str,
        main_url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Extract prospects from treatment center websites (RTC + PHP/IOP).
        Targets: Admissions Director, Clinical Director, Intake Coordinator, etc.
        Strategy: Scrape main page + staff/leadership/admissions pages.
        """
        prospects = []
        
        from urllib.parse import urljoin, urlparse
        parsed = urlparse(main_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Combine content from main page
        combined_content = main_content
        
        # Target pages for treatment centers (including common variations)
        target_pages = [
            '/team', '/meet-the-team', '/meet-the-team/', '/staff', '/our-team', '/leadership', 
            '/admissions', '/about', '/contact', '/who-we-are'
        ]
        
        # Also try to find team/staff links from the main page
        discovered_pages = []
        try:
            soup = BeautifulSoup(main_content, 'html.parser')
            team_links = soup.find_all('a', href=re.compile(r'team|staff|leadership|admissions', re.I))
            for link in team_links[:5]:  # Limit to 5 additional links
                href = link.get('href', '')
                if href:
                    # Normalize href
                    if href.startswith('/'):
                        normalized = href.rstrip('/')
                        if normalized not in target_pages:
                            discovered_pages.append(normalized)
                    elif base_url in href:
                        parsed = urlparse(href)
                        normalized = parsed.path.rstrip('/')
                        if normalized and normalized not in target_pages:
                            discovered_pages.append(normalized)
        except Exception as e:
            logger.warning(f"Link discovery failed: {e}")
        
        # Combine target pages with discovered pages
        all_pages = list(set(target_pages + discovered_pages))
        
        # Initialize clients for Firecrawl scraping
        self._init_clients()
        
        # Scrape additional pages (use Firecrawl first for JS-rendered content, fallback to free scrape)
        scraped_count = 0
        for path in all_pages[:6]:  # Limit to 6 pages
            try:
                if not path.startswith('/'):
                    path = '/' + path.lstrip('/')
                # Try with and without trailing slash
                for path_variant in [path, path.rstrip('/'), path + '/']:
                    page_url = urljoin(base_url, path_variant)
                    page_content = None
                    
                    # Try Firecrawl first (handles JavaScript-rendered pages)
                    try:
                        if self.firecrawl:
                            scraped = self.firecrawl.scrape_url(page_url)
                            if scraped and scraped.get('success'):
                                page_content = scraped.get('markdown', '') or scraped.get('content', '')
                                if page_content:
                                    logger.info(f"Firecrawl scraped {page_url}")
                    except Exception as fc_error:
                        logger.warning(f"Firecrawl failed for {page_url}, trying free scrape: {fc_error}")
                    
                    # Fallback to free scrape
                    if not page_content:
                        page_content = self._free_scrape(page_url)
                        if page_content:
                            logger.info(f"Free scraped {page_url}")
                    
                    if page_content:
                        combined_content += f"\n\n--- FROM {path_variant} ---\n" + page_content
                        scraped_count += 1
                        break  # Found it, move to next path
            except Exception as e:
                logger.warning(f"Failed to scrape {path}: {e}")
                continue
        
        logger.info(f"Scraped {scraped_count} additional pages for treatment center")
        
        # If no additional pages scraped, try Google search for team/leadership pages
        if scraped_count == 0 and self.google_search:
            try:
                # Search for team/staff pages on this domain
                domain = parsed.netloc.replace('www.', '')
                search_query = f'site:{domain} (team OR staff OR leadership OR "meet the team")'
                logger.info(f"Searching Google for team pages: {search_query}")
                
                search_results = self.google_search.search(query=search_query, num_results=3)
                for result in search_results:
                    if result.link and domain in result.link:
                        # Free scrape the found team page
                        team_content = self._free_scrape(result.link)
                        if team_content:
                            combined_content += f"\n\n--- FROM {result.link} (via Google) ---\n" + team_content
                            scraped_count += 1
                            logger.info(f"Found and scraped team page via Google: {result.link}")
                            break  # Just need one good team page
            except Exception as e:
                logger.warning(f"Google search for team pages failed: {e}")
        
        # Target roles for RTC + PHP/IOP
        target_roles = [
            'admissions director', 'admissions manager', 'admissions coordinator',
            'clinical director', 'program director', 'intake coordinator',
            'intake manager', 'family therapist', 'head of school',
            'executive director', 'clinical manager', 'admissions team',
            'chief executive officer', 'chief operating officer', 'chief clinical officer',
            'vice president', 'president'
        ]
        
        # Extract names with titles - STRICT patterns only
        # Pattern 1: "John Smith, Admissions Director" (name first, then title)
        pattern1 = r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}),?\s+(Admissions Director|Clinical Director|Program Director|Intake Coordinator|Intake Manager|Family Therapist|Head of School|Executive Director|Admissions Manager|Clinical Manager)\b'
        matches1 = re.findall(pattern1, combined_content, re.IGNORECASE)
        
        # Pattern 2: "Admissions Director: Jane Doe" (title first, then name)
        pattern2 = r'\b(Admissions Director|Clinical Director|Program Director|Intake Coordinator|Intake Manager|Family Therapist|Head of School|Executive Director|Admissions Manager|Clinical Manager)[:\s]+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
        matches2 = re.findall(pattern2, combined_content, re.IGNORECASE)
        
        names_with_titles = []
        
        # Process pattern 1 matches
        for match in matches1:
            name = match[0].strip()
            title = match[1].strip()
            # Validate name looks real
            if len(name.split()) == 2 and all(2 <= len(w) <= 12 for w in name.split()):
                names_with_titles.append({"name": name, "title": title})
        
        # Process pattern 2 matches
        for match in matches2:
            title = match[0].strip()
            name = match[1].strip()
            # Validate name looks real
            if len(name.split()) == 2 and all(2 <= len(w) <= 12 for w in name.split()):
                names_with_titles.append({"name": name, "title": title})
        
        # Pattern 3: Names in staff/team sections using BeautifulSoup
        # Common structures:
        # - <h3 class="entry-title">John Smith, MBA</h3>
        # - <h2>John Smith</h2> followed by role
        # - <div class="team-member"> with name and title
        try:
            soup = BeautifulSoup(combined_content, 'html.parser')
            
            # Method 3a: Look for h2/h3/h4 with entry-title or similar classes
            name_headings = soup.find_all(['h2', 'h3', 'h4'], class_=re.compile(r'entry-title|name|staff-name|team-member-name', re.I))
            for heading in name_headings:
                text = heading.get_text(strip=True)
                # Extract name (first part before comma, if any)
                name_part = text.split(',')[0].strip()
                # Check if it looks like a name
                if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}$', name_part):
                    # Look for role in position field (common pattern: <p class="team_member_position">)
                    role_found = None
                    parent = heading.find_parent(['div', 'section', 'article'])
                    if parent:
                        # Look for position field in parent
                        position_field = parent.find(['p', 'div', 'span'], class_=re.compile(r'position|role|title|team_member_position', re.I))
                        if position_field:
                            position_text = position_field.get_text(strip=True)
                            # Match against target roles (check for full match first)
                            for role in target_roles:
                                if role in position_text.lower():
                                    # Try to get the full title, not just the matched word
                                    role_found = position_text[:100]  # Use actual position text
                                    break
                        
                        # If no position field, check parent text
                        if not role_found:
                            parent_text = parent.get_text(strip=True).lower()
                            for role in target_roles:
                                if role in parent_text:
                                    # Extract the full title phrase
                                    role_match = re.search(rf'\b{role}[^\.\n]*', parent_text, re.I)
                                    if role_match:
                                        role_found = role_match.group(0).title()
                                    else:
                                        role_found = role.title()
                                    break
                    
                    # Fallback: check next sibling
                    if not role_found:
                        next_elem = heading.find_next_sibling()
                        if next_elem:
                            next_text = next_elem.get_text(strip=True).lower()
                            for role in target_roles:
                                if role in next_text:
                                    role_found = role.title()
                                    break
                    
                    if role_found:
                        names_with_titles.append({"name": name_part, "title": role_found})
            
            # Method 3b: Look for divs with team-member or staff classes
            team_divs = soup.find_all(['div', 'section'], class_=re.compile(r'team-member|staff-member|leadership-member', re.I))
            for div in team_divs:
                # Find name in heading within this div
                name_heading = div.find(['h2', 'h3', 'h4', 'h5'])
                if name_heading:
                    name_text = name_heading.get_text(strip=True)
                    name_part = name_text.split(',')[0].strip()
                    if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}$', name_part):
                        # Look for role in div text
                        div_text = div.get_text(strip=True).lower()
                        for role in target_roles:
                            if role in div_text:
                                names_with_titles.append({"name": name_part, "title": role.title()})
                                break
            
            # Method 3c: Look for position/role fields near names
            position_fields = soup.find_all(['p', 'div', 'span'], class_=re.compile(r'position|role|title|team_member_position', re.I))
            for field in position_fields:
                position_text = field.get_text(strip=True)
                if not position_text or len(position_text) < 3:
                    continue
                
                position_lower = position_text.lower()
                # Check if this position matches our target roles
                matched_role = None
                for role in target_roles:
                    if role in position_lower:
                        # Use the full position text, not just the matched word
                        matched_role = position_text[:100].strip()  # Use actual position text
                        break
                
                if matched_role:
                    # Find name in previous sibling or parent
                    prev_elem = field.find_previous(['h2', 'h3', 'h4', 'h5'])
                    if not prev_elem:
                        parent = field.find_parent(['div', 'section', 'article'])
                        if parent:
                            prev_elem = parent.find(['h2', 'h3', 'h4', 'h5'])
                    
                    if prev_elem:
                        name_text = prev_elem.get_text(strip=True)
                        name_part = name_text.split(',')[0].strip()
                        if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}$', name_part):
                            names_with_titles.append({"name": name_part, "title": matched_role})
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed: {e}")
            # Fallback to regex pattern
            staff_name_pattern = r'<h[23][^>]*>([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})</h[23]>'
            name_matches = re.findall(staff_name_pattern, combined_content)
            for name in name_matches:
                name_pos = combined_content.find(name)
                if name_pos != -1:
                    nearby = combined_content[name_pos:name_pos+200]
                    for role in target_roles:
                        if role in nearby.lower():
                            names_with_titles.append({"name": name, "title": role.title()})
                            break
        
        # Pattern 4: Name directly followed by title (no space/punctuation) - "Blake KinseyVice President"
        # This handles cases where names and titles are concatenated
        name_title_concat_pattern = r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})(Vice President|President|Director|Manager|Coordinator|Therapist|Head of School)'
        matches4 = re.findall(name_title_concat_pattern, combined_content)
        for match in matches4:
            name = match[0].strip()
            title = match[1].strip()
            if len(name.split()) == 2 and all(2 <= len(w) <= 12 for w in name.split()):
                names_with_titles.append({"name": name, "title": title})
        
        # Pattern 5: Role keywords followed by names
        for role in target_roles:
            role_pattern = rf'\b{role}\b[^<]*?([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}})'
            matches = re.findall(role_pattern, combined_content, re.IGNORECASE)
            for name in matches:
                name = name.strip()
                # Validate name
                if len(name.split()) == 2 and all(2 <= len(w) <= 12 for w in name.split()):
                    # Check it's not a common false positive
                    bad_words = ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 'programs', 'therapy', 'center']
                    if not any(bad in name.lower() for bad in bad_words):
                        names_with_titles.append({"name": name, "title": role.title()})
        
        # Pattern 6: Extract from text blocks - look for name patterns near role keywords
        # Split content into sentences/paragraphs and look for name + role combinations
        text_blocks = re.split(r'[\.\n]', combined_content)
        for block in text_blocks:
            # Look for name pattern
            name_match = re.search(r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b', block)
            if name_match:
                name = name_match.group(1)
                # Check if any role is in this block
                for role in target_roles:
                    if role in block.lower() and len(name.split()) == 2:
                        # Validate name
                        words = name.split()
                        if all(2 <= len(w) <= 12 for w in words):
                            names_with_titles.append({"name": name, "title": role.title()})
                            break
        
        # Dedupe by name and validate
        seen_names = set()
        bad_name_words = ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 
                         'programs', 'therapy', 'center', 'treatment', 'rehab',
                         'founder and', 'apy programs', 'ock facebook', 'help for',
                         'struggling', 'evoke', 'newport', 'academy']
        
        for item in names_with_titles:
            name = item["name"].strip()
            
            # Basic validation
            if name in seen_names or len(name) < 5:
                continue
            
            # Must be exactly 2 words
            words = name.split()
            if len(words) != 2:
                continue
            
            # Each word should be 2-12 chars
            if not all(2 <= len(w) <= 12 for w in words):
                continue
            
            # No bad words
            name_lower = name.lower()
            if any(bad in name_lower for bad in bad_name_words):
                continue
            
            # No HTML entities or special chars
            if '&' in name or '»' in name or '<' in name or '>' in name:
                continue
            
            # Must start with capital letter
            if not name[0].isupper():
                continue
            
            seen_names.add(name)
            
            # Extract email near this name (within 500 chars)
            email = None
            name_pos = combined_content.lower().find(name.lower())
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', nearby)
                valid_emails = [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                if valid_emails:
                    email = valid_emails[0]
            
            # Extract phone near this name
            phone = None
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby)
                if phones:
                    digits = re.sub(r'[^\d]', '', phones[0])
                    if len(digits) == 10:
                        area_code = int(digits[:3])
                        exchange = int(digits[3:6])
                        if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                            phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            
            # Extract organization name (usually in page title or h1)
            org_match = re.search(r'<title>([^<]+)</title>', combined_content, re.IGNORECASE)
            organization = None
            if org_match:
                title = org_match.group(1)
                # Extract organization name (remove common suffixes)
                org = re.sub(r'\s*-\s*(Treatment|Center|Rehab|Recovery|Program).*', '', title, flags=re.I)
                organization = org.strip()[:100]
            
            # Use category for tagging if provided
            specialty = []
            if category and category in PROSPECT_CATEGORIES:
                specialty = [PROSPECT_CATEGORIES[category]["name"]]
                logger.info(f"[CATEGORY: {category}] Tagging prospect '{name}' with category: {specialty[0]}")
            
            prospect = DiscoveredProspect(
                name=name,
                title=item.get("title", "Director"),
                organization=organization,
                specialty=specialty,
                contact=ProspectContact(
                    email=email,
                    phone=phone,
                    website=main_url
                ),
                source=source,
                source_url=main_url,
                bio_snippet=None,
            )
            prospects.append(prospect)
            
            if len(prospects) >= 10:  # Limit per center
                break
        
        # If prospects found but missing contact info, try Google enrichment
        if prospects and self.google_search:
            for prospect in prospects:
                if not prospect.contact.email and not prospect.contact.phone:
                    try:
                        # Search for contact info: "Name Title Organization email phone"
                        search_query = f'"{prospect.name}" {prospect.title or ""} {prospect.organization or ""} {parsed.netloc} email phone'
                        logger.info(f"Google contact enrichment for {prospect.name}: {search_query}")
                        
                        search_results = self.google_search.search(query=search_query, num_results=3)
                        for result in search_results:
                            # Extract email/phone from snippet
                            snippet = result.snippet or ""
                            if snippet:
                                # Extract email
                                if not prospect.contact.email:
                                    snippet_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', snippet)
                                    valid_emails = [e for e in snippet_emails 
                                                   if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                    if valid_emails:
                                        prospect.contact.email = valid_emails[0]
                                
                                # Extract phone
                                if not prospect.contact.phone:
                                    snippet_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                                    if snippet_phones:
                                        digits = re.sub(r'[^\d]', '', snippet_phones[0])
                                        if len(digits) == 10:
                                            area_code = int(digits[:3])
                                            exchange = int(digits[3:6])
                                            if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                                                prospect.contact.phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                            
                            # If still missing, scrape the result page
                            if (not prospect.contact.email or not prospect.contact.phone) and result.link:
                                try:
                                    page_content = self._free_scrape(result.link)
                                    if page_content:
                                        # Extract email
                                        if not prospect.contact.email:
                                            page_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_content)
                                            valid_emails = [e for e in page_emails 
                                                           if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                            if valid_emails:
                                                prospect.contact.email = valid_emails[0]
                                        
                                        # Extract phone
                                        if not prospect.contact.phone:
                                            page_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', page_content)
                                            if page_phones:
                                                digits = re.sub(r'[^\d]', '', page_phones[0])
                                                if len(digits) == 10:
                                                    area_code = int(digits[:3])
                                                    exchange = int(digits[3:6])
                                                    if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                                                        prospect.contact.phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                                except:
                                    pass
                            
                            # If we got both, stop searching
                            if prospect.contact.email and prospect.contact.phone:
                                break
                    except Exception as e:
                        logger.warning(f"Google contact enrichment failed for {prospect.name}: {e}")
        
        return prospects
    
    def _extract_embassy_contacts(
        self,
        main_content: str,
        main_url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Extract prospects from embassy/consulate websites.
        Targets: Education Officer, Cultural Attaché, Education Attaché, etc.
        Strategy: Scrape main page + education/culture/consular pages.
        """
        prospects = []
        
        from urllib.parse import urljoin, urlparse
        parsed = urlparse(main_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Combine content from main page
        combined_content = main_content
        
        # Target pages for embassies
        target_pages = [
            '/education', '/cultural', '/culture', '/consular', '/consular-services',
            '/about', '/contact', '/staff', '/team', '/officers'
        ]
        
        # Also try to find education/cultural links from the main page
        discovered_pages = []
        try:
            soup = BeautifulSoup(main_content, 'html.parser')
            embassy_links = soup.find_all('a', href=re.compile(r'education|cultural|culture|consular|contact', re.I))
            for link in embassy_links[:5]:  # Limit to 5 additional links
                href = link.get('href', '')
                if href:
                    # Normalize href
                    if href.startswith('/'):
                        normalized = href.rstrip('/')
                        if normalized not in target_pages:
                            discovered_pages.append(normalized)
                    elif base_url in href:
                        parsed_href = urlparse(href)
                        normalized = parsed_href.path.rstrip('/')
                        if normalized and normalized not in target_pages:
                            discovered_pages.append(normalized)
        except Exception as e:
            logger.warning(f"Link discovery failed: {e}")
        
        # Combine target pages with discovered pages
        all_pages = list(set(target_pages + discovered_pages))
        
        # Initialize clients
        self._init_clients()
        
        # Scrape additional pages
        scraped_count = 0
        for path in all_pages[:5]:  # Limit to 5 pages
            try:
                if not path.startswith('/'):
                    path = '/' + path.lstrip('/')
                # Try with and without trailing slash
                for path_variant in [path, path.rstrip('/'), path + '/']:
                    page_url = urljoin(base_url, path_variant)
                    page_content = None
                    
                    # Try Firecrawl first (handles JavaScript-rendered pages)
                    try:
                        if self.firecrawl:
                            scraped = self.firecrawl.scrape_url(page_url)
                            if scraped and scraped.get('success'):
                                page_content = scraped.get('markdown', '') or scraped.get('content', '')
                                if page_content:
                                    logger.info(f"Firecrawl scraped {page_url}")
                    except Exception as fc_error:
                        logger.warning(f"Firecrawl failed for {page_url}, trying free scrape: {fc_error}")
                    
                    # Fallback to free scrape
                    if not page_content:
                        page_content = self._free_scrape(page_url)
                        if page_content:
                            logger.info(f"Free scraped {page_url}")
                    
                    if page_content:
                        combined_content += f"\n\n--- FROM {path_variant} ---\n" + page_content
                        scraped_count += 1
                        break  # Found it, move to next path
            except Exception as e:
                logger.warning(f"Failed to scrape {path}: {e}")
                continue
        
        logger.info(f"Scraped {scraped_count} additional pages for embassy")
        
        # If no additional pages scraped, try Google search for education/cultural pages
        if scraped_count == 0 and self.google_search:
            try:
                domain = parsed.netloc.replace('www.', '')
                search_query = f'site:{domain} (education OR "cultural attache" OR "education officer" OR culture)'
                logger.info(f"Searching Google for embassy education pages: {search_query}")
                
                search_results = self.google_search.search(query=search_query, num_results=3)
                for result in search_results:
                    if result.link and domain in result.link:
                        page_content = self._free_scrape(result.link)
                        if page_content:
                            combined_content += f"\n\n--- FROM {result.link} (via Google) ---\n" + page_content
                            scraped_count += 1
                            logger.info(f"Found and scraped embassy page via Google: {result.link}")
                            break
            except Exception as e:
                logger.warning(f"Google search for embassy pages failed: {e}")
        
        # Target roles for embassies
        target_roles = [
            'education officer', 'cultural attaché', 'cultural attache', 'education attaché',
            'education attaché', 'cultural affairs officer', 'consular officer',
            'public affairs officer', 'information officer', 'press attaché'
        ]
        
        # Extract names with titles using BeautifulSoup
        names_with_titles = []
        
        try:
            soup = BeautifulSoup(combined_content, 'html.parser')
            
            # Method 1: Look for headings with names
            name_headings = soup.find_all(['h2', 'h3', 'h4', 'h5'], class_=re.compile(r'name|officer|staff|contact', re.I))
            for heading in name_headings:
                text = heading.get_text(strip=True)
                # Extract name (first part before comma or title)
                name_part = text.split(',')[0].split('–')[0].split('—')[0].strip()
                # Check if it looks like a name
                if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}(?:\s+[A-Z][a-z]{2,12})?$', name_part):
                    # Look for role in nearby text
                    parent = heading.find_parent(['div', 'section', 'article', 'li'])
                    if parent:
                        parent_text = parent.get_text(strip=True).lower()
                        for role in target_roles:
                            if role in parent_text:
                                names_with_titles.append({"name": name_part, "title": role.title()})
                                break
            
            # Method 2: Look for role keywords followed by names
            for role in target_roles:
                # Pattern: "Education Officer: John Smith" or "Education Officer - John Smith"
                role_pattern = rf'\b{re.escape(role)}\b[:\s–—]+\s*([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}})'
                matches = re.findall(role_pattern, combined_content, re.IGNORECASE)
                for name in matches:
                    if len(name.split()) >= 2:
                        names_with_titles.append({"name": name.strip(), "title": role.title()})
            
            # Method 3: Extract from structured lists/divs
            # Look for divs/sections containing embassy staff info
            staff_sections = soup.find_all(['div', 'section'], class_=re.compile(r'staff|officer|team|contact|person', re.I))
            for section in staff_sections:
                section_text = section.get_text()
                # Look for name + role patterns
                for role in target_roles:
                    if role in section_text.lower():
                        # Find name nearby
                        name_match = re.search(r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})', section_text)
                        if name_match:
                            name = name_match.group(1)
                            if len(name.split()) >= 2:
                                names_with_titles.append({"name": name, "title": role.title()})
                                break
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed: {e}")
        
        # Dedupe and validate
        seen_names = set()
        bad_name_words = ['embassy', 'consulate', 'diplomatic', 'mission', 'services', 
                         'contact', 'address', 'phone', 'email', 'office']
        
        for item in names_with_titles:
            name = item["name"].strip()
            
            if name in seen_names or len(name) < 5:
                continue
            
            words = name.split()
            if len(words) < 2:
                continue
            
            if not all(2 <= len(w) <= 15 for w in words):
                continue
            
            name_lower = name.lower()
            if any(bad in name_lower for bad in bad_name_words):
                continue
            
            if '&' in name or '<' in name or '>' in name:
                continue
            
            if not name[0].isupper():
                continue
            
            seen_names.add(name)
            
            # Extract email near this name
            email = None
            name_pos = combined_content.lower().find(name.lower())
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', nearby)
                # Embassy emails often end with .gov, .org, or embassy domain
                valid_emails = [e for e in emails 
                               if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                if valid_emails:
                    email = valid_emails[0]
            
            # Extract phone near this name
            phone = None
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby)
                if phones:
                    digits = re.sub(r'[^\d]', '', phones[0])
                    if len(digits) == 10:
                        area_code = int(digits[:3])
                        exchange = int(digits[3:6])
                        if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                            phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            
            # Extract embassy name from page title or h1
            org_match = re.search(r'<title>([^<]+)</title>', combined_content, re.IGNORECASE)
            organization = None
            if org_match:
                title = org_match.group(1)
                # Extract embassy name (remove common suffixes)
                org = re.sub(r'\s*-\s*(Embassy|Consulate|Diplomatic|Mission).*', '', title, flags=re.I)
                organization = org.strip()[:100]
            
            # If no org from title, try to get from URL
            if not organization:
                domain = parsed.netloc.replace('www.', '')
                if '.embassy.' in domain or '.consulate.' in domain:
                    organization = domain.replace('.embassy.', ' Embassy ').replace('.consulate.', ' Consulate ')
                elif domain.endswith('.gov') or domain.endswith('.org'):
                    organization = domain.split('.')[0].title() + " Embassy"
            
            # Use category for tagging if provided
            specialty = []
            if category and category in PROSPECT_CATEGORIES:
                specialty = [PROSPECT_CATEGORIES[category]["name"]]
                logger.info(f"[CATEGORY: {category}] Tagging prospect '{name}' with category: {specialty[0]}")
            
            prospect = DiscoveredProspect(
                name=name,
                title=item.get("title", "Education Officer"),
                organization=organization,
                specialty=specialty,
                contact=ProspectContact(
                    email=email,
                    phone=phone,
                    website=main_url
                ),
                source=source,
                source_url=main_url,
                bio_snippet=None,
            )
            prospects.append(prospect)
            
            if len(prospects) >= 10:  # Limit per embassy
                break
        
        # If prospects found but missing contact info, try Google enrichment
        if prospects and self.google_search:
            for prospect in prospects:
                if not prospect.contact.email and not prospect.contact.phone:
                    try:
                        search_query = f'"{prospect.name}" "{prospect.title or ""}" "{prospect.organization or ""}" email phone'
                        logger.info(f"Google contact enrichment for embassy contact {prospect.name}: {search_query}")
                        
                        search_results = self.google_search.search(query=search_query, num_results=3)
                        for result in search_results:
                            snippet = result.snippet or ""
                            if snippet:
                                # Extract email
                                if not prospect.contact.email:
                                    snippet_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', snippet)
                                    valid_emails = [e for e in snippet_emails 
                                                   if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                    if valid_emails:
                                        prospect.contact.email = valid_emails[0]
                                
                                # Extract phone
                                if not prospect.contact.phone:
                                    snippet_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                                    if snippet_phones:
                                        digits = re.sub(r'[^\d]', '', snippet_phones[0])
                                        if len(digits) == 10:
                                            area_code = int(digits[:3])
                                            exchange = int(digits[3:6])
                                            if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                                                prospect.contact.phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                            
                            # If still missing, scrape the result page
                            if (not prospect.contact.email or not prospect.contact.phone) and result.link:
                                try:
                                    page_content = self._free_scrape(result.link)
                                    if page_content:
                                        # Extract email
                                        if not prospect.contact.email:
                                            page_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_content)
                                            valid_emails = [e for e in page_emails 
                                                           if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                            if valid_emails:
                                                prospect.contact.email = valid_emails[0]
                                        
                                        # Extract phone
                                        if not prospect.contact.phone:
                                            page_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', page_content)
                                            if page_phones:
                                                digits = re.sub(r'[^\d]', '', page_phones[0])
                                                if len(digits) == 10:
                                                    area_code = int(digits[:3])
                                                    exchange = int(digits[3:6])
                                                    if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                                                        prospect.contact.phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                                except:
                                    pass
                            
                            if prospect.contact.email and prospect.contact.phone:
                                break
                    except Exception as e:
                        logger.warning(f"Google contact enrichment failed for {prospect.name}: {e}")
        
        return prospects
    
    def _extract_youth_sports(
        self,
        main_content: str,
        main_url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Extract prospects from youth sports organizations (academies, clubs, travel teams).
        Targets: Coaches, Directors, Program Directors, Athletic Directors, etc.
        Strategy: Scrape main page + staff/coaches/leadership pages.
        """
        prospects = []
        
        from urllib.parse import urljoin, urlparse
        parsed = urlparse(main_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Combine content from main page
        combined_content = main_content
        
        # Target pages for youth sports organizations
        target_pages = [
            '/coaches', '/staff', '/team', '/about', '/leadership', 
            '/programs', '/contact', '/coaching-staff'
        ]
        
        # Also try to find coaches/staff links from the main page
        discovered_pages = []
        try:
            soup = BeautifulSoup(main_content, 'html.parser')
            sports_links = soup.find_all('a', href=re.compile(r'coach|staff|team|director|program', re.I))
            for link in sports_links[:5]:  # Limit to 5 additional links
                href = link.get('href', '')
                if href:
                    # Normalize href
                    if href.startswith('/'):
                        normalized = href.rstrip('/')
                        if normalized not in target_pages:
                            discovered_pages.append(normalized)
                    elif base_url in href:
                        parsed_href = urlparse(href)
                        normalized = parsed_href.path.rstrip('/')
                        if normalized and normalized not in target_pages:
                            discovered_pages.append(normalized)
        except Exception as e:
            logger.warning(f"Link discovery failed: {e}")
        
        # Combine target pages with discovered pages
        all_pages = list(set(target_pages + discovered_pages))
        
        # Initialize clients
        self._init_clients()
        
        # Scrape additional pages
        scraped_count = 0
        for path in all_pages[:5]:  # Limit to 5 pages
            try:
                if not path.startswith('/'):
                    path = '/' + path.lstrip('/')
                # Try with and without trailing slash
                for path_variant in [path, path.rstrip('/'), path + '/']:
                    page_url = urljoin(base_url, path_variant)
                    page_content = None
                    
                    # Try Firecrawl first (handles JavaScript-rendered pages)
                    try:
                        if self.firecrawl:
                            scraped = self.firecrawl.scrape_url(page_url)
                            if scraped and scraped.get('success'):
                                page_content = scraped.get('markdown', '') or scraped.get('content', '')
                                if page_content:
                                    logger.info(f"Firecrawl scraped {page_url}")
                    except Exception as fc_error:
                        logger.warning(f"Firecrawl failed for {page_url}, trying free scrape: {fc_error}")
                    
                    # Fallback to free scrape
                    if not page_content:
                        page_content = self._free_scrape(page_url)
                        if page_content:
                            logger.info(f"Free scraped {page_url}")
                    
                    if page_content:
                        combined_content += f"\n\n--- FROM {path_variant} ---\n" + page_content
                        scraped_count += 1
                        break  # Found it, move to next path
            except Exception as e:
                logger.warning(f"Failed to scrape {path}: {e}")
                continue
        
        logger.info(f"Scraped {scraped_count} additional pages for youth sports")
        
        # If no additional pages scraped, try Google search for coaches/staff pages
        if scraped_count == 0 and self.google_search:
            try:
                domain = parsed.netloc.replace('www.', '')
                search_query = f'site:{domain} (coaches OR staff OR "program director" OR "athletic director")'
                logger.info(f"Searching Google for sports staff pages: {search_query}")
                
                search_results = self.google_search.search(query=search_query, num_results=3)
                for result in search_results:
                    if result.link and domain in result.link:
                        page_content = self._free_scrape(result.link)
                        if page_content:
                            combined_content += f"\n\n--- FROM {result.link} (via Google) ---\n" + page_content
                            scraped_count += 1
                            logger.info(f"Found and scraped sports staff page via Google: {result.link}")
                            break
            except Exception as e:
                logger.warning(f"Google search for sports staff pages failed: {e}")
        
        # Target roles for youth sports
        target_roles = [
            'director', 'program director', 'athletic director', 'coach', 'head coach',
            'assistant coach', 'director of coaching', 'technical director',
            'operations director', 'program manager', 'sports director'
        ]
        
        # Extract names with titles using BeautifulSoup
        names_with_titles = []
        
        try:
            soup = BeautifulSoup(combined_content, 'html.parser')
            
            # Method 1: Look for headings with names
            name_headings = soup.find_all(['h2', 'h3', 'h4', 'h5'], class_=re.compile(r'name|coach|staff|director|person', re.I))
            for heading in name_headings:
                text = heading.get_text(strip=True)
                # Extract name (first part before comma or title)
                name_part = text.split(',')[0].split('–')[0].split('—')[0].strip()
                # Check if it looks like a name
                if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}(?:\s+[A-Z][a-z]{2,12})?$', name_part):
                    # Look for role in nearby text
                    parent = heading.find_parent(['div', 'section', 'article', 'li'])
                    if parent:
                        parent_text = parent.get_text(strip=True).lower()
                        for role in target_roles:
                            if role in parent_text:
                                names_with_titles.append({"name": name_part, "title": role.title()})
                                break
            
            # Method 2: Look for role keywords followed by names
            for role in target_roles:
                # Pattern: "Head Coach: John Smith" or "Head Coach - John Smith"
                role_pattern = rf'\b{re.escape(role)}\b[:\s–—]+\s*([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}})'
                matches = re.findall(role_pattern, combined_content, re.IGNORECASE)
                for name in matches:
                    if len(name.split()) >= 2:
                        names_with_titles.append({"name": name.strip(), "title": role.title()})
            
            # Method 3: Extract from structured lists/divs
            staff_sections = soup.find_all(['div', 'section'], class_=re.compile(r'staff|coach|team|director|person', re.I))
            for section in staff_sections:
                section_text = section.get_text()
                # Look for name + role patterns
                for role in target_roles:
                    if role in section_text.lower():
                        # Find name nearby
                        name_match = re.search(r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})', section_text)
                        if name_match:
                            name = name_match.group(1)
                            if len(name.split()) >= 2:
                                names_with_titles.append({"name": name, "title": role.title()})
                                break
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed: {e}")
        
        # Dedupe and validate
        seen_names = set()
        bad_name_words = ['sports', 'academy', 'athletic', 'club', 'team', 'program',
                         'contact', 'address', 'phone', 'email', 'office', 'field']
        
        for item in names_with_titles:
            name = item["name"].strip()
            
            if name in seen_names or len(name) < 5:
                continue
            
            words = name.split()
            if len(words) < 2:
                continue
            
            if not all(2 <= len(w) <= 15 for w in words):
                continue
            
            name_lower = name.lower()
            if any(bad in name_lower for bad in bad_name_words):
                continue
            
            if '&' in name or '<' in name or '>' in name:
                continue
            
            if not name[0].isupper():
                continue
            
            seen_names.add(name)
            
            # Extract email near this name
            email = None
            name_pos = combined_content.lower().find(name.lower())
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', nearby)
                valid_emails = [e for e in emails 
                               if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                if valid_emails:
                    email = valid_emails[0]
            
            # Extract phone near this name
            phone = None
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby)
                if phones:
                    digits = re.sub(r'[^\d]', '', phones[0])
                    if len(digits) == 10:
                        area_code = int(digits[:3])
                        exchange = int(digits[3:6])
                        if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                            phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            
            # Extract organization name from page title or h1
            org_match = re.search(r'<title>([^<]+)</title>', combined_content, re.IGNORECASE)
            organization = None
            if org_match:
                title = org_match.group(1)
                # Extract organization name (remove common suffixes)
                org = re.sub(r'\s*-\s*(Academy|Club|Team|Sports|Athletic).*', '', title, flags=re.I)
                organization = org.strip()[:100]
            
            # If no org from title, try to get from URL
            if not organization:
                domain = parsed.netloc.replace('www.', '')
                if 'academy' in domain or 'club' in domain or 'sports' in domain:
                    # Try to extract meaningful org name from domain
                    parts = domain.split('.')
                    if parts:
                        org_part = parts[0].replace('-', ' ').title()
                        organization = org_part + " Academy" if 'academy' not in org_part.lower() else org_part
            
            # Use category for tagging if provided
            specialty = []
            if category and category in PROSPECT_CATEGORIES:
                specialty = [PROSPECT_CATEGORIES[category]["name"]]
                logger.info(f"[CATEGORY: {category}] Tagging prospect '{name}' with category: {specialty[0]}")
            
            prospect = DiscoveredProspect(
                name=name,
                title=item.get("title", "Director"),
                organization=organization,
                specialty=specialty,
                contact=ProspectContact(
                    email=email,
                    phone=phone,
                    website=main_url
                ),
                source=source,
                source_url=main_url,
                bio_snippet=None,
            )
            prospects.append(prospect)
            
            if len(prospects) >= 15:  # Limit per organization (coaches can be many)
                break
        
        # If prospects found but missing contact info, try Google enrichment
        if prospects and self.google_search:
            for prospect in prospects:
                if not prospect.contact.email and not prospect.contact.phone:
                    try:
                        search_query = f'"{prospect.name}" "{prospect.title or ""}" "{prospect.organization or ""}" email phone'
                        logger.info(f"Google contact enrichment for sports contact {prospect.name}: {search_query}")
                        
                        search_results = self.google_search.search(query=search_query, num_results=3)
                        for result in search_results:
                            snippet = result.snippet or ""
                            if snippet:
                                # Extract email
                                if not prospect.contact.email:
                                    snippet_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', snippet)
                                    valid_emails = [e for e in snippet_emails 
                                                   if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                    if valid_emails:
                                        prospect.contact.email = valid_emails[0]
                                
                                # Extract phone
                                if not prospect.contact.phone:
                                    snippet_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
                                    if snippet_phones:
                                        digits = re.sub(r'[^\d]', '', snippet_phones[0])
                                        if len(digits) == 10:
                                            area_code = int(digits[:3])
                                            exchange = int(digits[3:6])
                                            if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                                                prospect.contact.phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                            
                            # If still missing, scrape the result page
                            if (not prospect.contact.email or not prospect.contact.phone) and result.link:
                                try:
                                    page_content = self._free_scrape(result.link)
                                    if page_content:
                                        # Extract email
                                        if not prospect.contact.email:
                                            page_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_content)
                                            valid_emails = [e for e in page_emails 
                                                           if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                            if valid_emails:
                                                prospect.contact.email = valid_emails[0]
                                        
                                        # Extract phone
                                        if not prospect.contact.phone:
                                            page_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', page_content)
                                            if page_phones:
                                                digits = re.sub(r'[^\d]', '', page_phones[0])
                                                if len(digits) == 10:
                                                    area_code = int(digits[:3])
                                                    exchange = int(digits[3:6])
                                                    if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                                                        prospect.contact.phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                                except:
                                    pass
                            
                            if prospect.contact.email and prospect.contact.phone:
                                break
                    except Exception as e:
                        logger.warning(f"Google contact enrichment failed for {prospect.name}: {e}")
        
        return prospects
    
    def _extract_generic(
        self,
        content: str,
        url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Universal extraction using 3-layer approach:
        Layer 1: Expanded regex with all credentials
        Layer 2: Heuristic name detection
        Layer 3: LLM fallback (called separately if needed)
        """
        prospects = []
        
        # =================================================================
        # CONTACT INFO EXTRACTION
        # =================================================================
        
        # Email extraction - filter out generic/non-personal emails
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        
        # Also find obfuscated emails: john [at] example [dot] com
        obfuscated_pattern = r'([a-zA-Z0-9._%+-]+)\s*\[at\]\s*([a-zA-Z0-9.-]+)\s*\[dot\]\s*([a-zA-Z]{2,})'
        for match in re.findall(obfuscated_pattern, content, re.IGNORECASE):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
        
        # Also find: john (at) example (dot) com
        obfuscated_pattern2 = r'([a-zA-Z0-9._%+-]+)\s*\(at\)\s*([a-zA-Z0-9.-]+)\s*\(dot\)\s*([a-zA-Z]{2,})'
        for match in re.findall(obfuscated_pattern2, content, re.IGNORECASE):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
        
        # Also find: john AT example DOT com
        obfuscated_pattern3 = r'([a-zA-Z0-9._%+-]+)\s+AT\s+([a-zA-Z0-9.-]+)\s+DOT\s+([a-zA-Z]{2,})'
        for match in re.findall(obfuscated_pattern3, content):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
        
        emails = [e for e in emails 
                  if not e.endswith('.png') 
                  and not e.endswith('.jpg')
                  and not e.endswith('.gif')
                  and '@sentry' not in e.lower()
                  and not any(e.lower().startswith(prefix + '@') for prefix in GENERIC_EMAIL_PREFIXES)]
        emails = list(set(emails))  # Dedupe
        
        # Phone extraction
        phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content)
        phones = list(set(phones))  # Dedupe
        
        # =================================================================
        # LAYER 1: EXPANDED CREDENTIAL-BASED NAME EXTRACTION
        # =================================================================
        
        names_with_info = []
        
        # Global bad name patterns - these are NOT real person names
        bad_name_words = [
            'educational', 'administrative', 'outreach', 'experience', 'engagement',
            'customer', 'patient', 'human', 'service', 'services', 'standardized',
            'test', 'prep', 'head', 'start', 'reviewer', 'board', 'college',
            'resources', 'featured', 'guidance', 'admissions', 'tutoring', 'academic',
            'available', 'advising', 'member', 'independent', 'county', 'montgomery',
            'tedeschi', 'marks', 'education', 'consultant', 'consulting', 'group',
            'center', 'institute', 'foundation', 'association', 'program', 'school',
            'academy', 'learning', 'development', 'training', 'coaching', 'support',
            # Common website/UI phrases
            'help', 'how', 'can', 'you', 'your', 'child', 'contact', 'phone', 'number',
            'email', 'address', 'click', 'here', 'read', 'more', 'learn', 'about',
            'options', 'certified', 'planner', 'risk', 'lines', 'personal', 'day',
            'schools', 'what', 'why', 'when', 'where', 'our', 'the', 'and', 'for',
            'with', 'this', 'that', 'from', 'have', 'been', 'will', 'would', 'could',
            'should', 'their', 'there', 'which', 'other', 'some', 'many', 'most',
            'free', 'best', 'top', 'new', 'first', 'last', 'next', 'back', 'home',
            'page', 'site', 'web', 'online', 'info', 'information', 'details',
            'submit', 'send', 'get', 'find', 'search', 'browse', 'view', 'see',
            'call', 'today', 'now', 'schedule', 'book', 'appointment', 'meeting',
            # Location names that aren't person names
            'areas', 'cities', 'bethesda', 'north', 'south', 'east', 'west',
            'endorsed', 'endorsement', 'good', 'afternoon', 'morning', 'evening',
            'afternoon', 'royalty', 'institute', 'where', 'children', 'come', 'first',
            'powered', 'by', 'engineers', 'united', 'states', 'janak'
        ]
        
        # Additional non-name words to filter
        common_non_names = ['internet', 'licensed', 'professional', 'clinical', 'certified',
                            'registered', 'national', 'american', 'eclectic', 'compassion',
                            'focused', 'cognitive', 'behavioral', 'mental', 'health',
                            'therapists', 'therapist', 'family', 'adult', 'couples',
                            'marriage', 'anxiety', 'depression', 'trauma', 'addiction']
        
        role_words = ['therapist', 'counselor', 'psychologist', 'psychiatrist', 'coach',
                      'specialist', 'consultant', 'advisor', 'director', 'manager', 'worker',
                      'nurse', 'practitioner', 'physician', 'doctor', 'md', 'np']
        
        famous_names = ['maya angelou', 'martin luther', 'oprah winfrey', 'barack obama']
        job_titles = ['social worker', 'case manager', 'program director', 'clinical director',
                     'nurse practitioner', 'nurse', 'practitioner', 'physician assistant']
        
        def is_valid_person_name(name: str) -> bool:
            """Check if name looks like a real person name."""
            name_lower = name.lower()
            words = name.split()
            
            # Must be exactly 2-3 words
            if len(words) < 2 or len(words) > 3:
                return False
            
            # No bad words (check each word individually)
            for word in words:
                if word.lower() in bad_name_words:
                    return False
            
            # Each word should be 2-12 chars
            if not all(2 <= len(w.replace('.', '')) <= 12 for w in words):
                return False
            
            # First word shouldn't be a common non-name
            if words[0].lower() in common_non_names:
                return False
            
            # Last word shouldn't be a role
            if words[-1].lower() in role_words:
                return False
            
            # Filter famous people (quotes/testimonials)
            if name_lower in famous_names:
                return False
            
            # Filter job titles that look like names
            if name_lower in job_titles:
                return False
            
            # Filter location/direction words that aren't names
            location_direction_words = ['north', 'south', 'east', 'west', 'areas', 'cities', 
                                       'county', 'montgomery', 'bethesda', 'arlington']
            if any(w.lower() in location_direction_words for w in words):
                return False
            
            # Filter common phrases (Good Afternoon, etc.)
            common_phrases = ['good afternoon', 'good morning', 'good evening', 'thank you',
                             'click here', 'read more', 'learn more', 'contact us']
            if name_lower in common_phrases:
                return False
            
            # Filter names that look like sentences/phrases (contain common words)
            phrase_words = ['good', 'afternoon', 'morning', 'evening', 'endorsed', 
                           'endorsement', 'powered', 'by', 'engineers', 'where', 
                           'children', 'come', 'first']
            if any(w.lower() in phrase_words for w in words):
                return False
            
            # First and last words should start with capital letters (proper names)
            if not (words[0] and words[0][0].isupper() and words[-1] and words[-1][0].isupper()):
                return False
            
            return True
        
        # Pattern 1: STRICT - "FirstName LastName, CREDENTIAL"
        # Only match: "John Smith, PhD" or "Jane Doe, LCSW"
        strict_cred_pattern = rf'\b([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}}),\s*({CRED_PATTERN})\b'
        for match in re.findall(strict_cred_pattern, content):
            name = match[0].strip()
            if is_valid_person_name(name):
                names_with_info.append({"name": name, "title": match[1], "source": "credentials"})
        
        # Pattern 2: Dr./Mr./Ms. prefix - STRICT
        prefix_pattern = r'\b(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
        for match in re.findall(prefix_pattern, content):
            name = match.strip()
            if is_valid_person_name(name):
                names_with_info.append({"name": name, "title": "Dr.", "source": "prefix"})
        
        # Pattern 3: Extract names from email patterns (john.smith@example.com -> John Smith)
        email_name_pattern = r'([a-z]+)\.([a-z]+)@'
        for match in re.findall(email_name_pattern, content.lower()):
            first, last = match[0].capitalize(), match[1].capitalize()
            name = f"{first} {last}"
            if is_valid_person_name(name) and len(first) > 2 and len(last) > 2:
                names_with_info.append({"name": name, "title": None, "source": "email"})
        
        # Layer 2 removed - was causing too many false positives
        
        # =================================================================
        # DETECT PROFESSION - Use category if provided, otherwise auto-detect
        # =================================================================
        
        detected_profession = None
        profession_reason = None
        
        # If category is provided, use it for tagging (more accurate)
        if category and category in PROSPECT_CATEGORIES:
            detected_profession = PROSPECT_CATEGORIES[category]["name"]
            profession_reason = f"Category: {category}"
            logger.info(f"Tagging prospects with category: {detected_profession} (from category: {category})")
        else:
            logger.warning(f"No category provided for extraction - will auto-detect from content")
            # Fallback: Auto-detect from content keywords
            for cat_id, cat_info in PROSPECT_CATEGORIES.items():
                for kw in cat_info["keywords"]:
                    if kw.lower() in content.lower():
                        detected_profession = cat_info["name"]
                        profession_reason = f"Found keyword: {kw}"
                        break
                if detected_profession:
                    break
        
        # =================================================================
        # BUILD PROSPECT OBJECTS - Match contact info to names by proximity
        # =================================================================
        
        seen_names = set()
        used_emails = set()
        used_phones = set()
        
        for i, info in enumerate(names_with_info):
            name = info["name"]
            
            # Skip duplicates
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            
            # Find name position in content
            name_pos = content.find(name)
            
            # Extract bio snippet around the name (larger window for contact search)
            bio_snippet = None
            nearby_content = ""
            if name_pos >= 0:
                start = max(0, name_pos - 100)
                end = min(len(content), name_pos + len(name) + 500)
                nearby_content = content[start:end]
                bio_snippet = content[max(0, name_pos - 50):min(len(content), name_pos + len(name) + 200)].strip()
            
            # Find email near this name (within nearby_content)
            prospect_email = None
            nearby_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', nearby_content)
            for email in nearby_emails:
                email_lower = email.lower()
                if email not in used_emails and not any(email_lower.startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES):
                    if not email.endswith(('.png', '.jpg', '.gif')) and '@sentry' not in email_lower:
                        prospect_email = email
                        used_emails.add(email)
                        break
            
            # If no nearby email, try from global list
            if not prospect_email:
                for email in emails:
                    if email not in used_emails:
                        prospect_email = email
                        used_emails.add(email)
                        break
            
            # Find phone near this name
            prospect_phone = None
            nearby_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby_content)
            for phone in nearby_phones:
                if phone not in used_phones:
                    prospect_phone = phone
                    used_phones.add(phone)
                    break
            
            # If no nearby phone, try from global list
            if not prospect_phone:
                for phone in phones:
                    if phone not in used_phones:
                        prospect_phone = phone
                        used_phones.add(phone)
                        break
            
            # Try to extract website URL from nearby content
            prospect_website = None
            website_patterns = [
                r'https?://(?:www\.)?[\w\.-]+\.\w+(?:/[\w\.-]*)*',
                r'www\.[\w\.-]+\.\w+',
            ]
            for pattern in website_patterns:
                websites = re.findall(pattern, nearby_content)
                for site in websites:
                    if site != url and 'facebook' not in site and 'twitter' not in site and 'linkedin' not in site:
                        prospect_website = site if site.startswith('http') else f'https://{site}'
                        break
                if prospect_website:
                    break
            
            # Extract organization for this prospect
            prospect_organization = self._extract_organization(content, url)
            
            prospect = DiscoveredProspect(
                name=name,
                title=info.get("title"),
                organization=prospect_organization,
                specialty=[detected_profession] if detected_profession else [],
                source_url=url,
                source=source,
                contact=ProspectContact(
                    email=prospect_email,
                    phone=prospect_phone,
                    website=prospect_website,
                ),
                bio_snippet=bio_snippet or content[:200],
            )
            
            # Log what we found
            logger.info(f"Extracted prospect: {name} | email: {prospect_email} | phone: {prospect_phone} | website: {prospect_website}")
            
            # Add profession reason as metadata
            if profession_reason:
                prospect.bio_snippet = f"{profession_reason}. {prospect.bio_snippet or ''}"
            
            prospects.append(prospect)
            
            if len(prospects) >= 10:  # Limit per page
                break
        
        # =================================================================
        # FALLBACK: If no names but have contact info, use email-based name
        # =================================================================
        
        if not prospects and emails:
            for email in emails[:3]:
                name_from_email = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                # Clean up common patterns
                name_from_email = re.sub(r'\d+', '', name_from_email).strip()
                
                if len(name_from_email) >= 3:
                    prospect = DiscoveredProspect(
                        name=name_from_email,
                        title=detected_profession,
                        source_url=url,
                        source=source,
                        contact=ProspectContact(email=email),
                        bio_snippet=content[:200] if content else None,
                    )
                    prospects.append(prospect)
        
        return prospects
    
    def calculate_fit_score(
        self,
        prospect: DiscoveredProspect,
        target_specialty: Optional[str] = None,
        target_location: Optional[str] = None,
        categories: List[str] = None
    ) -> int:
        """
        Calculate influence score for a prospect (0-100)
        
        Scoring:
        - Direct influence on schooling: +40
        - Has contact info (email/phone): +20
        - DC/DMV location match: +20
        - Works with ages 10-18: +10
        - High socioeconomic clientele: +10
        - Group leadership role: +10
        """
        score = 0
        content_to_check = f"{prospect.bio_snippet or ''} {prospect.title or ''} {' '.join(prospect.specialty or [])}".lower()
        
        # =================================================================
        # DIRECT INFLUENCE ON K-12 DECISIONS (+40)
        # =================================================================
        
        high_influence_keywords = [
            'pediatrician', 'psychologist', 'psychiatrist', 'therapist',
            'educational consultant', 'school counselor', 'admissions',
            'treatment center', 'embassy', 'education officer', 'cultural officer',
            'athletic director', 'sports academy', 'coach',
            'mom group', 'parent network', 'pta', 'family services'
        ]
        
        if any(kw in content_to_check for kw in high_influence_keywords):
            score += 40
        elif prospect.title:
            # Check title for influence indicators
            title_lower = prospect.title.lower()
            if any(kw in title_lower for kw in ['director', 'founder', 'president', 'lead', 'chief', 'head']):
                score += 30
            else:
                score += 10  # Base for having any title
        
        # =================================================================
        # CONTACT INFO (+20)
        # =================================================================
        
        if prospect.contact.email:
            score += 15
        if prospect.contact.phone:
            score += 5
        
        # =================================================================
        # DC/DMV LOCATION MATCH (+20)
        # =================================================================
        
        location_content = f"{prospect.location or ''} {prospect.bio_snippet or ''} {prospect.source_url or ''}".lower()
        
        dc_keywords = ['washington dc', 'dc', 'd.c.', 'dmv', 'nova', 'northern virginia',
                      'montgomery county', 'fairfax', 'arlington', 'bethesda', 'silver spring',
                      'alexandria', 'chevy chase', 'georgetown', 'potomac', 'mclean', 'rockville']
        
        if target_location:
            target_lower = target_location.lower()
            is_dc_search = any(v in target_lower for v in ['dc', 'washington', 'dmv'])
            
            if is_dc_search:
                if any(kw in location_content for kw in dc_keywords):
                    score += 20
            elif target_lower in location_content:
                score += 20
        
        # =================================================================
        # WORKS WITH AGES 10-18 (+10)
        # =================================================================
        
        age_keywords = ['adolescent', 'teen', 'teenager', 'youth', 'k-12', 'k12',
                       'middle school', 'high school', 'ages 10', 'ages 11', 'ages 12',
                       'ages 13', 'ages 14', 'ages 15', 'ages 16', 'ages 17', 'ages 18',
                       'child', 'children', 'young', 'student']
        
        if any(kw in content_to_check for kw in age_keywords):
            score += 10
        
        # =================================================================
        # HIGH SOCIOECONOMIC CLIENTELE (+10)
        # =================================================================
        
        affluent_keywords = ['private school', 'boarding school', 'prep school', 'independent school',
                            'embassy', 'diplomat', 'elite', 'premier', 'exclusive', 'luxury',
                            'concierge', 'executive', 'professional']
        
        if any(kw in content_to_check for kw in affluent_keywords):
            score += 10
        
        # =================================================================
        # GROUP LEADERSHIP (+10)
        # =================================================================
        
        leadership_keywords = ['founder', 'director', 'president', 'chair', 'leader',
                              'organizer', 'coordinator', 'head of', 'chief']
        
        if any(kw in content_to_check for kw in leadership_keywords):
                score += 10
        
        # =================================================================
        # CATEGORY MATCH BONUS
        # =================================================================
        
        if categories:
            for cat_id in categories:
                cat_info = PROSPECT_CATEGORIES.get(cat_id, {})
                cat_keywords = cat_info.get("keywords", [])
                if any(kw.lower() in content_to_check for kw in cat_keywords):
                    score += 5
                    break
        
        return min(score, 100)
    
    async def _extract_with_llm(
        self,
        content: str,
        url: str,
        categories: List[str] = None
    ) -> List[DiscoveredProspect]:
        """
        Layer 3: LLM fallback extraction using Perplexity free tier.
        Called only when regex/heuristics fail but contact info exists.
        """
        if not self.perplexity:
            return []
        
        # Truncate content to save tokens
        content_snippet = content[:3000] if len(content) > 3000 else content
        
        category_context = ""
        if categories:
            cat_names = [PROSPECT_CATEGORIES.get(c, {}).get("name", c) for c in categories]
            category_context = f"Focus on finding: {', '.join(cat_names)}"
        
        prompt = f"""Extract prospect information from this webpage content.

{category_context}

Return ONLY if you find a real person (not a company). Format as JSON:
{{
  "name": "Full Name",
  "title": "Job title or credentials",
  "organization": "Company or org name",
  "profession": "e.g. Pediatrician, Educational Consultant, Embassy Officer",
  "email": "if found",
  "phone": "if found",
  "reason": "Why this person influences K-12 education decisions"
}}

If no individual person is found, return: {{"found": false}}

Content:
{content_snippet}"""

        try:
            response = self.perplexity.search(query=prompt)
            
            # Parse JSON response
            import json
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                if data.get("found") == False or not data.get("name"):
                    return []
                
                prospect = DiscoveredProspect(
                    name=data.get("name", "Unknown"),
                    title=data.get("title"),
                    organization=data.get("organization"),
                    specialty=[data.get("profession")] if data.get("profession") else [],
                    source_url=url,
                    source=ProspectSource.GENERAL_SEARCH,
                    contact=ProspectContact(
                        email=data.get("email"),
                        phone=data.get("phone"),
                    ),
                    bio_snippet=data.get("reason"),
                )
                return [prospect]
                
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
        
        return []
    
    async def _enrich_contact_with_llm(
        self,
        prospect: DiscoveredProspect,
        location: str
    ) -> Optional[Dict[str, str]]:
        """Use Perplexity to find contact info for a prospect."""
        if not self.perplexity:
            return None
        
        try:
            prompt = f"""Find the verified contact information for this professional:
Name: {prospect.name}
Organization: {prospect.organization or 'Unknown'}
Title: {prospect.title or 'Unknown'}
Location: {location}

Search for their official website, email address, and phone number.
Return ONLY a JSON object with these fields (use null if not found):
{{"email": "their@email.com", "phone": "123-456-7890", "website": "https://example.com"}}

Important: Only return verified, publicly available contact information. Do not guess."""

            response = self.perplexity.search(query=prompt)
            
            if response and response.answer:
                text = response.answer
                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', text)
                if json_match:
                    data = json.loads(json_match.group())
                    # Validate email format
                    if data.get("email") and "@" not in data["email"]:
                        data["email"] = None
                    return data
                    
        except Exception as e:
            logger.warning(f"LLM contact enrichment failed: {e}")
        
        return None
    
    async def discover_prospects(
        self,
        request: ProspectDiscoveryRequest
    ) -> ProspectDiscoveryResponse:
        """
        Discover prospects from a public source.
        
        Process:
        1. Build search query
        2. Search Google for source URLs
        3. Scrape each URL
        4. Extract prospect data
        5. Score and rank
        6. Optionally save to prospects
        """
        self._init_clients()
        
        discovery_id = f"discovery_{request.source.value}_{int(time.time())}"
        
        logger.info(f"Starting prospect discovery: {discovery_id}")
        logger.info(f"Source: {request.source}, Specialty: {request.specialty}, Location: {request.location}")
        
        # Build search query
        search_query = self.build_search_query(
            source=request.source,
            specialty=request.specialty,
            location=request.location,
            keywords=request.keywords
        )
        
        logger.info(f"Search query: {search_query}")
        
        # Use Firecrawl to search and scrape
        all_prospects = []
        
        try:
            # Search for URLs (using Firecrawl's search if available, or scrape known directory URLs)
            urls_to_scrape = []
            
            # For Psychology Today, construct direct URLs
            if request.source == ProspectSource.PSYCHOLOGY_TODAY:
                # Handle DC specially
                if request.location and "dc" in request.location.lower():
                    location_slug = "district-of-columbia"
                elif request.location:
                    location_slug = request.location.lower().replace(" ", "-")
                else:
                    location_slug = "district-of-columbia"
                
                specialty_slug = request.specialty.lower().replace(" ", "-") if request.specialty else ""
                
                # Build URLs - use specialty in query param
                if specialty_slug:
                    urls_to_scrape = [
                        f"https://www.psychologytoday.com/us/therapists/{location_slug}?spec=187",  # 187 = educational consultant
                        f"https://www.psychologytoday.com/us/therapists/{location_slug}?category=educational-consultant",
                    ]
                else:
                    urls_to_scrape = [
                        f"https://www.psychologytoday.com/us/therapists/{location_slug}",
                    ]
            
            # For IECA, use their search
            elif request.source == ProspectSource.IECA_DIRECTORY:
                urls_to_scrape = [
                    "https://www.iecaonline.com/quick-search/",
                ]
            
            # For general search, we'd use Google Custom Search
            else:
                # Fallback: scrape based on the search query pattern
                urls_to_scrape = []
            
            # Scrape each URL
            for url in urls_to_scrape[:5]:  # Limit to 5 URLs
                try:
                    logger.info(f"Scraping: {url}")
                    scraped = self.firecrawl.scrape_url(url)
                    
                    if scraped and scraped.content:
                        prospects = self.extract_prospects_from_content(
                            content=scraped.content,
                            url=url,
                            source=request.source
                        )
                        all_prospects.extend(prospects)
                        
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue
            
            # Calculate fit scores
            if request.auto_score:
                for prospect in all_prospects:
                    prospect.fit_score = self.calculate_fit_score(
                        prospect,
                        target_specialty=request.specialty,
                        target_location=request.location
                    )
            
            # Sort by fit score
            all_prospects.sort(key=lambda p: p.fit_score, reverse=True)
            
            # Limit results
            all_prospects = all_prospects[:request.max_results]
            
            # Store discovery results
            self._store_discovery(request.user_id, discovery_id, request, all_prospects, search_query)
            
            # Optionally save to prospects collection
            if request.save_to_prospects and all_prospects:
                self._save_to_prospects(request.user_id, all_prospects)
            
            return ProspectDiscoveryResponse(
                success=True,
                discovery_id=discovery_id,
                source=request.source.value,
                total_found=len(all_prospects),
                prospects=all_prospects,
                search_query_used=search_query,
            )
            
        except Exception as e:
            logger.exception(f"Prospect discovery failed: {e}")
            return ProspectDiscoveryResponse(
                success=False,
                discovery_id=discovery_id,
                source=request.source.value,
                total_found=0,
                error=str(e),
            )
    
    def _store_discovery(
        self,
        user_id: str,
        discovery_id: str,
        request: ProspectDiscoveryRequest,
        prospects: List[DiscoveredProspect],
        search_query: str
    ):
        """Store discovery results in Firestore"""
        doc_data = {
            "discovery_id": discovery_id,
            "source": request.source.value,
            "specialty": request.specialty,
            "location": request.location,
            "keywords": request.keywords,
            "search_query": search_query,
            "total_found": len(prospects),
            "prospects": [p.dict() for p in prospects],
            "created_at": time.time(),
        }
        
        doc_ref = db.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
        doc_ref.set(doc_data)
        
        logger.info(f"Stored discovery: {discovery_id} with {len(prospects)} prospects")
    
    def _save_to_prospects(self, user_id: str, prospects: List[DiscoveredProspect]):
        """Save discovered prospects to the main prospects collection (skip duplicates)"""
        saved_count = 0
        
        # Final validation filter - remove garbage names and invalid prospects
        def is_valid_prospect_for_saving(p: DiscoveredProspect) -> bool:
            """Final validation check before saving prospect"""
            if not p.name or not p.name.strip():
                return False
            
            name = p.name.strip()
            name_lower = name.lower()
            words = name.split()
            
            # Must be 2-3 words (proper person names)
            if len(words) < 2 or len(words) > 3:
                logger.info(f"Filtering out invalid prospect (word count: {len(words)} words): {name}")
                return False
            
            # IMPORTANT: Check if name is a DC neighborhood - if so, allow it (but still check other validations)
            # DC neighborhoods are valid location names and should not be filtered
            dc_neighborhoods_lower = [n.lower() for n in DC_NEIGHBORHOODS]
            is_dc_neighborhood = name_lower in dc_neighborhoods_lower
            
            # Check for bad words (but skip location-related words if it's a DC neighborhood)
            bad_words = [
                'areas', 'cities', 'bethesda', 'endorsed', 'endorsement',
                'north', 'south', 'east', 'west', 'good', 'afternoon',
                'morning', 'evening', 'powered', 'by', 'engineers',
                'where', 'children', 'come', 'first', 'educational',
                'administrative', 'outreach', 'experience', 'engagement',
                'nurse', 'practitioner',  # Job titles, not names
                'played', 'playing', 'will', 'was', 'were', 'been',  # Verbs
                'bilingual', 'clinical',  # These are descriptors, not names
                'janak', 'scadmoa',  # Invalid single words that might appear
            ]
            # Only add location words to bad_words if it's NOT a DC neighborhood
            if not is_dc_neighborhood:
                bad_words.extend(['capitol', 'heights'])
            
            if any(w.lower() in bad_words for w in words):
                logger.info(f"Filtering out invalid prospect (bad words in name): {name}")
                return False
            
            # Filter location-only names (but allow DC neighborhoods and location words if they're part of a real person name)
            # Only filter if the name looks like a location phrase, not a person name
            location_phrases = ['areas cities', 'north bethesda', 'south bethesda', 'east bethesda',
                              'west bethesda', 'montgomery county', 'fairfax county', 'north arlington',
                              'south arlington', 'silver spring', 'chevy chase', 'capitol heights']
            # Filter out location phrases (these are places, not people)
            # DC neighborhoods are valid place names, but they shouldn't be person names
            name_lower_phrase = name_lower.replace(' ', ' ')
            if name_lower_phrase in location_phrases or name_lower_phrase.startswith('areas ') or name_lower_phrase.startswith('cities '):
                logger.info(f"Filtering out invalid prospect (location phrase, not a person): {name}")
                return False
            
            # Filter if name starts with location direction words (likely location phrases)
            # But skip this check for DC neighborhoods
            if not is_dc_neighborhood:
                location_directions = ['north', 'south', 'east', 'west', 'areas', 'cities']
                if words[0].lower() in location_directions and len(words) == 2:
                    # Check if second word is also a location (e.g., "North Bethesda")
                    common_location_second_words = ['bethesda', 'arlington', 'fairfax', 'alexandria', 
                                                   'georgetown', 'potomac', 'montgomery', 'cleveland',
                                                   'heights', 'park', 'springs', 'county']
                    if words[1].lower() in common_location_second_words:
                        logger.info(f"Filtering out invalid prospect (location phrase): {name}")
                        return False
            
            # Filter role words at end of name (e.g., "John Counselor", "Jane Director", "Bilingual Clinical")
            role_words = ['counselor', 'director', 'therapist', 'psychologist', 'psychiatrist', 'coach',
                         'specialist', 'consultant', 'advisor', 'manager', 'worker', 'officer', 'athletic',
                         'clinical', 'bilingual', 'licensed', 'certified', 'registered']
            if words[-1].lower() in role_words:
                logger.info(f"Filtering out invalid prospect (role/descriptor word at end): {name}")
                return False
            
            # Filter if name starts with a role/descriptor (e.g., "Bilingual Clinical", "Licensed Therapist")
            if words[0].lower() in role_words:
                logger.info(f"Filtering out invalid prospect (role/descriptor word at start): {name}")
                return False
            
            # Filter phrases and names starting with bad prefixes
            phrases = ['good afternoon', 'good morning', 'good evening']
            if name_lower in phrases or any(phrase in name_lower for phrase in phrases):
                logger.debug(f"Filtering out invalid prospect (phrase): {name}")
                return False
            
            # Filter names starting with common prefixes that aren't person names
            bad_prefixes = ['endorsed', 'endorsement', 'areas', 'cities']
            if any(name_lower.startswith(prefix + ' ') for prefix in bad_prefixes):
                logger.info(f"Filtering out invalid prospect (bad prefix): {name}")
                return False
            
            # Must start with capital letters
            if not (words[0] and words[0][0].isupper() and words[-1] and words[-1][0].isupper()):
                logger.debug(f"Filtering out invalid prospect (capitalization): {name}")
                return False
            
            # Validate organization name if present
            if p.organization:
                org_lower = p.organization.lower().strip()
                
                # Filter out sentences/phrases that look like content, not organization names
                # Organization names should be 2-5 words max, not full sentences
                org_words = p.organization.split()
                
                # Sentence patterns that indicate this is not an organization name
                sentence_patterns = [
                    'may also be', 'are also known', 'can also', 'will also',
                    'is also', 'and hospital', 'pediatricians may', 'psychologists may',
                    'may also be known', 'are also known as', 'by the following'
                ]
                
                # Check for sentence patterns first (most reliable indicator)
                if any(pattern in org_lower for pattern in sentence_patterns):
                    logger.info(f"Filtering out invalid organization (contains sentence pattern): {name} | {p.organization[:60]}...")
                    p.organization = None
                elif len(org_words) >= 10:  # 10+ words is definitely a sentence
                    logger.info(f"Filtering out invalid organization (too long, looks like a sentence): {name} | {p.organization[:50]}...")
                    p.organization = None
                elif len(org_words) > 6:  # 7-9 words is suspicious
                    logger.info(f"Filtering out invalid organization (too many words for org name): {name} | {p.organization[:60]}...")
                    p.organization = None
                
                # Template phrases (duplicate check for safety)
                template_phrases = ['powered by', 'built with', 'designed by', 'is powered by',
                                   'in the united states', 'where children come first',
                                   'in united states', 'the united states', 'in the us',
                                   'may also be known', 'are also known as', 'and hospital',
                                   'by the following', 'the following']
                if any(phrase in org_lower for phrase in template_phrases):
                    logger.info(f"Filtering out invalid organization (template phrase): {name} | {p.organization[:60]}...")
                    p.organization = None  # Clear bad org instead of filtering prospect
                # Check if organization is exactly a template phrase
                if org_lower in ['where children come first', 'in the united states', 'in united states', 
                                'the united states', 'in the us']:
                    logger.info(f"Filtering out invalid prospect (template organization name): {name} | {p.organization}")
                    p.organization = None
                # Filter out directory/aggregator sites (not actual organizations)
                directory_sites = ['psychologytoday', 'psychology today', 'healthgrades', 'webmd', 
                                 'zocdoc', 'vitals', 'ratemds', 'doctor.com', 'pmc', 'ncbi',
                                 'callsource', 'indeed', 'glassdoor', 'linkedin', 'savannahmastercalendar',
                                 'royaltyinstitute']
                if org_lower in directory_sites or any(ds in org_lower for ds in directory_sites):
                    # Directory sites are not organizations - set to None
                    p.organization = None
                    logger.debug(f"Filtering out directory site as organization: {org_lower} for {name}")
            
            return True
        
        # Filter prospects before saving
        valid_prospects = [p for p in prospects if is_valid_prospect_for_saving(p)]
        filtered_count = len(prospects) - len(valid_prospects)
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} invalid prospects before saving (from {len(prospects)} total)")
        
        # Final cleanup: Ensure any remaining bad organizations are cleared
        for prospect in valid_prospects:
            if prospect.organization:
                org_lower = prospect.organization.lower().strip()
                org_words = prospect.organization.split()
                
                # Double-check for sentence patterns
                sentence_patterns = [
                    'may also be', 'are also known', 'can also', 'will also',
                    'is also', 'and hospital', 'pediatricians may', 'psychologists may',
                    'may also be known', 'are also known as', 'by the following'
                ]
                
                if any(pattern in org_lower for pattern in sentence_patterns):
                    logger.info(f"[CLEANUP] Clearing bad organization: {prospect.name} | {prospect.organization[:60]}...")
                    prospect.organization = None
                elif len(org_words) >= 10:
                    logger.info(f"[CLEANUP] Clearing long organization (10+ words): {prospect.name} | {prospect.organization[:60]}...")
                    prospect.organization = None
                elif len(org_words) > 6:
                    logger.info(f"[CLEANUP] Clearing long organization (7-9 words): {prospect.name} | {prospect.organization[:60]}...")
                    prospect.organization = None
        
        logger.info(f"Attempting to save {len(valid_prospects)} valid prospects (filtered {filtered_count} invalid)")
        
        # Track categories for summary
        category_counts = {}
        
        for prospect in valid_prospects:
            # Create unique doc ID from email or name
            if prospect.contact.email:
                doc_id = prospect.contact.email.replace("@", "_at_").replace(".", "_")
            else:
                # Use name-based ID to prevent duplicates
                doc_id = prospect.name.lower().replace(" ", "_").replace(".", "")
            
            doc_ref = db.collection("users").document(user_id).collection("prospects").document(doc_id)
            
            # Check if already exists - skip if so
            if doc_ref.get().exists:
                logger.debug(f"Skipping duplicate prospect: {prospect.name}")
                continue
            
            prospect_doc = {
                "name": prospect.name,
                "title": prospect.title,
                "company": prospect.organization,
                "email": prospect.contact.email,
                "phone": prospect.contact.phone,
                "website": prospect.contact.website,
                "location": prospect.location,
                "source": f"discovery:{prospect.source.value}",
                "source_url": prospect.source_url,
                "fit_score": prospect.fit_score,
                "status": "new",
                "tags": prospect.specialty or [],
                "bio_snippet": prospect.bio_snippet,
                "created_at": time.time(),
            }
            
            # Track category
            category_tag = prospect.specialty[0] if prospect.specialty else "Unknown"
            category_counts[category_tag] = category_counts.get(category_tag, 0) + 1
            
            logger.info(f"[SAVE] {prospect.name} | Category: {category_tag} | Org: {prospect.organization} | Email: {prospect.contact.email or 'N/A'} | Phone: {prospect.contact.phone or 'N/A'}")
            doc_ref.set(prospect_doc)
            saved_count += 1
        
        duplicate_count = len(valid_prospects) - saved_count
        logger.info(f"=== SAVE SUMMARY ===")
        logger.info(f"Total prospects found: {len(prospects)}")
        logger.info(f"Filtered (invalid): {filtered_count}")
        logger.info(f"Valid prospects: {len(valid_prospects)}")
        logger.info(f"Duplicates skipped: {duplicate_count}")
        logger.info(f"Successfully saved: {saved_count}")
        logger.info(f"=== CATEGORY BREAKDOWN ===")
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {cat}: {count} prospects")
    
    async def scrape_urls(
        self,
        user_id: str,
        urls: List[str],
        source_type: str = "direct_url"
    ) -> ProspectDiscoveryResponse:
        """
        Scrape specific URLs for prospect data.
        Use this when you have direct profile URLs (e.g., from Psychology Today).
        """
        self._init_clients()
        
        discovery_id = f"discovery_urls_{int(time.time())}"
        all_prospects = []
        
        logger.info(f"Scraping {len(urls)} direct URLs")
        
        for url in urls[:20]:  # Limit to 20 URLs
            try:
                logger.info(f"Scraping: {url}")
                scraped = self.firecrawl.scrape_url(url)
                
                if scraped and scraped.content:
                    # Determine source from URL
                    source = ProspectSource.GENERAL_SEARCH
                    if "psychologytoday.com" in url:
                        source = ProspectSource.PSYCHOLOGY_TODAY
                    elif "iecaonline.com" in url:
                        source = ProspectSource.IECA_DIRECTORY
                    
                    prospects = self.extract_prospects_from_content(
                        content=scraped.content,
                        url=url,
                        source=source
                    )
                    
                    # For single profile pages, we might get just one prospect
                    # Add the URL as additional context
                    for p in prospects:
                        p.source_url = url
                    
                    all_prospects.extend(prospects)
                    
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")
                continue
        
        # Calculate fit scores
        for prospect in all_prospects:
            prospect.fit_score = self.calculate_fit_score(prospect)
        
        # Sort by fit score
        all_prospects.sort(key=lambda p: p.fit_score, reverse=True)
        
        # Store results
        doc_data = {
            "discovery_id": discovery_id,
            "source": "direct_urls",
            "urls_scraped": urls,
            "total_found": len(all_prospects),
            "prospects": [p.dict() for p in all_prospects],
            "created_at": time.time(),
        }
        
        doc_ref = db.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
        doc_ref.set(doc_data)
        
        return ProspectDiscoveryResponse(
            success=True,
            discovery_id=discovery_id,
            source="direct_urls",
            total_found=len(all_prospects),
            prospects=all_prospects,
            search_query_used=f"Direct scrape of {len(urls)} URLs",
        )
    
    def build_category_search_query(
        self,
        categories: List[str],
        location: str,
        additional_context: Optional[str] = None
    ) -> str:
        """Build an optimized search query based on selected categories"""
        
        # Collect search terms from selected categories
        search_terms = []
        for cat_id in categories:
            cat_info = PROSPECT_CATEGORIES.get(cat_id, {})
            terms = cat_info.get("search_terms", [])
            if terms:
                search_terms.extend(terms[:2])  # Take top 2 from each category
        
        # If no categories selected, use general terms
        if not search_terms:
            search_terms = ["educational consultant", "pediatrician", "therapist"]
        
        # Build location part
        location_lower = location.lower() if location else ""
        is_dc = any(v in location_lower for v in ['dc', 'washington', 'dmv'])
        
        if is_dc:
            location_query = DC_LOCATION_QUERY
        else:
            location_query = f'"{location}"' if location else ""
        
        # Combine terms with OR
        terms_query = " OR ".join(f'"{t}"' for t in search_terms[:5])  # Limit to 5 terms
        
        # Build final query with category-specific site preferences
        query_parts = [f"({terms_query})", location_query]
        if additional_context:
            query_parts.append(additional_context)
        
        # Category-specific directory preferences
        medical_cats = ['pediatricians', 'psychologists', 'treatment_centers']
        sports_cats = ['youth_sports', 'athletic_academies']
        education_cats = ['education_consultants', 'school_counselors', 'tutoring_centers']
        community_cats = ['mom_groups', 'parenting_coaches', 'youth_programs']
        
        # Category-specific search optimization for ALL categories
        # Combine site preferences from ALL selected categories (not just first match)
        
        # Check which categories are selected (handle various naming formats)
        has_pediatricians = any(cat in ['pediatricians', 'pediatric'] for cat in categories)
        has_psychologists = any(cat in ['psychologists', 'psychiatrists', 'psychologists_psychiatrists'] for cat in categories)
        has_treatment = any(cat in ['treatment_centers', 'treatment'] for cat in categories)
        has_embassies = any(cat in ['embassies', 'diplomats'] for cat in categories)
        has_sports = any(cat in ['youth_sports', 'athletic_academies', 'youth_sports_programs'] for cat in categories)
        has_mom_groups = any(cat in ['mom_groups', 'parent_networks', 'mom_groups_parent_networks'] for cat in categories)
        has_international = any(cat in ['international_students', 'international_student_services'] for cat in categories)
        has_education = any(cat in ['education_consultants', 'school_counselors'] for cat in categories)
        
        # Collect site preferences from ALL selected categories
        site_preferences = []
        category_keywords = []
        
        if has_pediatricians:
            site_preferences.append("site:healthgrades.com OR site:vitals.com OR site:webmd.com")
        if has_psychologists:
            # Prioritize Psychology Today profile pages specifically (therapist/psychiatrist profiles with IDs)
            # Use more specific site targeting to get actual profile pages
            site_preferences.append("site:psychologytoday.com/us/therapists OR site:psychologytoday.com/us/psychiatrists")
            # Add location-specific search terms for DC area
            category_keywords.append("(\"child psychologist\" OR \"adolescent psychiatrist\" OR \"family therapist\" OR \"teen therapist\" OR \"child therapist\") (\"Washington DC\" OR \"District of Columbia\" OR Bethesda OR \"North Bethesda\" OR Arlington OR \"Montgomery County\")")
        if has_treatment:
            # Target treatment center websites specifically, not Psychology Today
            category_keywords.append("\"residential treatment center\" OR \"therapeutic boarding school\" OR \"adolescent treatment\" OR \"RTC\" (\"admissions director\" OR \"clinical director\" OR \"intake coordinator\" OR \"program director\") email contact")
            # Remove Psychology Today - not primary source for treatment centers
            # site_preferences.append("site:psychologytoday.com")
        if has_embassies:
            # Target embassy and consulate websites
            site_preferences.append("site:*.embassy. OR site:*.consulate. OR site:*.gov")
            category_keywords.append("\"education officer\" OR \"education attaché\" OR \"cultural attaché\" OR \"cultural officer\" OR \"diplomatic family services\" (Washington DC OR \"District of Columbia\") email contact")
        if has_sports:
            category_keywords.append("\"athletic academy\" OR \"sports academy\" OR \"elite youth sports\" OR \"travel team\" OR \"youth soccer\" OR \"youth basketball\" (\"athletic director\" OR \"director of coaching\" OR \"program director\" OR \"head coach\") (Washington DC OR \"DMV\" OR \"NOVA\" OR \"Montgomery County\") email contact")
        if has_mom_groups:
            # Target PTA pages and school district parent contacts
            # Focus on public school/district websites where PTA contacts are listed
            category_keywords.append("\"PTA\" OR \"parent teacher association\" OR \"parent coordinator\" (\"Washington DC\" OR \"DC Public Schools\" OR \"Montgomery County Public Schools\" OR Bethesda OR Arlington OR Alexandria) contact email")
            # Target school district and community organization websites
            site_preferences.append("site:*.k12.*.us OR site:*.edu OR site:*.org")
        if has_international:
            # Target school international offices and placement services
            category_keywords.append("\"international student\" OR \"foreign student services\" OR \"host family\" OR \"ESL program\" (\"international advisor\" OR \"student services coordinator\" OR \"admissions counselor\") (Washington DC OR \"DMV\" OR \"Montgomery County\") email contact")
            site_preferences.append("site:*.edu OR site:*.org")
        if has_education:
            category_keywords.append("\"educational consultant\" OR \"college consultant\" OR \"admissions consultant\" email contact")
        
        # Combine all site preferences with OR
        if site_preferences:
            # Deduplicate and combine
            unique_sites = set()
            for pref in site_preferences:
                # Extract site: patterns
                sites = re.findall(r'site:([^\s)]+)', pref)
                unique_sites.update(sites)
            
            if unique_sites:
                combined_sites = " OR ".join(f"site:{site}" for site in unique_sites)
                query_parts.append(f"({combined_sites})")
        
        # Add category keywords if any
        if category_keywords:
            query_parts.append(f"({' OR '.join(category_keywords)})")
        
        # Default if nothing was added
        if not site_preferences and not category_keywords:
            query_parts.append("email OR phone OR contact")
        
        excluded_sites = "-site:linkedin.com -site:facebook.com -site:twitter.com -site:glassdoor.com -site:indeed.com -site:iecaonline.com"
        
        # For psychologists, also exclude common garbage patterns
        if has_psychologists:
            excluded_sites += " -form -document -pdf -download -observation -verification -pta -program"
        
        query_parts.append(excluded_sites)
        
        return " ".join(filter(None, query_parts))
    
    async def _process_search_results(
        self,
        search_results: List,
        category: Optional[str],
        location: str,
        max_urls: int = 5
    ) -> tuple[List[DiscoveredProspect], List[str]]:
        """
        Helper method to process Google search results: scrape URLs and extract prospects.
        Returns tuple of (prospects, scraped_urls).
        """
        from app.models.prospect_discovery import DiscoveredProspect, ProspectSource
        
        all_prospects = []
        urls_scraped = []
        
        # Filter out URLs that can't be scraped
        scrapeable_results = [r for r in search_results 
                              if not any(domain in r.link.lower() for domain in BLOCKED_DOMAINS)]
        
        # Category-specific URL filtering and prioritization
        if category:
            category_lower = category.lower()
            
            # Psychologists: ONLY accept Psychology Today profile URLs (strict filtering)
            if 'psychologists' in category_lower or 'psychiatrists' in category_lower:
                # ONLY keep Psychology Today profile URLs (must have ID number pattern)
                profile_urls = [r for r in scrapeable_results 
                               if 'psychologytoday.com' in r.link.lower() 
                               and (re.search(r'/therapists/[^/]+/\d{4,}', r.link) or re.search(r'/psychiatrists/[^/]+/\d{4,}', r.link))]
                
                if profile_urls:
                    logger.info(f"[CATEGORY: {category}] Found {len(profile_urls)} Psychology Today profile URLs - using ONLY these")
                    scrapeable_results = profile_urls  # ONLY use profile URLs, reject everything else
                else:
                    logger.warning(f"[CATEGORY: {category}] No Psychology Today profile URLs found - will try all results")
                
                # Also skip obvious garbage URLs
                non_profile_patterns = ['/form', '/document', '/pdf', '/download', '/file', '/observation', '/verification', '/pta', '/program', '/student']
                scrapeable_results = [r for r in scrapeable_results 
                                     if not any(pattern in r.link.lower() for pattern in non_profile_patterns)]
            
            # Treatment Centers: Prioritize treatment center websites, skip generic directories
            elif 'treatment' in category_lower:
                treatment_urls = [r for r in scrapeable_results 
                                 if any(keyword in r.link.lower() for keyword in ['treatment', 'rehab', 'residential', 'therapeutic'])]
                if treatment_urls:
                    logger.info(f"[CATEGORY: {category}] Found {len(treatment_urls)} treatment center URLs - prioritizing these")
                    scrapeable_results = treatment_urls + [r for r in scrapeable_results if r not in treatment_urls]
                
                # Skip directory sites and non-relevant pages
                skip_patterns = ['/directory', '/listings', '/find', '/search', '/psychologytoday.com']
                scrapeable_results = [r for r in scrapeable_results 
                                     if not any(pattern in r.link.lower() for pattern in skip_patterns)]
            
            # Embassies: Prioritize embassy/consulate websites
            elif 'embassies' in category_lower or 'diplomats' in category_lower:
                embassy_urls = [r for r in scrapeable_results 
                               if '.embassy.' in r.link.lower() or '.consulate.' in r.link.lower() or r.link.lower().endswith('.gov')]
                if embassy_urls:
                    logger.info(f"[CATEGORY: {category}] Found {len(embassy_urls)} embassy/consulate URLs - prioritizing these")
                    scrapeable_results = embassy_urls + [r for r in scrapeable_results if r not in embassy_urls]
            
            # Youth Sports: Prioritize academy/club websites
            elif 'sports' in category_lower or 'athletic' in category_lower:
                sports_urls = [r for r in scrapeable_results 
                              if any(keyword in r.link.lower() for keyword in ['academy', 'sports', 'athletic', 'club'])]
                if sports_urls:
                    logger.info(f"[CATEGORY: {category}] Found {len(sports_urls)} sports academy/club URLs - prioritizing these")
                    scrapeable_results = sports_urls + [r for r in scrapeable_results if r not in sports_urls]
            
            # International Students: Prioritize .edu and international office pages
            elif 'international' in category_lower:
                edu_urls = [r for r in scrapeable_results 
                           if '.edu' in r.link.lower() or 'international' in r.link.lower()]
                if edu_urls:
                    logger.info(f"[CATEGORY: {category}] Found {len(edu_urls)} education/international URLs - prioritizing these")
                    scrapeable_results = edu_urls + [r for r in scrapeable_results if r not in edu_urls]
            
            # Mom Groups: Prioritize community/PTA websites, deprioritize social media (blocked anyway)
            elif 'mom' in category_lower or 'parent' in category_lower:
                mom_urls = [r for r in scrapeable_results 
                           if any(keyword in r.link.lower() for keyword in ['pta', 'pta-', 'parent', 'family', 'mom', 'meetup', 'community'])]
                # Remove social media that will be blocked
                mom_urls = [r for r in mom_urls 
                           if not any(social in r.link.lower() for social in ['facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com'])]
                if mom_urls:
                    logger.info(f"[CATEGORY: {category}] Found {len(mom_urls)} community/parent URLs - prioritizing these")
                    scrapeable_results = mom_urls + [r for r in scrapeable_results if r not in mom_urls]
        
        logger.info(f"Filtered {len(search_results)} results to {len(scrapeable_results)} scrapeable URLs")
        
        for result in scrapeable_results[:max_urls]:
            try:
                logger.info(f"Scraping: {result.link}")
                
                # Try Firecrawl first, fallback to free scraping
                combined_content = None
                try:
                    if self.firecrawl:
                        scraped = self.firecrawl.scrape_url(result.link)
                        if scraped and scraped.content:
                            combined_content = scraped.content
                except Exception as fc_error:
                    logger.warning(f"Firecrawl failed, trying free scrape: {fc_error}")
                
                # Fallback to free scraping
                if not combined_content:
                    combined_content = self._free_scrape(result.link)
                
                if combined_content:
                    urls_scraped.append(result.link)
                    
                    # Multi-page scraping: Also scrape /contact, /about, /team pages
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(result.link)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"
                        
                        contact_paths = ['/contact', '/contact-us', '/about', '/about-us', '/team', '/staff', '/our-team']
                        for path in contact_paths[:3]:  # Limit to 3 extra pages
                            try:
                                contact_url = f"{base_url}{path}"
                                contact_content = self._free_scrape(contact_url)
                                if contact_content:
                                    combined_content += f"\n\n--- FROM {path} ---\n" + contact_content
                                    logger.info(f"Also scraped {contact_url}")
                            except Exception:
                                pass  # Contact page doesn't exist, that's fine
                    except Exception as e:
                        logger.warning(f"Multi-page scraping failed: {e}")
                    
                    logger.info(f"[CATEGORY: {category}] Extracting prospects from {result.link}")
                    prospects = self.extract_prospects_from_content(
                        content=combined_content,
                        url=result.link,
                        source=ProspectSource.GENERAL_SEARCH,
                        category=category  # Pass category to ensure correct tagging
                    )
                    
                    logger.info(f"[CATEGORY: {category}] Extracted {len(prospects)} prospects from {result.link}")
                    
                    # Add search result context and extract from snippet
                    for p in prospects:
                        p.source_url = result.link
                        if not p.bio_snippet:
                            p.bio_snippet = result.snippet
                        
                        # Extract contact from Google snippet if not found
                        if result.snippet and (not p.contact.phone or not p.contact.email):
                            snippet_phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', result.snippet)
                            snippet_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', result.snippet)
                            if snippet_phones and not p.contact.phone:
                                p.contact.phone = snippet_phones[0]
                                logger.debug(f"[CATEGORY: {category}] Added phone from snippet for {p.name}")
                            if snippet_emails and not p.contact.email:
                                p.contact.email = snippet_emails[0]
                                logger.debug(f"[CATEGORY: {category}] Added email from snippet for {p.name}")
                        
                        # Use improved organization extraction
                        if not p.organization:
                            p.organization = self._extract_organization(combined_content, result.link)
                            if p.organization:
                                logger.info(f"[CATEGORY: {category}] Extracted organization '{p.organization}' for {p.name}")
                            else:
                                logger.debug(f"[CATEGORY: {category}] No organization found for {p.name} from {result.link}")
                    
                    all_prospects.extend(prospects)
                    
            except Exception as e:
                logger.warning(f"Failed to scrape {result.link}: {e}")
                continue
        
        return all_prospects, urls_scraped
    
    async def find_prospects_free(
        self,
        user_id: str,
        specialty: str,
        location: str,
        additional_context: Optional[str] = None,
        max_results: int = 10,
        categories: List[str] = None
    ) -> ProspectDiscoveryResponse:
        """
        Use Google Custom Search (FREE - 100/day) + Firecrawl to find prospects.
        
        Args:
            categories: List of category IDs from PROSPECT_CATEGORIES
                       e.g., ["pediatricians", "psychologists", "embassies"]
        """
        self._init_clients()
        
        if not self.google_search:
            return ProspectDiscoveryResponse(
                success=False,
                discovery_id="",
                source="google_search",
                total_found=0,
                error="Google Custom Search API not configured"
            )
        
        discovery_id = f"discovery_google_{int(time.time())}"
        
        # Build search query based on categories or specialty
        if categories:
            search_query = self.build_category_search_query(categories, location, additional_context)
        else:
            # Legacy: use specialty directly
            query_parts = [f'"{specialty}"']
            
            # Enhanced DC location handling
            location_lower = location.lower() if location else ""
            is_dc = any(v in location_lower for v in ['dc', 'washington', 'dmv'])
            
            if is_dc:
                query_parts.append(DC_LOCATION_QUERY)
            else:
                query_parts.append(f'"{location}"')
            
            if additional_context:
                query_parts.append(additional_context)
                
                # Detect specialty type and optimize search
                specialty_lower = specialty.lower() if specialty else ""
                
                if any(term in specialty_lower for term in ['therapist', 'psychologist', 'psychiatrist', 'counselor', 'mental health']):
                    query_parts.append("site:psychologytoday.com OR site:healthgrades.com")
                elif any(term in specialty_lower for term in ['pediatrician', 'doctor', 'physician', 'md']):
                    query_parts.append("site:healthgrades.com OR site:vitals.com OR site:webmd.com")
                elif any(term in specialty_lower for term in ['coach', 'sports', 'athletic', 'soccer', 'basketball']):
                    query_parts.append("coach OR director email contact")
                elif any(term in specialty_lower for term in ['consultant', 'education', 'college', 'admissions']):
                    query_parts.append("\"educational consultant\" OR \"college consultant\" email contact")
                else:
                    query_parts.append("email contact")
                
                query_parts.append("-site:linkedin.com -site:facebook.com -site:twitter.com -site:glassdoor.com -site:indeed.com -site:iecaonline.com")
            
            search_query = " ".join(query_parts)
        
        logger.info(f"Categories selected: {categories}")
        logger.info(f"Location: {location}")
        
        try:
            # NEW APPROACH: Run separate search per category for better results
            all_prospects = []
            urls_scraped = []
            all_search_queries = []
            
            if categories and len(categories) > 1:
                # Multi-category: Run separate search per category, then merge
                logger.info(f"Running per-category searches for {len(categories)} categories")
                results_per_category = max(3, max_results // len(categories))  # Distribute max_results across categories
                
                for category in categories:
                    try:
                        logger.info(f"=== PROCESSING CATEGORY: {category} ===")
                        # Build category-specific query
                        category_query = self.build_category_search_query(
                            categories=[category],  # Single category
                            location=location,
                            additional_context=additional_context
                        )
                        all_search_queries.append(f"[{category}]: {category_query}")
                        
                        logger.info(f"[CATEGORY: {category}] Google search query: {category_query}")
                        logger.info(f"[CATEGORY: {category}] Max results per category: {results_per_category}")
                        
                        # Search for this category
                        category_results = self.google_search.search(category_query, num_results=results_per_category)
                        logger.info(f"[CATEGORY: {category}] Google returned {len(category_results) if category_results else 0} search results")
                        
                        if not category_results:
                            logger.warning(f"[CATEGORY: {category}] No search results, skipping")
                            continue
                        
                        # Process this category's results
                        logger.info(f"[CATEGORY: {category}] Processing {len(category_results)} search results...")
                        category_prospects, category_urls = await self._process_search_results(
                            category_results, category, location
                        )
                        
                        all_prospects.extend(category_prospects)
                        urls_scraped.extend(category_urls)
                        
                        logger.info(f"[CATEGORY: {category}] ✅ Extracted {len(category_prospects)} prospects from {len(category_urls)} URLs")
                        logger.info(f"[CATEGORY: {category}] Total prospects so far: {len(all_prospects)}")
                        
                    except Exception as e:
                        logger.warning(f"Error processing category '{category}': {e}")
                        continue
                
                # Combine all queries for logging
                search_query = " | ".join(all_search_queries)
                
            else:
                # Single category or legacy specialty search: Run single combined search
                logger.info(f"Google Search (FREE): {search_query}")
                
                # Step 1: Google Search (FREE)
                search_results = self.google_search.search(search_query, num_results=10)
                logger.info(f"Google search returned {len(search_results) if search_results else 0} results")
                
                if not search_results:
                    logger.warning(f"No Google search results for query: {search_query}")
                    return ProspectDiscoveryResponse(
                        success=True,
                        discovery_id=discovery_id,
                        source="google_search",
                        total_found=0,
                        prospects=[],
                        search_query_used=search_query,
                    )
                
                # Process single search results
                all_prospects, urls_scraped = await self._process_search_results(
                    search_results, 
                    categories[0] if categories else None,
                    location
                )
            
            # Continue with existing enrichment/scoring logic below...
            
            # =================================================================
            # LLM FALLBACK: If we have URLs but no prospects, try LLM extraction
            # =================================================================
            
            if not all_prospects and urls_scraped and self.perplexity:
                logger.info("No prospects from regex, trying LLM fallback...")
                for url in urls_scraped[:2]:  # Limit LLM calls
                    try:
                        content = self._free_scrape(url)
                        if content:
                            llm_prospects = await self._extract_with_llm(
                                content, url, categories
                            )
                            all_prospects.extend(llm_prospects)
                    except Exception as e:
                        logger.warning(f"LLM extraction failed for {url}: {e}")
            
            # =================================================================
            # CONTACT ENRICHMENT: Google search for contact info (FREE)
            # =================================================================
            
            prospects_needing_contact = [p for p in all_prospects if not p.contact.email and not p.contact.phone]
            
            if prospects_needing_contact and self.google_search:
                logger.info(f"Searching Google for contact info for {len(prospects_needing_contact)} prospects...")
                
                for prospect in prospects_needing_contact[:5]:
                    try:
                        # Search Google for this person's contact info
                        contact_query = f'"{prospect.name}" {location} phone email contact'
                        contact_results = self.google_search.search(contact_query, num_results=3)
                        
                        for cr in contact_results:
                            # Check snippet for contact info
                            if cr.snippet:
                                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', cr.snippet)
                                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', cr.snippet)
                                
                                if phones and not prospect.contact.phone:
                                    prospect.contact.phone = phones[0]
                                    logger.info(f"Google found phone for {prospect.name}: {phones[0]}")
                                if emails and not prospect.contact.email:
                                    # Filter generic emails
                                    valid_emails = [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                    if valid_emails:
                                        prospect.contact.email = valid_emails[0]
                                        logger.info(f"Google found email for {prospect.name}: {valid_emails[0]}")
                            
                            # If still missing, quick scrape the result page
                            if not prospect.contact.phone or not prospect.contact.email:
                                page_content = self._free_scrape(cr.link)
                                if page_content:
                                    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', page_content)
                                    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_content)
                                    
                                    if phones and not prospect.contact.phone:
                                        prospect.contact.phone = phones[0]
                                    if emails and not prospect.contact.email:
                                        valid_emails = [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                                        if valid_emails:
                                            prospect.contact.email = valid_emails[0]
                            
                            if prospect.contact.phone and prospect.contact.email:
                                break  # Found both, move to next prospect
                    
                    except Exception as e:
                        logger.warning(f"Google contact search failed for {prospect.name}: {e}")
            
            # =================================================================
            # CALCULATE INFLUENCE SCORES
            # =================================================================
            
            for prospect in all_prospects:
                prospect.fit_score = self.calculate_fit_score(
                    prospect,
                    target_specialty=specialty,
                    target_location=location,
                    categories=categories
                )
            
            # Sort and limit
            all_prospects.sort(key=lambda p: p.fit_score, reverse=True)
            all_prospects = all_prospects[:max_results]
            
            logger.info(f"=== EXTRACTION SUMMARY ===")
            logger.info(f"Total prospects found: {len(all_prospects)}")
            logger.info(f"URLs scraped: {len(urls_scraped)}")
            if all_prospects:
                logger.info(f"Sample prospect: {all_prospects[0].name} - {all_prospects[0].contact.email or 'no email'} - {all_prospects[0].contact.phone or 'no phone'}")
            
            # Store results
            doc_data = {
                "discovery_id": discovery_id,
                "source": "google_search_free",
                "specialty": specialty,
                "location": location,
                "search_query": search_query,
                "urls_scraped": urls_scraped,
                "total_found": len(all_prospects),
                "prospects": [p.dict() for p in all_prospects],
                "created_at": time.time(),
            }
            
            doc_ref = db.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
            doc_ref.set(doc_data)
            
            # Save to main prospects collection so they show in pipeline
            if all_prospects:
                self._save_to_prospects(user_id, all_prospects)
            
            return ProspectDiscoveryResponse(
                success=True,
                discovery_id=discovery_id,
                source="google_search_free",
                total_found=len(all_prospects),
                prospects=all_prospects,
                search_query_used=search_query,
            )
            
        except Exception as e:
            logger.exception(f"Google search failed: {e}")
            return ProspectDiscoveryResponse(
                success=False,
                discovery_id=discovery_id,
                source="google_search_free",
                total_found=0,
                error=str(e)
            )
    
    async def find_prospects_with_ai(
        self,
        user_id: str,
        specialty: str,
        location: str,
        additional_context: Optional[str] = None,
        max_results: int = 10
    ) -> ProspectDiscoveryResponse:
        """
        Use Perplexity AI to find real prospects (PAID).
        Only use this when Google Search free tier is exhausted.
        """
        self._init_clients()
        
        if not self.perplexity:
            return ProspectDiscoveryResponse(
                success=False,
                discovery_id="",
                source="perplexity_ai",
                total_found=0,
                error="Perplexity API not configured"
            )
        
        discovery_id = f"discovery_ai_{int(time.time())}"
        
        # Build a specific prompt for finding prospects
        prompt = f"""List {max_results} specific {specialty}s who work in {location}.

IMPORTANT: Return ACTUAL PEOPLE with their REAL NAMES, not service descriptions.

For each person, format exactly like this:
1. [Full Name], [Credentials like PhD, LCSW, CEP, IECA] - [Organization Name]
   Specialties: [list their focus areas]
   Website: [their website URL]
   Phone: [if publicly available]

{f'Focus on: {additional_context}' if additional_context else ''}

Only include real, verifiable professionals. Do not include generic descriptions like "Admissions Strategy" or "Test Preparation" - I need actual human names like "Jane Smith, CEP" or "Dr. John Doe"."""

        logger.info(f"AI prospect search: {specialty} in {location}")
        
        try:
            # Use Perplexity to search
            research = self.perplexity.research_topic(
                topic=prompt,
                num_results=max_results,
                include_comparison=False
            )
            
            summary = research.get("summary", "")
            sources = research.get("sources", [])
            
            # Parse the AI response to extract prospects
            prospects = self._parse_ai_prospect_response(summary, sources, location)
            
            # Calculate fit scores
            for prospect in prospects:
                prospect.fit_score = self.calculate_fit_score(
                    prospect,
                    target_specialty=specialty,
                    target_location=location
                )
            
            # Sort by fit score
            prospects.sort(key=lambda p: p.fit_score, reverse=True)
            prospects = prospects[:max_results]
            
            # Store results
            doc_data = {
                "discovery_id": discovery_id,
                "source": "perplexity_ai",
                "specialty": specialty,
                "location": location,
                "prompt": prompt,
                "ai_response": summary[:2000],
                "total_found": len(prospects),
                "prospects": [p.dict() for p in prospects],
                "created_at": time.time(),
            }
            
            doc_ref = db.collection("users").document(user_id).collection("prospect_discoveries").document(discovery_id)
            doc_ref.set(doc_data)
            
            return ProspectDiscoveryResponse(
                success=True,
                discovery_id=discovery_id,
                source="perplexity_ai",
                total_found=len(prospects),
                prospects=prospects,
                search_query_used=prompt[:200],
            )
            
        except Exception as e:
            logger.exception(f"AI prospect search failed: {e}")
            return ProspectDiscoveryResponse(
                success=False,
                discovery_id=discovery_id,
                source="perplexity_ai",
                total_found=0,
                error=str(e)
            )
    
    def _parse_ai_prospect_response(
        self,
        response: str,
        sources: List[Dict],
        location: str
    ) -> List[DiscoveredProspect]:
        """Parse Perplexity's response to extract prospect data"""
        prospects = []
        
        # Look for name patterns in the response
        # Common patterns: "Name, Credentials" or "Dr. Name" or numbered lists
        
        # Pattern 1: Numbered list items with names
        numbered_pattern = r'\d+\.\s*\*?\*?([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\*?\*?'
        
        # Pattern 2: Names with credentials
        cred_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s+((?:PhD|PsyD|LCSW|LMFT|LPC|MEd|MA|MS|EdD|MD|CEP|IECA)(?:[,\s]+(?:PhD|PsyD|LCSW|LMFT|LPC|MEd|MA|MS|EdD|MD|CEP|IECA))*)'
        
        # Pattern 3: Dr. prefix
        dr_pattern = r'Dr\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        
        # Extract names
        names_found = []
        
        for pattern in [cred_pattern, dr_pattern, numbered_pattern]:
            matches = re.findall(pattern, response)
            for match in matches:
                if isinstance(match, tuple):
                    names_found.append({"name": match[0], "credentials": match[1] if len(match) > 1 else ""})
                else:
                    names_found.append({"name": match, "credentials": ""})
        
        # Extract websites from sources
        websites = [s.get("url", "") for s in sources if s.get("url")]
        
        # Extract phone numbers from response
        phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', response)
        
        # Extract emails from response
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', response)
        
        # Build prospects
        seen_names = set()
        for i, item in enumerate(names_found):
            name = item["name"].strip()
            
            # Skip duplicates and invalid names
            if name in seen_names or len(name) < 5:
                continue
            
            # Skip common non-name phrases
            skip_words = ["educational", "consultant", "therapist", "psychology", "school", "private"]
            if any(sw in name.lower() for sw in skip_words):
                continue
            
            seen_names.add(name)
            
            prospect = DiscoveredProspect(
                name=name,
                title=item.get("credentials") or None,
                location=location,
                source_url=websites[i] if i < len(websites) else "",
                source=ProspectSource.GENERAL_SEARCH,
                contact=ProspectContact(
                    email=emails[i] if i < len(emails) else None,
                    phone=phones[i] if i < len(phones) else None,
                    website=websites[i] if i < len(websites) else None,
                ),
            )
            prospects.append(prospect)
            
            if len(prospects) >= 15:
                break
        
        return prospects


# Singleton
_service: Optional[ProspectDiscoveryService] = None


def get_prospect_discovery_service() -> ProspectDiscoveryService:
    """Get or create service instance"""
    global _service
    if _service is None:
        _service = ProspectDiscoveryService()
    return _service

