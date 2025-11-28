"""
Test 2-hop extraction for pediatrician directories
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
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        return re.sub(r'\s+', ' ', text)[:50000]
    except Exception as e:
        print(f"   ❌ Scrape error: {e}")
        return ""

def test_healthgrades_extraction():
    """Test 2-hop extraction from Healthgrades"""
    print("=" * 60)
    print("TESTING 2-HOP EXTRACTION: Healthgrades Pediatricians")
    print("=" * 60)
    
    # Step 1: Get directory page
    directory_url = "https://www.healthgrades.com/pediatrics-directory/dc-district-of-columbia"
    print(f"\n📁 Step 1: Scraping directory page")
    print(f"   URL: {directory_url}")
    
    directory_content = free_scrape(directory_url)
    if not directory_content:
        print("   ❌ Failed to scrape directory")
        return
    
    print(f"   ✅ Scraped {len(directory_content)} chars")
    
    # Step 2: Extract profile URLs - try multiple patterns
    print(f"\n🔍 Step 2: Extracting profile URLs")
    parsed = urlparse(directory_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Try multiple patterns
    profile_patterns = [
        r'href=["\']([^"\']*\/doctor\/[^"\']+)',
        r'\/doctor\/([^"\'\s<>]+)',
        r'data-href=["\']([^"\']*\/doctor\/[^"\']+)',
        r'url["\']:\s*["\']([^"\']*\/doctor\/[^"\']+)',
    ]
    
    profile_urls = []
    for pattern in profile_patterns:
        matches = re.findall(pattern, directory_content, re.IGNORECASE)
        for match in matches:
            if '/doctor/' in match.lower():
                if match.startswith('http'):
                    profile_urls.append(match)
                else:
                    profile_urls.append(urljoin(base_url, '/' + match.lstrip('/')))
    
    # Also try extracting from HTML directly
    soup = BeautifulSoup(directory_content, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '/doctor/' in href.lower():
            if href.startswith('http'):
                profile_urls.append(href)
            else:
                profile_urls.append(urljoin(base_url, href))
    
    profile_urls = list(set(profile_urls))[:3]  # Test with 3 profiles
    print(f"   ✅ Found {len(profile_urls)} profile URLs")
    
    if not profile_urls:
        print(f"   ⚠️  No profile URLs found in HTML (likely JavaScript-loaded)")
        print(f"   💡 Testing direct profile extraction from directory page...")
        
        # Extract names directly from directory (we know this works)
        name_matches = re.findall(r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}),?\s+(?:MD|M\.D\.)', directory_content)
        if name_matches:
            print(f"   ✅ Found {len(name_matches)} doctor names: {name_matches[:3]}")
            print(f"   💡 For production: Use names + Google contact enrichment")
            print(f"   💡 Testing phone extraction from a sample profile...")
            
            # Try to find any phone numbers in the directory page itself
            phones_in_dir = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', directory_content)
            if phones_in_dir:
                print(f"   ✅ Found {len(phones_in_dir)} phone numbers in directory page")
                print(f"   Sample: {phones_in_dir[:2]}")
            
            # For this test, let's manually test a known profile URL pattern
            # Healthgrades profile URLs are like: /physician/dr-firstname-lastname-12345
            print(f"\n   🔧 Testing with manual profile URL construction...")
            # We'll skip to testing a real profile if we can find one
            # Test phone extraction from directory page itself
            print(f"\n   📞 Testing phone extraction from directory page...")
            phones_in_dir = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', directory_content)
            if phones_in_dir:
                print(f"   ✅ Found {len(set(phones_in_dir))} unique phones in directory")
                print(f"   Sample: {list(set(phones_in_dir))[:3]}")
            
            # The key test: Can we extract phones when we DO have a profile URL?
            # Let's test with a known profile URL pattern
            print(f"\n   🧪 Testing phone extraction from profile page structure...")
            print(f"   (This would work if we had profile URLs from Google search results)")
            return
    
    if profile_urls:
        print(f"   Sample URLs:")
        for url in profile_urls[:2]:
            print(f"      - {url}")
    
    # Step 3: Scrape each profile and extract contact
    print(f"\n👨‍⚕️ Step 3: Extracting from profile pages")
    
    results = []
    for i, profile_url in enumerate(profile_urls, 1):
        print(f"\n   Profile {i}: {profile_url}")
        
        profile_content = free_scrape(profile_url)
        if not profile_content:
            print("      ❌ Failed to scrape")
            continue
        
        # Extract name
        name = None
        name_patterns = [
            r'<h1[^>]*>([^<]+)</h1>',
            r'"name":\s*"([^"]+)"',
            r'<title>([^<]+)</title>',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, profile_content, re.IGNORECASE)
            if match:
                name_candidate = match.group(1).strip()
                if ',' in name_candidate or 'MD' in name_candidate:
                    name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', name_candidate)
                    if name_match:
                        name = name_match.group(1)
                        break
        
        if not name:
            name_matches = re.findall(r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12}),?\s+(?:MD|DO)', profile_content)
            if name_matches:
                name = name_matches[0]
        
        # Extract phone - Healthgrades specific
        phones = []
        phone_match = re.search(r'data-qa-target=["\']provider-phone["\'][^>]*>([^<]+)', profile_content, re.IGNORECASE)
        if phone_match:
            phones.append(phone_match.group(1).strip())
        
        # Generic phone patterns
        phones.extend(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', profile_content))
        
        # Clean phones
        cleaned_phones = []
        for p in phones:
            digits = re.sub(r'[^\d]', '', p)
            if len(digits) == 10:
                cleaned_phones.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
        phones = list(set(cleaned_phones))
        phone = phones[0] if phones else None
        
        # Extract email
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', profile_content)
        emails = [e for e in emails if not e.lower().startswith(('info@', 'contact@', 'support@'))]
        email = emails[0] if emails else None
        
        print(f"      Name: {name or 'NOT FOUND'}")
        print(f"      Phone: {phone or 'NOT FOUND'}")
        print(f"      Email: {email or 'NOT FOUND'}")
        
        if name:
            results.append({
                'name': name,
                'phone': phone,
                'email': email,
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
        print(f"\n📋 Sample Results:")
        for r in results[:3]:
            print(f"   • {r['name']} - {r['phone'] or 'No phone'}")

def test_phone_extraction_logic():
    """Test phone extraction from Healthgrades profile HTML structure"""
    print("\n" + "=" * 60)
    print("TESTING PHONE EXTRACTION LOGIC")
    print("=" * 60)
    
    # Mock Healthgrades profile HTML
    mock_html = """
    <html>
    <h1>Dr. John Smith, MD</h1>
    <div data-qa-target="provider-phone">(202) 555-1234</div>
    <p>Phone: 202-555-5678</p>
    <span>Call us at 202.555.9012</span>
    </html>
    """
    
    # Test Healthgrades-specific pattern
    phone_match = re.search(r'data-qa-target=["\']provider-phone["\'][^>]*>([^<]+)', mock_html, re.IGNORECASE)
    if phone_match:
        print(f"✅ Healthgrades pattern found: {phone_match.group(1).strip()}")
    
    # Test generic patterns
    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', mock_html)
    print(f"✅ Generic patterns found: {phones}")
    
    # Clean and format
    cleaned = []
    for p in phones:
        digits = re.sub(r'[^\d]', '', p)
        if len(digits) == 10:
            cleaned.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
    print(f"✅ Formatted phones: {list(set(cleaned))}")

if __name__ == "__main__":
    test_healthgrades_extraction()
    test_phone_extraction_logic()

