"""
Test JSON parser for Healthgrades directory pages
"""
import re
import json
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
        print(f"   ❌ Scrape error: {e}")
        return ""

def extract_profile_urls_from_json(html_content: str, base_url: str):
    """Extract doctor profile URLs from Next.js __NEXT_DATA__ JSON"""
    profile_urls = []
    
    try:
        # Find the __NEXT_DATA__ script tag
        json_match = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
            html_content,
            re.DOTALL | re.IGNORECASE
        )
        
        if not json_match:
            print("   ⚠️  No __NEXT_DATA__ script tag found")
            return []
        
        print("   ✅ Found __NEXT_DATA__ script tag")
        json_str = json_match.group(1).strip()
        
        # Check JSON size
        print(f"   📦 JSON size: {len(json_str)} chars")
        
        data = json.loads(json_str)
        
        def find_profile_urls(obj, path="", depth=0):
            """Recursively search for profile URLs in JSON"""
            if depth > 8:  # Limit depth
                return []
            
            urls = []
            
            if isinstance(obj, dict):
                # Check for profileUrl keys
                if 'profileUrl' in obj:
                    url = obj['profileUrl']
                    if url and isinstance(url, str):
                        if '/provider/' in url.lower() or '/doctor/' in url.lower():
                            if not url.startswith('http'):
                                url = urljoin(base_url, url)
                            urls.append(url)
                            print(f"      ✅ Found profileUrl at {path}: {url}")
                
                # Check searchResults arrays
                if 'searchResults' in obj:
                    print(f"      📋 Found searchResults array at {path}")
                    if isinstance(obj['searchResults'], list):
                        for i, item in enumerate(obj['searchResults'][:5]):  # Limit to first 5
                            urls.extend(find_profile_urls(item, f"{path}.searchResults[{i}]", depth+1))
                
                # Check props.pageProps structure (common Next.js pattern)
                if 'props' in obj and isinstance(obj['props'], dict):
                    if 'pageProps' in obj['props']:
                        page_props = obj['props']['pageProps']
                        urls.extend(find_profile_urls(page_props, f"{path}.props.pageProps", depth+1))
                
                # Recurse into nested objects (limit)
                if depth < 5:
                    for key, value in list(obj.items())[:10]:  # Limit keys checked
                        if key not in ['profileUrl', 'searchResults']:
                            urls.extend(find_profile_urls(value, f"{path}.{key}", depth+1))
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj[:5]):  # Limit list items
                    urls.extend(find_profile_urls(item, f"{path}[{i}]", depth+1))
            
            return urls
        
        profile_urls = find_profile_urls(data)
        
        # Also try direct path access
        try:
            if 'props' in data and 'pageProps' in data['props']:
                page_props = data['props']['pageProps']
                if 'searchResults' in page_props:
                    print(f"   📋 Direct access: found searchResults in props.pageProps")
                    for result in page_props['searchResults'][:5]:
                        if 'profileUrl' in result:
                            url = result['profileUrl']
                            if not url.startswith('http'):
                                url = urljoin(base_url, url)
                            profile_urls.append(url)
        except Exception as e:
            print(f"   ⚠️  Direct path access failed: {e}")
        
        # Dedupe
        profile_urls = list(set(profile_urls))
        
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON decode error: {e}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return profile_urls

def test_json_extraction():
    """Test JSON extraction from Healthgrades directory"""
    print("=" * 60)
    print("TESTING JSON PROFILE URL EXTRACTION")
    print("=" * 60)
    
    directory_url = "https://www.healthgrades.com/pediatrics-directory/dc-district-of-columbia"
    print(f"\n📁 Testing: {directory_url}")
    
    # Step 1: Scrape directory page
    print(f"\n🔍 Step 1: Scraping directory page...")
    html_content = free_scrape(directory_url)
    
    if not html_content:
        print("   ❌ Failed to scrape")
        return
    
    print(f"   ✅ Scraped {len(html_content)} chars")
    
    # Step 2: Check what script tags exist
    print(f"\n🔍 Step 2: Analyzing HTML structure...")
    
    # Find all script tags
    soup = BeautifulSoup(html_content, 'html.parser')
    script_tags = soup.find_all('script', type='application/json')
    print(f"   Found {len(script_tags)} JSON script tags")
    
    for i, script in enumerate(script_tags[:5], 1):
        script_id = script.get('id', 'no-id')
        script_class = script.get('class', [])
        content_preview = script.string[:100] if script.string else ''
        print(f"   {i}. id='{script_id}', preview: {content_preview[:50]}...")
    
    # Also check for any script with "NEXT" or "DATA"
    next_scripts = soup.find_all('script', id=re.compile('next|data', re.I))
    if next_scripts:
        print(f"   Found {len(next_scripts)} scripts with 'next' or 'data' in ID")
        for script in next_scripts[:3]:
            print(f"      - id='{script.get('id')}'")
    
    # Check for inline JSON in script tags
    all_scripts = soup.find_all('script')
    json_scripts = [s for s in all_scripts if s.string and '{' in s.string and 'profileUrl' in s.string.lower()]
    if json_scripts:
        print(f"   ✅ Found {len(json_scripts)} scripts containing 'profileUrl'")
    
    # Check for links to provider/doctor pages
    provider_links = soup.find_all('a', href=re.compile(r'/provider/|/doctor/', re.I))
    print(f"   Found {len(provider_links)} links to /provider/ or /doctor/ pages")
    if provider_links:
        print(f"   Sample links:")
        for link in provider_links[:3]:
            href = link.get('href', '')
            text = link.get_text(strip=True)[:50]
            print(f"      - {href} ({text})")
    
    # Check for data attributes that might contain URLs
    data_urls = soup.find_all(attrs={'data-url': True}) + soup.find_all(attrs={'data-href': True})
    if data_urls:
        print(f"   Found {len(data_urls)} elements with data-url/data-href")
    
    # Step 3: Extract JSON
    print(f"\n🔍 Step 3: Extracting profile URLs from JSON...")
    parsed = urlparse(directory_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    profile_urls = extract_profile_urls_from_json(html_content, base_url)
    
    # Step 3: Results
    print(f"\n" + "=" * 60)
    print(f"RESULTS")
    print("=" * 60)
    print(f"✅ Profile URLs found: {len(profile_urls)}")
    
    if profile_urls:
        print(f"\n📋 Sample profile URLs:")
        for i, url in enumerate(profile_urls[:5], 1):
            print(f"   {i}. {url}")
        
        # Test scraping one profile
        if profile_urls:
            test_url = profile_urls[0]
            print(f"\n🧪 Testing phone extraction from profile page...")
            print(f"   URL: {test_url}")
            
            profile_html = free_scrape(test_url)
            if profile_html:
                # Extract phone using Healthgrades pattern
                phone_match = re.search(r'data-qa-target=["\']provider-phone["\'][^>]*>([^<]+)', profile_html, re.IGNORECASE)
                if phone_match:
                    phone = phone_match.group(1).strip()
                    print(f"   ✅ Phone found: {phone}")
                else:
                    # Try generic pattern
                    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', profile_html)
                    if phones:
                        print(f"   ✅ Phone found (generic): {phones[0]}")
                    else:
                        print(f"   ⚠️  No phone found")
    else:
        print(f"   ❌ No profile URLs extracted")
        print(f"   💡 This means the JSON structure is different than expected")

if __name__ == "__main__":
    test_json_extraction()

