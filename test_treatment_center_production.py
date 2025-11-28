"""
Production test of treatment center extraction
Tests with Firecrawl to handle JavaScript-rendered pages
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from app.services.prospect_discovery_service import ProspectDiscoveryService
from app.models.prospect_discovery import ProspectSource

async def test_production_extraction():
    """Test treatment center extraction with full pipeline"""
    print("=" * 70)
    print("TREATMENT CENTER EXTRACTION - PRODUCTION TEST")
    print("=" * 70)
    
    service = ProspectDiscoveryService()
    
    # Test URL - Newport Academy (known treatment center with team page)
    test_url = "https://www.newportacademy.com/"
    
    print(f"\n📁 Testing URL: {test_url}\n")
    
    try:
        # Initialize clients (including Firecrawl) - gracefully handle missing API keys
        print("🔧 Initializing clients (Firecrawl, etc.)...")
        try:
            service._init_clients()
            print("✅ Clients initialized\n")
        except Exception as init_error:
            print(f"⚠️  Client initialization warning: {init_error}")
            print("   (Will use free scraping fallback)\n")
        
        # Scrape main page using Firecrawl
        print("🔍 Scraping main page with Firecrawl...")
        try:
            if service.firecrawl:
                scrape_result = service.firecrawl.scrape_url(test_url)
                if scrape_result and scrape_result.get('success'):
                    main_content = scrape_result.get('markdown', '') or scrape_result.get('content', '')
                    print(f"✅ Scraped {len(main_content)} chars with Firecrawl")
                else:
                    print("⚠️  Firecrawl scrape unsuccessful, trying free scrape...")
                    main_content = service._free_scrape(test_url)
                    if main_content:
                        print(f"✅ Scraped {len(main_content)} chars with free scrape")
                    else:
                        print("❌ Failed to scrape main page")
                        return
            else:
                print("⚠️  Firecrawl not available, using free scrape...")
                main_content = service._free_scrape(test_url)
                if main_content:
                    print(f"✅ Scraped {len(main_content)} chars")
                else:
                    print("❌ Failed to scrape main page")
                    return
        except Exception as e:
            print(f"⚠️  Firecrawl error: {e}, trying free scrape...")
            main_content = service._free_scrape(test_url)
            if main_content:
                print(f"✅ Scraped {len(main_content)} chars with free scrape")
            else:
                print("❌ Failed to scrape")
                return
        
        # Run treatment center extraction
        print("\n" + "=" * 70)
        print("RUNNING TREATMENT CENTER EXTRACTION")
        print("=" * 70)
        print("\n🔍 Extracting prospects...")
        
        prospects = service._extract_treatment_center(
            main_content=main_content,
            main_url=test_url,
            source=ProspectSource.TREATMENT_CENTERS
        )
        
        print(f"\n✅ Extraction complete!")
        print(f"📊 Found {len(prospects)} prospects\n")
        
        if prospects:
            print("=" * 70)
            print("EXTRACTED PROSPECTS")
            print("=" * 70)
            
            for i, p in enumerate(prospects, 1):
                print(f"\n{i}. {p.name}")
                print(f"   Title: {p.title or 'N/A'}")
                print(f"   Organization: {p.organization or 'N/A'}")
                print(f"   Email: {p.contact.email or '❌ NOT FOUND'}")
                print(f"   Phone: {p.contact.phone or '❌ NOT FOUND'}")
                print(f"   Source URL: {p.source_url}")
                if p.fit_score:
                    print(f"   Fit Score: {p.fit_score}/100")
            
            # Summary
            total = len(prospects)
            if total > 0:
                print("\n" + "=" * 70)
                print("SUMMARY")
                print("=" * 70)
                print(f"Total prospects: {total}")
                print(f"With names: {sum(1 for p in prospects if p.name)} ({sum(1 for p in prospects if p.name)/total*100:.0f}%)")
                print(f"With titles: {sum(1 for p in prospects if p.title)} ({sum(1 for p in prospects if p.title)/total*100:.0f}%)")
                print(f"With emails: {sum(1 for p in prospects if p.contact.email)} ({sum(1 for p in prospects if p.contact.email)/total*100:.0f}%)")
                print(f"With phones: {sum(1 for p in prospects if p.contact.phone)} ({sum(1 for p in prospects if p.contact.phone)/total*100:.0f}%)")
                print(f"With org: {sum(1 for p in prospects if p.organization)} ({sum(1 for p in prospects if p.organization)/total*100:.0f}%)")
            
            # Show target roles found
            target_roles = ['admissions', 'director', 'coordinator', 'clinical', 'intake']
            roles_found = []
            for p in prospects:
                if p.title:
                    for role in target_roles:
                        if role in p.title.lower() and role not in roles_found:
                            roles_found.append(role)
            
            if roles_found:
                print(f"\n🎯 Target roles found: {', '.join(roles_found)}")
        else:
            print("\n⚠️  No prospects found")
            print("\nPossible reasons:")
            print("  - Team page not scraped (JavaScript not rendered)")
            print("  - No matching names/titles found")
            print("  - Name validation too strict")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_production_extraction())

