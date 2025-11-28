"""
Test Psychology Today 2-hop extraction
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

def test_psychology_today_listing():
    """Test 2-hop extraction from Psychology Today listing page"""
    print("=" * 60)
    print("TESTING PSYCHOLOGY TODAY 2-HOP EXTRACTION")
    print("=" * 60)
    
    listing_url = "https://www.psychologytoday.com/us/therapists/dc/washington"
    print(f"\n📁 Step 1: Scraping listing page")
    print(f"   URL: {listing_url}")
    
    listing_content = free_scrape(listing_url)
    if not listing_content:
        print("   ❌ Failed to scrape")
        return
    
    print(f"   ✅ Scraped {len(listing_content)} chars")
    
    # Step 2: Extract profile URLs
    print(f"\n🔍 Step 2: Extracting profile URLs...")
    parsed = urlparse(listing_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    profile_urls = []
    
    # Psychology Today profile URLs are like: /us/therapists/jane-doe-washington-dc/195716
    # They have a slug (name) and an ID number
    
    # Pattern 1: Actual therapist profile URLs (have ID at end)
    profile_pattern = r'href=["\'](/us/therapists/[a-z0-9-]+/\d{4,})'
    matches = re.findall(profile_pattern, listing_content, re.IGNORECASE)
    for match in matches:
        if not any(skip in match.lower() for skip in ['?category', '/find', '/browse']):
            profile_urls.append(urljoin(base_url, match))
    
    # Pattern 2: Therapist profile links with full URLs
    profile_pattern2 = r'href=["\'](https://www\.psychologytoday\.com/us/therapists/[a-z0-9-]+/\d{4,})'
    matches2 = re.findall(profile_pattern2, listing_content, re.IGNORECASE)
    profile_urls.extend(matches2)
    
    # Also try BeautifulSoup with more specific filtering
    soup = BeautifulSoup(listing_content, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        # Look for therapist profile URLs (have ID number at end)
        if '/therapists/' in href and re.search(r'/\d{5,}', href):
            if '?category' not in href and '/find' not in href:
                if href.startswith('http'):
                    profile_urls.append(href)
                else:
                    profile_urls.append(urljoin(base_url, href))
    
    profile_urls = list(set(profile_urls))[:5]  # Limit to 5
    
    print(f"   ✅ Found {len(profile_urls)} profile URLs")
    
    if profile_urls:
        print(f"   Sample URLs:")
        for url in profile_urls[:3]:
            print(f"      - {url}")
    
    # Step 3: Test profile page extraction
    print(f"\n👨‍⚕️ Step 3: Testing profile page extraction...")
    
    results = []
    for i, profile_url in enumerate(profile_urls[:3], 1):  # Test 3 profiles
        print(f"\n   Profile {i}: {profile_url}")
        
        profile_content = free_scrape(profile_url)
        if not profile_content:
            print("      ❌ Failed to scrape")
            continue
        
        # Extract name
        name = None
        name_patterns = [
            r'<h1[^>]*class=["\'][^"\']*name[^"\']*["\'][^>]*>([^<]+)</h1>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<title>([^<]+)\s*-\s*Psychology Today</title>',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, profile_content, re.IGNORECASE)
            if match:
                name_candidate = match.group(1).strip()
                name_match = re.search(r'([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})(?:,|\s+MD|\s+PhD|\s+LCSW)?', name_candidate)
                if name_match:
                    name = name_match.group(1)
                    break
        
        if not name:
            # Try page title
            title_match = re.search(r'<title>([^<]+)</title>', profile_content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
                name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', title)
                if name_match:
                    name = name_match.group(1)
        
        print(f"      Name: {name or 'NOT FOUND'}")
        
        # Extract phone - Psychology Today uses tel: links
        phones = []
        
        # Look for tel: links
        tel_pattern = r'<a[^>]*href=["\']tel:([^"\']+)["\'][^>]*>([^<]+)</a>'
        tel_matches = re.findall(tel_pattern, profile_content, re.IGNORECASE)
        for match in tel_matches:
            phones.append(match[1] if match[1] else match[0])
        
        # Generic phone patterns
        phones.extend(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', profile_content))
        
        # Clean and format
        cleaned_phones = []
        for p in phones:
            digits = re.sub(r'[^\d]', '', str(p))
            if len(digits) == 10:
                cleaned_phones.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
        phones = list(set(cleaned_phones))
        phone = phones[0] if phones else None
        
        print(f"      Phone: {phone or 'NOT FOUND'}")
        
        # Extract email
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', profile_content)
        emails = [e for e in emails if not e.lower().startswith(('info@', 'contact@', 'support@', 'noreply@'))]
        email = emails[0] if emails else None
        
        print(f"      Email: {email or 'NOT FOUND'}")
        
        # Extract credentials
        cred_pattern = r'\b(PhD|PsyD|LCSW|LMFT|LPC|MEd|EdD|MD|NCC|LCPC|LMHC)\b'
        cred_match = re.search(cred_pattern, profile_content, re.IGNORECASE)
        title = cred_match.group(1) if cred_match else "Therapist"
        
        print(f"      Credentials: {title}")
        
        if name:
            results.append({
                'name': name,
                'phone': phone,
                'email': email,
                'title': title,
                'url': profile_url
            })
    
    # Summary
    print(f"\n" + "=" * 60)
    print(f"SUMMARY")
    print("=" * 60)
    print(f"✅ Profiles tested: {len(results)}")
    print(f"✅ Names found: {sum(1 for r in results if r['name'])}")
    print(f"✅ Phones found: {sum(1 for r in results if r['phone'])}")
    print(f"✅ Emails found: {sum(1 for r in results if r['email'])}")
    
    if results:
        print(f"\n📋 Results:")
        for r in results:
            print(f"   • {r['name']} ({r['title']})")
            print(f"     Phone: {r['phone'] or 'None'}")
            print(f"     Email: {r['email'] or 'None'}")

if __name__ == "__main__":
    test_psychology_today_listing()

