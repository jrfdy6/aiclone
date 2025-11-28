"""
Full test of treatment center extraction using actual service logic
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService
import asyncio

async def test_treatment_center_extraction():
    """Test treatment center extraction end-to-end"""
    print("=" * 60)
    print("TESTING TREATMENT CENTER EXTRACTION (FULL)")
    print("=" * 60)
    
    service = ProspectDiscoveryService()
    
    # Test URL - Newport Academy (known to have team page)
    test_url = "https://www.newportacademy.com/"
    
    print(f"\n📁 Testing URL: {test_url}")
    
    # Scrape the URL
    try:
        from app.services.firecrawl_client import get_firecrawl_client
        firecrawl = get_firecrawl_client()
        
        print("\n   🔍 Scraping main page...")
        scrape_result = firecrawl.scrape_url(test_url)
        if not scrape_result or not scrape_result.get('success'):
            print("   ❌ Failed to scrape with Firecrawl, trying free scrape...")
            main_content = service._free_scrape(test_url)
        else:
            main_content = scrape_result.get('markdown', '') or scrape_result.get('content', '')
        
        if not main_content:
            print("   ❌ No content scraped")
            return
        
        print(f"   ✅ Scraped {len(main_content)} chars")
        
        # Check if it's detected as treatment center
        url_lower = test_url.lower()
        is_treatment = (
            'treatment' in url_lower or 'rehab' in url_lower or 
            'residential' in url_lower or 'php' in url_lower or 
            'iop' in url_lower or '/team' in url_lower or 
            '/staff' in url_lower or '/leadership' in url_lower or 
            '/admissions' in url_lower
        )
        
        print(f"   🎯 Detected as treatment center: {is_treatment}")
        
        if is_treatment:
            print("\n   🔍 Running treatment center extraction...")
            # Call the extraction method directly
            prospects = service._extract_treatment_center(test_url, main_content)
            
            print(f"\n   📊 Results:")
            print(f"      Found {len(prospects)} prospects")
            
            for i, prospect in enumerate(prospects[:5], 1):
                print(f"\n      {i}. {prospect.get('name', 'N/A')}")
                print(f"         Title: {prospect.get('title', 'N/A')}")
                print(f"         Email: {prospect.get('email', 'NOT FOUND')}")
                print(f"         Phone: {prospect.get('phone', 'NOT FOUND')}")
                print(f"         Org: {prospect.get('organization', 'N/A')}")
        else:
            print("   ⚠️  Not detected as treatment center, trying generic extraction...")
            # Try generic extraction
            prospects = service._extract_generic(test_url, main_content)
            print(f"   Found {len(prospects)} prospects via generic extraction")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_treatment_center_extraction())

