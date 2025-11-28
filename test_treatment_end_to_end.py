"""
End-to-end test of treatment center extraction
Tests the actual service method
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from app.services.prospect_discovery_service import ProspectDiscoveryService
from app.models.prospect_discovery import ProspectSource

async def test_end_to_end():
    """Test treatment center extraction end-to-end"""
    print("=" * 60)
    print("END-TO-END TREATMENT CENTER EXTRACTION TEST")
    print("=" * 60)
    
    service = ProspectDiscoveryService()
    
    # Test URL
    test_url = "https://www.newportacademy.com/"
    
    print(f"\n📁 Testing: {test_url}\n")
    
    try:
        # Scrape content
        main_content = service._free_scrape(test_url)
        
        if not main_content:
            print("❌ Failed to scrape")
            return
        
        print(f"✅ Scraped {len(main_content)} chars")
        
        # Run extraction
        print("\n🔍 Running treatment center extraction...\n")
        prospects = service._extract_treatment_center(
            main_content=main_content,
            main_url=test_url,
            source=ProspectSource.TREATMENT_CENTERS
        )
        
        print(f"📊 RESULTS: Found {len(prospects)} prospects\n")
        
        if prospects:
            for i, p in enumerate(prospects[:10], 1):
                print(f"{i}. {p.name}")
                print(f"   Title: {p.title or 'N/A'}")
                print(f"   Email: {p.contact.email or 'NOT FOUND'}")
                print(f"   Phone: {p.contact.phone or 'NOT FOUND'}")
                print(f"   Org: {p.organization or 'N/A'}")
                print()
        else:
            print("⚠️  No prospects found")
            
        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total prospects: {len(prospects)}")
        print(f"With emails: {sum(1 for p in prospects if p.contact.email)}")
        print(f"With phones: {sum(1 for p in prospects if p.contact.phone)}")
        print(f"With titles: {sum(1 for p in prospects if p.title)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_end_to_end())

