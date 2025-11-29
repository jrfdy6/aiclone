"""
Generic/universal prospect extractor - fallback for all source types
"""
import re
import logging
from typing import List, Optional

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect, ProspectContact

from ..constants import CRED_PATTERN, GENERIC_EMAIL_PREFIXES, PROSPECT_CATEGORIES
from ..validators import is_valid_person_name
from ..organization_extractor import extract_organization
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class GenericExtractor(BaseExtractor):
    """
    Universal extraction using 3-layer approach:
    Layer 1: Expanded regex with all credentials
    Layer 2: Email-based name extraction
    Layer 3: LLM fallback (called separately if needed)
    """
    
    def extract(
        self,
        content: str,
        url: str,
        source: ProspectSource,
        category: Optional[str] = None
    ) -> List[DiscoveredProspect]:
        """Extract prospects from generic content"""
        prospects = []
        
        # Extract emails and phones using base class methods
        emails = self.extract_emails(content)
        phones = self.extract_phones(content)
        
        # Extract names with credentials
        names_with_info = []
        
        # Pattern 1: STRICT - "FirstName LastName, CREDENTIAL"
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
        
        # Detect profession - use category if provided
        detected_profession = None
        profession_reason = None
        
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
        
        # Build prospect objects - match contact info to names by proximity
        seen_names = set()
        used_emails = set()
        used_phones = set()
        
        for info in names_with_info:
            name = info["name"]
            
            # Skip duplicates
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            
            # Find name position in content
            name_pos = content.find(name)
            
            # Extract bio snippet around the name
            bio_snippet = None
            nearby_content = ""
            if name_pos >= 0:
                start = max(0, name_pos - 100)
                end = min(len(content), name_pos + len(name) + 500)
                nearby_content = content[start:end]
                bio_snippet = content[max(0, name_pos - 50):min(len(content), name_pos + len(name) + 200)].strip()
            
            # Find email near this name
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
            
            # Extract website URL from nearby content
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
            
            # Extract organization
            prospect_organization = extract_organization(content, url)
            
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
            
            # Add profession reason as metadata
            if profession_reason:
                prospect.bio_snippet = f"{profession_reason}. {prospect.bio_snippet or ''}"
            
            prospects.append(prospect)
            
            if len(prospects) >= 10:  # Limit per page
                break
        
        # FALLBACK: If no names but have contact info, use email-based name
        if not prospects and emails:
            for email in emails[:3]:
                name_from_email = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
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

