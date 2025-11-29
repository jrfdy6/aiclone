"""
Organization extraction from web content
"""
import re
from typing import Optional
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


def is_valid_organization(org: str) -> bool:
    """Check if organization name looks valid (not template/footer text)"""
    org_lower = org.lower().strip()
    
    # Template/footer phrases to filter out (NOT organization names)
    template_phrases = [
        'powered by', 'built with', 'designed by', 'created by',
        'all rights reserved', 'copyright', 'privacy policy',
        'terms of service', 'cookie policy', 'sitemap',
        'is powered by', 'is built with', 'is designed by',
        'where children come first', 'in the united states',
        'in united states', 'the united states', 'in the us',
        'may also be known', 'are also known as', 'and hospital',
        'pediatricians may', 'psychologists may', 'may also be'
    ]
    
    # Filter template phrases
    if any(phrase in org_lower for phrase in template_phrases):
        return False
    
    # Filter out sentences/phrases that are too long (not organization names)
    words = org.split()
    if len(words) > 10:  # Organization names should be 2-10 words max
        return False
    
    # Filter sentences (contains sentence patterns) - check this BEFORE word count
    sentence_patterns = [
        'may also be', 'are also known', 'can also', 'will also',
        'is also', 'and hospital', 'pediatricians may', 'psychologists may',
        'may also be known', 'are also known as', 'by the following', 'the following'
    ]
    if any(pattern in org_lower for pattern in sentence_patterns):
        return False
    
    # Filter organizations with too many words (likely sentences)
    if len(words) > 6:  # Lowered from 10 - 7+ words is suspicious for an org name
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


def extract_organization(content: str, url: str) -> Optional[str]:
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


# Helper functions for extractors using BeautifulSoup

def extract_from_html(soup: BeautifulSoup, url: Optional[str] = None) -> Optional[str]:
    """
    Extract organization from BeautifulSoup HTML object.
    Wrapper around extract_organization().
    """
    if soup is None:
        return None
    
    html_content = str(soup)
    return extract_organization(html_content, url or "")


def extract_from_profile(soup: BeautifulSoup, url: Optional[str] = None) -> Optional[str]:
    """
    Extract organization from profile page (same as extract_from_html for now).
    Can be extended with profile-specific logic.
    """
    return extract_from_html(soup, url)

