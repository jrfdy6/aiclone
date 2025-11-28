"""
Debug treatment center extraction - inspect actual HTML structure
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

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

def inspect_treatment_center_structure():
    """Inspect actual HTML structure of treatment center pages"""
    print("=" * 60)
    print("INSPECTING TREATMENT CENTER HTML STRUCTURE")
    print("=" * 60)
    
    # Try a few treatment center URLs
    test_urls = [
        "https://www.newportacademy.com/",
        "https://www.evoketherapy.com/",
    ]
    
    for url in test_urls:
        print(f"\n📁 Inspecting: {url}")
        content = free_scrape(url)
        
        if not content:
            continue
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Look for staff/team/leadership sections
        print(f"\n   🔍 Looking for staff/team sections...")
        
        # Check for common staff page indicators
        staff_indicators = ['team', 'staff', 'leadership', 'admissions', 'about']
        for indicator in staff_indicators:
            links = soup.find_all('a', href=re.compile(indicator, re.I))
            if links:
                print(f"      Found {len(links)} links with '{indicator}'")
                for link in links[:3]:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)[:50]
                    print(f"         - {href} ({text})")
        
        # Look for names in the content
        print(f"\n   👥 Looking for names in HTML...")
        
        # Check h2, h3 tags
        headings = soup.find_all(['h2', 'h3'])
        name_candidates = []
        for h in headings[:10]:
            text = h.get_text(strip=True)
            # Check if it looks like a name
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', text) and len(text.split()) == 2:
                name_candidates.append(text)
                # Check what's near it
                next_sibling = h.find_next_sibling()
                if next_sibling:
                    next_text = next_sibling.get_text(strip=True)[:100]
                    print(f"      Found: {text}")
                    print(f"         Next: {next_text}")
        
        if name_candidates:
            print(f"   ✅ Found {len(name_candidates)} potential names: {name_candidates[:5]}")
        else:
            print(f"   ⚠️  No names found in headings")
        
        # Look for role keywords
        print(f"\n   🎯 Looking for role keywords...")
        target_roles = ['admissions director', 'clinical director', 'intake coordinator']
        for role in target_roles:
            if role in content.lower():
                print(f"      ✅ Found '{role}' in content")
                # Find context around it
                matches = list(re.finditer(role, content, re.I))
                if matches:
                    match = matches[0]
                    context = content[max(0, match.start()-100):match.end()+100]
                    print(f"         Context: {context[:150]}...")
        
        # Look for email patterns
        print(f"\n   📧 Looking for emails...")
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.gif')) and '@' in e]
        if valid_emails:
            print(f"      ✅ Found {len(set(valid_emails))} unique emails: {list(set(valid_emails))[:5]}")
        else:
            print(f"      ⚠️  No emails found")
        
        # Look for phone patterns
        print(f"\n   📞 Looking for phones...")
        phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', content)
        if phones:
            print(f"      ✅ Found {len(set(phones))} unique phones: {list(set(phones))[:5]}")
        else:
            print(f"      ⚠️  No phones found")
        
        # Only test first URL for now
        break

if __name__ == "__main__":
    inspect_treatment_center_structure()

