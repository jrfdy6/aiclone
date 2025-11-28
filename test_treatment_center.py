"""
Test treatment center extraction (RTC + PHP/IOP)
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

def test_treatment_center_extraction():
    """Test treatment center extraction"""
    print("=" * 60)
    print("TESTING TREATMENT CENTER EXTRACTION")
    print("=" * 60)
    
    # Test with treatment centers that have staff pages
    test_urls = [
        "https://www.newportacademy.com/",  # Newport Academy
        "https://www.aspeneducationgroup.com/",  # Aspen Education Group
    ]
    
    for main_url in test_urls:
        print(f"\n📁 Testing: {main_url}")
        
        # Step 1: Scrape main page
        main_content = free_scrape(main_url)
        if not main_content:
            print("   ❌ Failed to scrape main page")
            continue
        
        print(f"   ✅ Scraped {len(main_content)} chars from main page")
        
        # Step 2: Try to scrape additional pages
        parsed = urlparse(main_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        target_pages = ['/team', '/staff', '/leadership', '/admissions', '/about']
        combined_content = main_content
        
        for path in target_pages[:3]:
            try:
                page_url = urljoin(base_url, path)
                page_content = free_scrape(page_url)
                if page_content:
                    combined_content += f"\n\n--- FROM {path} ---\n" + page_content
                    print(f"   ✅ Also scraped {path}")
            except:
                pass
        
        # Step 3: Extract names with roles
        target_roles = [
            'admissions director', 'admissions manager', 'admissions coordinator',
            'clinical director', 'program director', 'intake coordinator',
            'intake manager', 'family therapist', 'head of school',
            'executive director', 'clinical manager'
        ]
        
        names_with_titles = []
        
        # Pattern 1: "John Smith, Admissions Director"
        pattern1 = r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}),?\s+(Admissions Director|Clinical Director|Program Director|Intake Coordinator|Intake Manager|Family Therapist|Head of School|Executive Director)'
        matches = re.findall(pattern1, combined_content, re.IGNORECASE)
        for match in matches:
            names_with_titles.append({"name": match[0], "title": match[1]})
        
        # Pattern 2: "Admissions Director: Jane Doe"
        pattern2 = r'(Admissions Director|Clinical Director|Program Director|Intake Coordinator|Intake Manager|Family Therapist|Head of School|Executive Director)[:\s]+([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})'
        matches2 = re.findall(pattern2, combined_content, re.IGNORECASE)
        for match in matches2:
            names_with_titles.append({"name": match[1], "title": match[0]})
        
        # Pattern 3: Role keywords near names
        for role in target_roles:
            role_pattern = rf'{role}[^:]*:?\s*([A-Z][a-z]{{2,12}}\s+[A-Z][a-z]{{2,12}})'
            matches = re.findall(role_pattern, combined_content, re.IGNORECASE)
            for name in matches:
                names_with_titles.append({"name": name, "title": role.title()})
        
        # Dedupe and validate
        seen = set()
        bad_name_words = ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 
                         'programs', 'therapy', 'center', 'treatment', 'rehab',
                         'founder and', 'apy programs', 'ock facebook', 'help for',
                         'struggling', 'evoke', 'newport', 'academy']
        
        unique_names = []
        for item in names_with_titles:
            name = item["name"].strip()
            
            if name in seen or len(name) < 5:
                continue
            
            # Must be exactly 2 words
            words = name.split()
            if len(words) != 2:
                continue
            
            # Each word should be 2-12 chars
            if not all(2 <= len(w) <= 12 for w in words):
                continue
            
            # No bad words
            name_lower = name.lower()
            if any(bad in name_lower for bad in bad_name_words):
                continue
            
            # No HTML entities
            if '&' in name or '»' in name or '<' in name or '>' in name:
                continue
            
            # Must start with capital
            if not name[0].isupper():
                continue
            
            seen.add(name)
            unique_names.append(item)
        
        print(f"\n   👥 Found {len(unique_names)} unique names with roles")
        
        # Step 4: Extract contact info for each
        results = []
        for item in unique_names[:5]:  # Test first 5
            name = item["name"]
            title = item.get("title", "Director")
            
            # Find email near name
            name_pos = combined_content.lower().find(name.lower())
            email = None
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', nearby)
                valid_emails = [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_EMAIL_PREFIXES)]
                if valid_emails:
                    email = valid_emails[0]
            
            # Find phone near name
            phone = None
            if name_pos != -1:
                nearby = combined_content[max(0, name_pos-250):name_pos+250]
                phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', nearby)
                if phones:
                    digits = re.sub(r'[^\d]', '', phones[0])
                    if len(digits) == 10:
                        area_code = int(digits[:3])
                        exchange = int(digits[3:6])
                        if 200 <= area_code <= 999 and 200 <= exchange <= 999:
                            phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            
            # Extract organization
            org_match = re.search(r'<title>([^<]+)</title>', combined_content, re.IGNORECASE)
            organization = None
            if org_match:
                title = org_match.group(1)
                org = re.sub(r'\s*-\s*(Treatment|Center|Rehab|Recovery|Program).*', '', title, flags=re.I)
                organization = org.strip()[:100]
            
            print(f"\n      • {name} ({title})")
            print(f"        Email: {email or 'NOT FOUND'}")
            print(f"        Phone: {phone or 'NOT FOUND'}")
            print(f"        Org: {organization or 'NOT FOUND'}")
            
            results.append({
                'name': name,
                'title': title,
                'email': email,
                'phone': phone,
                'organization': organization
            })
        
        # Summary
        print(f"\n   📊 Summary:")
        print(f"      Names: {len(results)}")
        print(f"      Emails: {sum(1 for r in results if r['email'])}")
        print(f"      Phones: {sum(1 for r in results if r['phone'])}")
        
        if results:
            break  # Test one URL for now

if __name__ == "__main__":
    test_treatment_center_extraction()

