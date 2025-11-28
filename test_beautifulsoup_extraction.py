"""
Test BeautifulSoup-based extraction
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

def test_beautifulsoup_extraction():
    """Test BeautifulSoup extraction on team page"""
    url = "https://www.newportacademy.com/meet-the-team/"
    print(f"Testing: {url}\n")
    
    content = free_scrape(url)
    if not content:
        print("Failed to scrape")
        return
    
    soup = BeautifulSoup(content, 'html.parser')
    
    target_roles = [
        'admissions director', 'admissions manager', 'admissions coordinator',
        'clinical director', 'program director', 'intake coordinator',
        'intake manager', 'family therapist', 'head of school',
        'executive director', 'clinical manager', 'admissions team',
        'vice president', 'president', 'chief', 'officer'
    ]
    
    names_with_titles = []
    
    # Method 1: Look for h2/h3/h4 with entry-title or similar classes
    print("=" * 60)
    print("METHOD 1: entry-title headings")
    print("=" * 60)
    
    name_headings = soup.find_all(['h2', 'h3', 'h4'], class_=re.compile(r'entry-title|name|staff-name|team-member-name', re.I))
    print(f"Found {len(name_headings)} headings with name classes")
    
    for heading in name_headings[:10]:
        text = heading.get_text(strip=True)
        name_part = text.split(',')[0].strip()
        if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}$', name_part):
            print(f"\n  Name: {name_part}")
            
            # Look for role
            role_found = None
            next_elem = heading.find_next_sibling()
            if next_elem:
                next_text = next_elem.get_text(strip=True).lower()
                for role in target_roles:
                    if role in next_text:
                        role_found = role.title()
                        print(f"    Role (next sibling): {role_found}")
                        break
            
            if not role_found:
                parent = heading.find_parent(['div', 'section', 'article'])
                if parent:
                    parent_text = parent.get_text(strip=True).lower()
                    for role in target_roles:
                        if role in parent_text:
                            role_found = role.title()
                            print(f"    Role (parent): {role_found}")
                            break
            
            if role_found:
                names_with_titles.append({"name": name_part, "title": role_found})
    
    # Method 2: Look for position/role fields
    print("\n" + "=" * 60)
    print("METHOD 2: position/role fields")
    print("=" * 60)
    
    position_fields = soup.find_all(['p', 'div', 'span'], class_=re.compile(r'position|role|title|team_member_position', re.I))
    print(f"Found {len(position_fields)} position/role fields")
    
    for field in position_fields[:10]:
        position_text = field.get_text(strip=True)
        print(f"\n  Position text: {position_text[:80]}")
        
        # Check if matches target roles
        matched_role = None
        position_lower = position_text.lower()
        for role in target_roles:
            if role in position_lower:
                # Use full position text
                matched_role = position_text[:100].strip()
                break
        
        if matched_role:
            # Use full position text
            matched_role = position_text[:100].strip()
            print(f"    Matched role (full): {matched_role}")
            
            # Find name nearby
            prev_elem = field.find_previous(['h2', 'h3', 'h4', 'h5'])
            if not prev_elem:
                parent = field.find_parent(['div', 'section', 'article'])
                if parent:
                    prev_elem = parent.find(['h2', 'h3', 'h4', 'h5'])
            
            if prev_elem:
                name_text = prev_elem.get_text(strip=True)
                name_part = name_text.split(',')[0].strip()
                if re.match(r'^[A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}$', name_part):
                    print(f"    Found name: {name_part}")
                    names_with_titles.append({"name": name_part, "title": matched_role})
    
    # Dedupe
    seen = set()
    final_prospects = []
    for item in names_with_titles:
        name = item["name"]
        if name not in seen:
            seen.add(name)
            final_prospects.append(item)
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Found {len(final_prospects)} unique prospects:\n")
    
    for i, prospect in enumerate(final_prospects[:10], 1):
        print(f"{i}. {prospect['name']} - {prospect.get('title', 'N/A')}")

if __name__ == "__main__":
    test_beautifulsoup_extraction()

