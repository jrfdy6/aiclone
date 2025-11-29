"""
Web scraping utilities
"""
import re
import json
import logging
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def free_scrape(url: str) -> Optional[str]:
    """
    Free scraping fallback using requests + BeautifulSoup.
    Mimics a real browser to avoid bot detection.
    """
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


# Helper functions for extractors

def absolute_url(base_url: str, href: str) -> str:
    """Convert relative URL to absolute URL"""
    if href.startswith('http'):
        return href
    return urljoin(base_url, href)


def extract_next_data_profile_urls(html: str, base_url: str) -> List[str]:
    """Extract profile URLs from Next.js __NEXT_DATA__ JSON"""
    profile_urls = []
    
    try:
        # Find __NEXT_DATA__ script tag
        json_match = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE
        )
        
        if not json_match:
            return []
        
        json_str = json_match.group(1).strip()
        data = json.loads(json_str)
        
        # Recursively find profile URLs
        def find_urls(obj, path=""):
            urls = []
            if isinstance(obj, dict):
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
                
                if 'searchResults' in obj and isinstance(obj['searchResults'], list):
                    for item in obj['searchResults']:
                        urls.extend(find_urls(item))
                
                if len(path.split('.')) < 10:  # Limit recursion
                    for key, value in obj.items():
                        if key not in ['profileUrl', 'profile_url']:
                            urls.extend(find_urls(value, path + f".{key}"))
            elif isinstance(obj, list):
                for item in obj:
                    urls.extend(find_urls(item))
            return urls
        
        profile_urls = find_urls(data)
        
        # Try direct path access
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
        
        return list(set(profile_urls))
    except Exception as e:
        logger.warning(f"Error extracting profile URLs from JSON: {e}")
        return []


def find_likely_team_pages(soup: BeautifulSoup, base_url: str, extra_keywords: Optional[List[str]] = None) -> List[str]:
    """Find links to team/staff pages"""
    keywords = ["team", "staff", "leadership", "coaches", "coaching", "meet", "about"]
    if extra_keywords:
        keywords.extend(extra_keywords)
    
    links = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').lower()
        text = a.get_text(strip=True).lower()
        for kw in keywords:
            if kw in href or kw in text:
                full_url = absolute_url(base_url, a.get('href'))
                if full_url not in links:
                    links.append(full_url)
    return links[:10]  # Limit to 10


def find_contact_pages(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Find links to contact pages"""
    links = []
    keywords = ["contact", "reach", "connect"]
    
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').lower()
        text = a.get_text(strip=True).lower()
        for kw in keywords:
            if kw in href or kw in text:
                full_url = absolute_url(base_url, a.get('href'))
                if full_url not in links:
                    links.append(full_url)
    return links[:5]  # Limit to 5


def domain_to_org(url: str) -> Optional[str]:
    """Extract organization name from domain"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        parts = domain.split('.')
        if len(parts) >= 2:
            main_part = parts[0]
            if main_part not in ['site', 'www', 'home', 'main']:
                return main_part.replace('-', ' ').title()
    except:
        pass
    return None


def extract_role_from_element(element, role_keywords: List[str]) -> Optional[str]:
    """Extract role/title from HTML element text"""
    if hasattr(element, 'get_text'):
        text = element.get_text(" ", strip=True).lower()
        for role in role_keywords:
            if role.lower() in text:
                # Try to find the full role phrase
                words = text.split()
                for i in range(len(words) - len(role.split()) + 1):
                    phrase = " ".join(words[i:i+len(role.split())])
                    if phrase == role.lower():
                        return role.title()
                return role.title()
    return None


def extract_role_from_text(text: str, role_keywords: List[str]) -> Optional[str]:
    """Extract role/title from text"""
    text_lower = text.lower()
    for role in role_keywords:
        if role.lower() in text_lower:
            return role.title()
    return None


def find_text_block_near(soup: BeautifulSoup, search_text: str, window: int = 500) -> str:
    """Find text block near a search string"""
    full_text = soup.get_text(" ", strip=True)
    pos = full_text.find(search_text)
    if pos >= 0:
        start = max(0, pos - window)
        end = min(len(full_text), pos + len(search_text) + window)
        return full_text[start:end]
    return ""

