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
            self.firecrawl = get_firecrawl_client()
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
        source: ProspectSource
    ) -> List[DiscoveredProspect]:
        """Extract prospect information from scraped content"""
        prospects = []
        
        # Source-specific extraction
        if source == ProspectSource.PSYCHOLOGY_TODAY:
            return self._extract_psychology_today(content, url, source)
        
        # Generic extraction for other sources
        return self._extract_generic(content, url, source)
    
    def _extract_psychology_today(
        self,
        content: str,
        url: str,
        source: ProspectSource
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
                
            seen_names.add(name)
            
            # Find specialties in nearby content
            found_specialties = []
            for kw in specialty_keywords:
                if kw.lower() in content.lower():
                    found_specialties.append(kw)
            
            prospect = DiscoveredProspect(
                name=name,
                title=item.get("credentials") or "Therapist",
                organization=None,
                specialty=found_specialties[:3],
                location=location,
                source_url=url,
                source=source,
                contact=ProspectContact(
                    phone=phones[len(prospects)] if len(prospects) < len(phones) else None,
                ),
                bio_snippet=None,
            )
            prospects.append(prospect)
            
            if len(prospects) >= 10:  # Limit per page
                break
        
        return prospects
    
    def _extract_generic(
        self,
        content: str,
        url: str,
        source: ProspectSource
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
            'call', 'today', 'now', 'schedule', 'book', 'appointment', 'meeting'
        ]
        
        # Additional non-name words to filter
        common_non_names = ['internet', 'licensed', 'professional', 'clinical', 'certified',
                            'registered', 'national', 'american', 'eclectic', 'compassion',
                            'focused', 'cognitive', 'behavioral', 'mental', 'health',
                            'therapists', 'therapist', 'family', 'adult', 'couples',
                            'marriage', 'anxiety', 'depression', 'trauma', 'addiction']
        
        role_words = ['therapist', 'counselor', 'psychologist', 'psychiatrist', 'coach',
                      'specialist', 'consultant', 'advisor', 'director', 'manager', 'worker']
        
        famous_names = ['maya angelou', 'martin luther', 'oprah winfrey', 'barack obama']
        job_titles = ['social worker', 'case manager', 'program director', 'clinical director']
        
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
        # DETECT PROFESSION FROM CONTENT
        # =================================================================
        
        detected_profession = None
        profession_reason = None
        
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
            
            prospect = DiscoveredProspect(
                name=name,
                title=info.get("title"),
                organization=None,
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
            response = self.perplexity.chat(prompt)
            
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
        
        for prospect in prospects:
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
            
            logger.info(f"Saving prospect: {prospect.name} | email: {prospect.contact.email} | phone: {prospect.contact.phone}")
            doc_ref.set(prospect_doc)
            saved_count += 1
        
        logger.info(f"Saved {saved_count} new prospects (skipped {len(prospects) - saved_count} duplicates)")
    
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
        
        # Build final query - exclude social media sites
        query_parts = [f"({terms_query})", location_query]
        if additional_context:
            query_parts.append(additional_context)
        query_parts.append("(email OR contact)")
        query_parts.append("-site:linkedin.com -site:facebook.com -site:twitter.com")
        
        return " ".join(filter(None, query_parts))
    
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
            
            # Add site preferences for scrape-friendly directories
            query_parts.append("site:psychologytoday.com OR site:healthgrades.com OR site:zocdoc.com OR site:vitals.com OR (email contact)")
            query_parts.append("-site:linkedin.com -site:facebook.com -site:twitter.com -site:glassdoor.com -site:indeed.com")
            
            search_query = " ".join(query_parts)
        
        logger.info(f"Google Search (FREE): {search_query}")
        
        try:
            # Step 1: Google Search (FREE)
            search_results = self.google_search.search(search_query, num_results=10)
            
            if not search_results:
                return ProspectDiscoveryResponse(
                    success=True,
                    discovery_id=discovery_id,
                    source="google_search",
                    total_found=0,
                    prospects=[],
                    search_query_used=search_query,
                )
            
            # Step 2: Scrape top URLs with Firecrawl
            all_prospects = []
            urls_scraped = []
            
            # Filter out URLs that can't be scraped
            scrapeable_results = [r for r in search_results 
                                  if not any(domain in r.link.lower() for domain in BLOCKED_DOMAINS)]
            
            logger.info(f"Filtered {len(search_results)} results to {len(scrapeable_results)} scrapeable URLs")
            
            for result in scrapeable_results[:5]:  # Limit to 5 URLs
                try:
                    logger.info(f"Scraping: {result.link}")
                    
                    # Try Firecrawl first, fallback to free scraping
                    combined_content = None
                    try:
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
                        
                        # =============================================================
                        # MULTI-PAGE SCRAPING: Also scrape /contact, /about, /team pages
                        # =============================================================
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(result.link)
                            base_url = f"{parsed.scheme}://{parsed.netloc}"
                            
                            contact_paths = ['/contact', '/contact-us', '/about', '/about-us', '/team', '/staff', '/our-team']
                            for path in contact_paths[:3]:  # Limit to 3 extra pages
                                try:
                                    contact_url = f"{base_url}{path}"
                                    # Use free scrape for contact pages
                                    contact_content = self._free_scrape(contact_url)
                                    if contact_content:
                                        combined_content += f"\n\n--- FROM {path} ---\n" + contact_content
                                        logger.info(f"Also scraped {contact_url}")
                                except Exception as e:
                                    pass  # Contact page doesn't exist, that's fine
                        except Exception as e:
                            logger.warning(f"Multi-page scraping failed: {e}")
                        
                        prospects = self.extract_prospects_from_content(
                            content=combined_content,
                            url=result.link,
                            source=ProspectSource.GENERAL_SEARCH
                        )
                        
                        # Add search result context AND extract from snippet
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
                                if snippet_emails and not p.contact.email:
                                    p.contact.email = snippet_emails[0]
                        
                        all_prospects.extend(prospects)
                        
                except Exception as e:
                    logger.warning(f"Failed to scrape {result.link}: {e}")
                    continue
            
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

