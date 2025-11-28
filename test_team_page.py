"""
Test scraping the actual team page
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
        print(f"   ❌ Error: {e}")
        return ""

def test_team_page():
    """Test scraping team page"""
    url = "https://www.newportacademy.com/meet-the-team/"
    print(f"Scraping: {url}\n")
    
    content = free_scrape(url)
    if not content:
        print("Failed to scrape")
        return
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Look for names in various structures
    print("=" * 60)
    print("LOOKING FOR NAMES")
    print("=" * 60)
    
    # Method 1: Look in all text for name patterns
    text = soup.get_text()
    
    # Find all potential names (2 capitalized words)
    name_pattern = r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
    potential_names = re.findall(name_pattern, text)
    
    # Filter out common false positives
    bad_words = ['Newport Academy', 'Washington DC', 'Los Angeles', 'San Francisco', 
                 'New York', 'United States', 'Contact Us', 'Get Started', 'Learn More',
                 'Read More', 'View All', 'See All', 'Click Here', 'Sign Up', 'Log In']
    
    filtered_names = []
    for name in potential_names:
        if not any(bad in name for bad in bad_words):
            if len(name.split()) == 2:
                filtered_names.append(name)
    
    print(f"\nFound {len(set(filtered_names))} unique potential names:")
    for name in list(set(filtered_names))[:20]:
        print(f"  - {name}")
    
    # Method 2: Look for specific HTML structures
    print("\n" + "=" * 60)
    print("LOOKING IN HTML STRUCTURES")
    print("=" * 60)
    
    # Check divs with class containing "name", "staff", "team", "member"
    staff_divs = soup.find_all(['div', 'section'], class_=re.compile(r'name|staff|team|member|person', re.I))
    print(f"\nFound {len(staff_divs)} divs with staff-related classes")
    
    for div in staff_divs[:5]:
        text = div.get_text(strip=True)
        if len(text) < 200:  # Not too long
            print(f"\n  Div text: {text[:150]}")
    
    # Check for role keywords near names
    print("\n" + "=" * 60)
    print("LOOKING FOR ROLES")
    print("=" * 60)
    
    roles = ['admissions', 'director', 'clinical', 'intake', 'coordinator', 'manager', 'therapist']
    for role in roles:
        if role in text.lower():
            print(f"  ✅ Found '{role}'")
            # Find context
            matches = list(re.finditer(role, text, re.I))
            if matches:
                match = matches[0]
                context = text[max(0, match.start()-50):match.end()+50]
                print(f"     Context: {context}")

if __name__ == "__main__":
    test_team_page()

