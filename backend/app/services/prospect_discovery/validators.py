"""
Validation functions for prospect discovery
"""
import re
import logging
from typing import TYPE_CHECKING, List, Optional

from .constants import DC_NEIGHBORHOODS, CRED_PATTERN, GENERIC_EMAIL_PREFIXES

if TYPE_CHECKING:
    from app.models.prospect_discovery import DiscoveredProspect

logger = logging.getLogger(__name__)

def is_valid_person_name(name: str) -> bool:
    """
    Check if name looks like a real person name. Used during extraction to filter garbage names.
    """
    name_lower = name.lower()
    words = name.split()
    
    # Must be exactly 2-3 words
    if len(words) < 2 or len(words) > 3:
        return False
    
    # Bad name words
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


def is_valid_prospect_for_saving(prospect: 'DiscoveredProspect') -> bool:
    """
    Final validation check before saving prospect to database.
    More strict than extraction-time validation.
    """
    if not prospect.name or not prospect.name.strip():
        return False
    
    name = prospect.name.strip()
    name_lower = name.lower()
    words = name.split()
    
    # Must be 2-3 words (proper person names)
    if len(words) < 2 or len(words) > 3:
        logger.info(f"Filtering out invalid prospect (word count: {len(words)} words): {name}")
        return False
    
    # IMPORTANT: Check if name is a DC neighborhood - if so, allow it (but still check other validations)
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
    ]
    # Only add location words to bad_words if it's NOT a DC neighborhood
    if not is_dc_neighborhood:
        bad_words.extend(['capitol', 'heights'])
    
    if any(w.lower() in bad_words for w in words):
        logger.info(f"Filtering out invalid prospect (bad words in name): {name}")
        return False
    
    # Filter location-only names (but allow DC neighborhoods)
    location_phrases = ['areas cities', 'north bethesda', 'south bethesda', 'east bethesda',
                      'west bethesda', 'montgomery county', 'fairfax county', 'north arlington',
                      'south arlington', 'silver spring', 'chevy chase']
    name_lower_phrase = name_lower.replace(' ', ' ')
    if not is_dc_neighborhood and (name_lower_phrase in location_phrases or name_lower_phrase.startswith('areas ') or name_lower_phrase.startswith('cities ')):
        logger.info(f"Filtering out invalid prospect (location phrase): {name}")
        return False
    
    # Filter if name starts with location direction words (likely location phrases)
    if not is_dc_neighborhood:
        location_directions = ['north', 'south', 'east', 'west', 'areas', 'cities']
        if words[0].lower() in location_directions and len(words) == 2:
            common_location_second_words = ['bethesda', 'arlington', 'fairfax', 'alexandria', 
                                           'georgetown', 'potomac', 'montgomery', 'cleveland',
                                           'heights', 'park', 'springs', 'county']
            if words[1].lower() in common_location_second_words:
                logger.info(f"Filtering out invalid prospect (location phrase): {name}")
                return False
    
    # Filter role words at end of name (e.g., "John Counselor", "Jane Director")
    role_words = ['counselor', 'director', 'therapist', 'psychologist', 'psychiatrist', 'coach',
                 'specialist', 'consultant', 'advisor', 'manager', 'worker', 'officer', 'athletic']
    if words[-1].lower() in role_words:
        logger.info(f"Filtering out invalid prospect (role word at end): {name}")
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
    if prospect.organization:
        org_lower = prospect.organization.lower().strip()
        template_phrases = ['powered by', 'built with', 'designed by', 'is powered by',
                           'in the united states', 'where children come first',
                           'in united states', 'the united states', 'in the us']
        if any(phrase in org_lower for phrase in template_phrases):
            logger.info(f"Filtering out invalid prospect (template organization): {name} | {prospect.organization}")
            return False
        if org_lower in ['where children come first', 'in the united states', 'in united states', 
                        'the united states', 'in the us']:
            logger.info(f"Filtering out invalid prospect (template organization name): {name} | {prospect.organization}")
            return False
        # Filter out directory/aggregator sites (not actual organizations)
        directory_sites = ['psychologytoday', 'psychology today', 'healthgrades', 'webmd', 
                         'zocdoc', 'vitals', 'ratemds', 'doctor.com', 'pmc', 'ncbi',
                         'callsource', 'indeed', 'glassdoor', 'linkedin']
        if org_lower in directory_sites or any(ds in org_lower for ds in directory_sites):
            # Directory sites are not organizations - set to None
            prospect.organization = None
            logger.debug(f"Filtering out directory site as organization: {org_lower} for {name}")
    
    return True


# Helper functions for extractors

def find_name_in_text(text: str) -> Optional[str]:
    """Find a person name in text using validation"""
    # Try credential patterns first
    pattern = rf'\b([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}}),?\s*({CRED_PATTERN})\b'
    matches = re.findall(pattern, text)
    for match in matches:
        name = match[0].strip()
        if is_valid_person_name(name):
            return name
    
    # Try Dr. prefix
    pattern = r'\b(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
    matches = re.findall(pattern, text)
    for match in matches:
        name = match.strip()
        if is_valid_person_name(name):
            return name
    
    return None


def find_names_in_document(text: str, limit: int = 10) -> List[str]:
    """Find multiple person names in document text"""
    names = []
    
    # Pattern 1: Name with credentials
    pattern = rf'\b([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}}),?\s*({CRED_PATTERN})\b'
    for match in re.findall(pattern, text):
        name = match[0].strip()
        if is_valid_person_name(name) and name not in names:
            names.append(name)
            if len(names) >= limit:
                break
    
    # Pattern 2: Dr. prefix
    if len(names) < limit:
        pattern = r'\b(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
        for match in re.findall(pattern, text):
            name = match.strip()
            if is_valid_person_name(name) and name not in names:
                names.append(name)
                if len(names) >= limit:
                    break
    
    return names


def normalize_phone(phone_str: str) -> Optional[str]:
    """Normalize phone number to (XXX) XXX-XXXX format"""
    digits = re.sub(r'[^\d]', '', phone_str)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone_str if phone_str else None


def find_phone_in_text(text: str) -> Optional[str]:
    """Find and normalize first phone number in text"""
    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phones:
        return normalize_phone(phones[0])
    return None


def find_emails_in_text(text: str) -> List[str]:
    """Find emails in text, including obfuscated ones"""
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    
    # Obfuscated patterns
    patterns = [
        r'([a-zA-Z0-9._%+-]+)\s*\[at\]\s*([a-zA-Z0-9.-]+)\s*\[dot\]\s*([a-zA-Z]{2,})',
        r'([a-zA-Z0-9._%+-]+)\s*\(at\)\s*([a-zA-Z0-9.-]+)\s*\(dot\)\s*([a-zA-Z]{2,})',
        r'([a-zA-Z0-9._%+-]+)\s+AT\s+([a-zA-Z0-9.-]+)\s+DOT\s+([a-zA-Z]{2,})',
    ]
    
    for pattern in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            emails.append(f"{match[0]}@{match[1]}.{match[2]}")
    
    # Filter invalid emails
    emails = [e for e in emails 
              if not e.endswith(('.png', '.jpg', '.gif'))
              and '@sentry' not in e.lower()
              and not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
    
    return list(set(emails))  # Dedupe

