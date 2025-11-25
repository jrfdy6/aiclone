"""
Prospect Discovery Service

Finds actual prospects (people/organizations) from public directories.
Extracts structured data: name, title, organization, contact info.
"""

import logging
import time
import re
from typing import List, Dict, Any, Optional

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
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


class ProspectDiscoveryService:
    """Service for discovering prospects from public directories"""
    
    def __init__(self):
        self.firecrawl = None
        self.perplexity = None
    
    def _init_clients(self):
        """Lazy init clients"""
        if self.firecrawl is None:
            self.firecrawl = get_firecrawl_client()
        if self.perplexity is None:
            try:
                self.perplexity = get_perplexity_client()
            except:
                self.perplexity = None
    
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
        """Generic extraction for non-Psychology Today sources"""
        prospects = []
        
        # Email extraction
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        emails = [e for e in emails if not e.endswith('.png') and not e.endswith('.jpg')]
        
        # Phone extraction
        phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content)
        
        # Name extraction patterns
        name_patterns = [
            r'(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:PhD|PsyD|LCSW|LMFT|MEd|MA|MS)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:Director|Consultant|Therapist|Counselor)',
        ]
        
        names = []
        for pattern in name_patterns:
            found = re.findall(pattern, content)
            names.extend(found)
        
        # Build prospects
        if names:
            for i, name in enumerate(list(set(names))[:5]):
                prospect = DiscoveredProspect(
                    name=name.strip(),
                    source_url=url,
                    source=source,
                    contact=ProspectContact(
                        email=emails[i] if i < len(emails) else None,
                        phone=phones[i] if i < len(phones) else None,
                    ),
                    bio_snippet=content[:200] if content else None,
                )
                prospects.append(prospect)
        elif emails:
            for email in list(set(emails))[:3]:
                name_from_email = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                prospect = DiscoveredProspect(
                    name=name_from_email,
                    source_url=url,
                    source=source,
                    contact=ProspectContact(email=email),
                )
                prospects.append(prospect)
        
        return prospects
    
    def calculate_fit_score(
        self,
        prospect: DiscoveredProspect,
        target_specialty: Optional[str] = None,
        target_location: Optional[str] = None
    ) -> int:
        """Calculate fit score for a prospect (0-100)"""
        score = 50  # Base score
        
        # Has email: +20
        if prospect.contact.email:
            score += 20
        
        # Has phone: +10
        if prospect.contact.phone:
            score += 10
        
        # Has title: +10
        if prospect.title:
            score += 10
        
        # Has organization: +5
        if prospect.organization:
            score += 5
        
        # Location match: +10
        if target_location and prospect.location:
            if target_location.lower() in prospect.location.lower():
                score += 10
        
        # Specialty match in bio: +15
        if target_specialty and prospect.bio_snippet:
            if target_specialty.lower() in prospect.bio_snippet.lower():
                score += 15
        
        return min(score, 100)
    
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
        """Save discovered prospects to the main prospects collection"""
        for prospect in prospects:
            prospect_doc = {
                "name": prospect.name,
                "title": prospect.title,
                "company": prospect.organization,
                "email": prospect.contact.email,
                "phone": prospect.contact.phone,
                "location": prospect.location,
                "source": f"discovery:{prospect.source.value}",
                "source_url": prospect.source_url,
                "fit_score": prospect.fit_score,
                "status": "new",
                "created_at": time.time(),
            }
            
            # Use email as document ID if available, otherwise generate one
            doc_id = prospect.contact.email or f"prospect_{int(time.time() * 1000)}"
            doc_id = doc_id.replace("@", "_at_").replace(".", "_")
            
            doc_ref = db.collection("users").document(user_id).collection("prospects").document(doc_id)
            doc_ref.set(prospect_doc, merge=True)
        
        logger.info(f"Saved {len(prospects)} prospects to collection")
    
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
    
    async def find_prospects_with_ai(
        self,
        user_id: str,
        specialty: str,
        location: str,
        additional_context: Optional[str] = None,
        max_results: int = 10
    ) -> ProspectDiscoveryResponse:
        """
        Use Perplexity AI to find real prospects.
        This asks Perplexity to search and return actual people/organizations.
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
        prompt = f"""Find {max_results} real {specialty}s in {location}.

For each person, provide:
- Full name
- Title/credentials
- Organization/practice name
- Specialties
- Contact info (website, phone if public)
- Brief description

{f'Additional context: {additional_context}' if additional_context else ''}

Focus on finding actual practitioners, not articles about the profession.
Return real, verifiable professionals with their actual contact information."""

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

