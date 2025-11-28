"""
Test treatment center extraction patterns on real scraped content
"""
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

GENERIC_EMAIL_PREFIXES = ['info', 'contact', 'support', 'hello', 'admin', 'sales', 
                          'help', 'office', 'mail', 'enquiries', 'inquiries', 'noreply',
                          'webmaster', 'newsletter', 'team', 'careers', 'jobs']

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

def test_extraction_patterns():
    """Test extraction patterns on real content"""
    print("=" * 60)
    print("TESTING TREATMENT CENTER EXTRACTION PATTERNS")
    print("=" * 60)
    
    # Scrape main page and team page
    base_url = "https://www.newportacademy.com"
    main_content = free_scrape(base_url)
    team_content = free_scrape(f"{base_url}/meet-the-team/")
    
    combined_content = main_content
    if team_content:
        combined_content += f"\n\n--- FROM /meet-the-team/ ---\n" + team_content
    
    print(f"\n📄 Total content: {len(combined_content)} chars")
    
    # Target roles
    target_roles = [
        'admissions director', 'admissions manager', 'admissions coordinator',
        'clinical director', 'program director', 'intake coordinator',
        'intake manager', 'family therapist', 'head of school',
        'executive director', 'clinical manager', 'admissions team',
        'vice president'
    ]
    
    names_with_titles = []
    
    # Pattern 1: "John Smith, Admissions Director"
    pattern1 = r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}),?\s+(Admissions Director|Clinical Director|Program Director|Intake Coordinator|Intake Manager|Family Therapist|Head of School|Executive Director|Admissions Manager|Clinical Manager)\b'
    matches1 = re.findall(pattern1, combined_content, re.IGNORECASE)
    print(f"\n✅ Pattern 1 (name, title): {len(matches1)} matches")
    for match in matches1[:3]:
        print(f"   - {match[0]}, {match[1]}")
        if len(match[0].split()) == 2:
            names_with_titles.append({"name": match[0], "title": match[1]})
    
    # Pattern 2: "Admissions Director: Jane Doe"
    pattern2 = r'\b(Admissions Director|Clinical Director|Program Director|Intake Coordinator|Intake Manager|Family Therapist|Head of School|Executive Director|Admissions Manager|Clinical Manager)[:\s]+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b'
    matches2 = re.findall(pattern2, combined_content, re.IGNORECASE)
    print(f"\n✅ Pattern 2 (title: name): {len(matches2)} matches")
    for match in matches2[:3]:
        print(f"   - {match[1]} ({match[0]})")
        if len(match[1].split()) == 2:
            names_with_titles.append({"name": match[1], "title": match[0]})
    
    # Pattern 3: Name directly followed by title (no space) - "Blake KinseyVice President"
    pattern3 = r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})(Vice President|President|Director|Manager|Coordinator|Therapist|Head of School)'
    matches3 = re.findall(pattern3, combined_content)
    print(f"\n✅ Pattern 3 (nameTitle): {len(matches3)} matches")
    for match in matches3[:5]:
        print(f"   - {match[0]}{match[1]}")
        if len(match[0].split()) == 2:
            names_with_titles.append({"name": match[0], "title": match[1]})
    
    # Pattern 4: Role keywords followed by names
    for role in ['vice president', 'admissions', 'clinical director']:
        role_pattern = rf'\b{role}\b[^<]*?([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}})'
        matches = re.findall(role_pattern, combined_content, re.IGNORECASE)
        if matches:
            print(f"\n✅ Pattern 4 ({role}): {len(matches)} matches")
            for name in matches[:3]:
                print(f"   - {name}")
                if len(name.split()) == 2:
                    names_with_titles.append({"name": name, "title": role.title()})
    
    # Pattern 5: Extract from text blocks
    text_blocks = re.split(r'[\.\n]', combined_content)
    found_in_blocks = 0
    for block in text_blocks[:100]:  # Check first 100 blocks
        name_match = re.search(r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b', block)
        if name_match:
            name = name_match.group(1)
            for role in target_roles:
                if role in block.lower() and len(name.split()) == 2:
                    words = name.split()
                    if all(2 <= len(w) <= 12 for w in words):
                        names_with_titles.append({"name": name, "title": role.title()})
                        found_in_blocks += 1
                        break
    if found_in_blocks > 0:
        print(f"\n✅ Pattern 5 (text blocks): {found_in_blocks} matches")
    
    # Dedupe and validate
    seen_names = set()
    bad_name_words = ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 
                     'programs', 'therapy', 'center', 'treatment', 'rehab',
                     'founder and', 'apy programs', 'ock facebook', 'help for',
                     'struggling', 'evoke', 'newport', 'academy', 'washington',
                     'los angeles', 'san francisco', 'new york']
    
    valid_prospects = []
    for item in names_with_titles:
        name = item["name"].strip()
        
        if name in seen_names or len(name) < 5:
            continue
        
        words = name.split()
        if len(words) != 2:
            continue
        
        if not all(2 <= len(w) <= 12 for w in words):
            continue
        
        name_lower = name.lower()
        if any(bad in name_lower for bad in bad_name_words):
            continue
        
        if '&' in name or '»' in name or '<' in name or '>' in name:
            continue
        
        if not name[0].isupper():
            continue
        
        seen_names.add(name)
        valid_prospects.append(item)
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"   Total unique prospects: {len(valid_prospects)}")
    
    for i, prospect in enumerate(valid_prospects[:10], 1):
        print(f"\n   {i}. {prospect['name']}")
        print(f"      Title: {prospect.get('title', 'N/A')}")
        
        # Try to find email/phone near name
        name_pos = combined_content.lower().find(prospect['name'].lower())
        if name_pos != -1:
            nearby = combined_content[max(0, name_pos-250):name_pos+250]
            
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', nearby)
            valid_emails = [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
            if valid_emails:
                print(f"      Email: {valid_emails[0]}")
            
            phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby)
            if phones:
                digits = re.sub(r'[^\d]', '', phones[0])
                if len(digits) == 10:
                    area_code = int(digits[:3])
                    exchange = int(digits[3:6])
                    if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                        print(f"      Phone: ({digits[:3]}) {digits[3:6]}-{digits[6:]}")

if __name__ == "__main__":
    test_extraction_patterns()

