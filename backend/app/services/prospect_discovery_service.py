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
from app.services.firestore_client import db

logger = logging.getLogger(__name__)


class ProspectDiscoveryService:
    """Service for discovering prospects from public directories"""
    
    def __init__(self):
        self.firecrawl = None
    
    def _init_clients(self):
        """Lazy init clients"""
        if self.firecrawl is None:
            self.firecrawl = get_firecrawl_client()
    
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
        
        # Title extraction
        title_patterns = [
            r'((?:Director|Head|Dean|Manager)\s+of\s+\w+(?:\s+\w+)?)',
            r'(Educational\s+Consultant)',
            r'(Admissions\s+Director)',
            r'(School\s+Psychologist)',
            r'(Licensed\s+\w+\s+Therapist)',
        ]
        
        titles = []
        for pattern in title_patterns:
            found = re.findall(pattern, content, re.IGNORECASE)
            titles.extend(found)
        
        # Organization extraction
        org_patterns = [
            r'(?:at|with|from)\s+([A-Z][A-Za-z\s]+(?:School|Academy|Center|Consulting|Associates))',
            r'([A-Z][A-Za-z\s]+(?:School|Academy|Center|Consulting|Associates))',
        ]
        
        orgs = []
        for pattern in org_patterns:
            found = re.findall(pattern, content)
            orgs.extend(found)
        
        # Location extraction
        location_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s+(CA|NY|TX|FL|MA|CT|NJ|PA|California|New York|Texas|Florida)'
        locations = re.findall(location_pattern, content)
        
        # Build prospects from extracted data
        # If we found names, create a prospect for each
        if names:
            for i, name in enumerate(list(set(names))[:5]):  # Limit to 5 per page
                prospect = DiscoveredProspect(
                    name=name.strip(),
                    title=titles[i] if i < len(titles) else None,
                    organization=orgs[i] if i < len(orgs) else None,
                    location=f"{locations[0][0]}, {locations[0][1]}" if locations else None,
                    source_url=url,
                    source=source,
                    contact=ProspectContact(
                        email=emails[i] if i < len(emails) else None,
                        phone=phones[i] if i < len(phones) else None,
                    ),
                    bio_snippet=content[:200] if content else None,
                )
                prospects.append(prospect)
        
        # If no names but we have emails, create prospects from emails
        elif emails:
            for email in list(set(emails))[:3]:
                # Try to extract name from email
                name_from_email = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
                
                prospect = DiscoveredProspect(
                    name=name_from_email,
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
                location_slug = request.location.lower().replace(" ", "-") if request.location else "california"
                specialty_slug = request.specialty.lower().replace(" ", "-") if request.specialty else "therapist"
                urls_to_scrape = [
                    f"https://www.psychologytoday.com/us/therapists/{location_slug}?spec={specialty_slug}",
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


# Singleton
_service: Optional[ProspectDiscoveryService] = None


def get_prospect_discovery_service() -> ProspectDiscoveryService:
    """Get or create service instance"""
    global _service
    if _service is None:
        _service = ProspectDiscoveryService()
    return _service

