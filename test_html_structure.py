"""
Inspect HTML structure to find where names actually are
"""
import re
import requests
from bs4 import BeautifulSoup

def free_scrape(url: str) -> str:
    """Scrape a URL for free"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error: {e}")
        return ""

def inspect_html():
    """Inspect HTML to find name structures"""
    url = "https://www.newportacademy.com/meet-the-team/"
    print(f"Inspecting: {url}\n")
    
    content = free_scrape(url)
    if not content:
        print("Failed to scrape")
        return
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Look for all text that matches name pattern
    all_text = soup.get_text()
    
    # Find all potential names
    name_pattern = r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
    all_matches = re.findall(name_pattern, all_text)
    
    # Filter to likely real names
    likely_names = []
    bad_phrases = ['Newport Academy', 'Washington DC', 'Los Angeles', 'Get Started',
                   'Contact Us', 'Learn More', 'Read More', 'View All', 'See All',
                   'Sign Up', 'Log In', 'Insurance Cover', 'Residential Services',
                   'Learning and', 'Mental Health', 'Substance Use', 'Young Adults']
    
    for name in all_matches:
        if not any(bad in name for bad in bad_phrases):
            words = name.split()
            if len(words) == 2 and all(2 <= len(w) <= 12 for w in words):
                likely_names.append(name)
    
    print(f"Found {len(set(likely_names))} unique likely names:")
    for name in list(set(likely_names))[:20]:
        # Find where this name appears in HTML
        name_pos = content.find(name)
        if name_pos != -1:
            # Get surrounding HTML
            context_start = max(0, name_pos - 200)
            context_end = min(len(content), name_pos + 200)
            context = content[context_start:context_end]
            
            # Look for role keywords nearby
            roles_found = []
            for role in ['director', 'president', 'manager', 'coordinator', 'therapist', 'admissions', 'clinical']:
                if role in context.lower():
                    roles_found.append(role)
            
            print(f"\n  {name}")
            if roles_found:
                print(f"    Roles nearby: {', '.join(roles_found)}")
            print(f"    HTML context: {context[:150]}...")

if __name__ == "__main__":
    inspect_html()

