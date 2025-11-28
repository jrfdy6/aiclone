"""
Live test of treatment center extraction with real RTC/PHP/IOP domains
Tests the full pipeline without Firecrawl credits
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from app.services.prospect_discovery_service import ProspectDiscoveryService
from app.models.prospect_discovery import ProspectSource

# Test domains - known treatment centers
TEST_DOMAINS = [
    "https://www.newportacademy.com/",
    "https://www.evoketherapy.com/",
    "https://www.mcleanhospital.org/",  # McLean Hospital
    # Add more as needed
]

async def test_treatment_center_domain(url: str):
    """Test a single treatment center domain"""
    print("\n" + "=" * 70)
    print(f"TESTING: {url}")
    print("=" * 70)
    
    service = ProspectDiscoveryService()
    
    try:
        # Initialize clients (without Firecrawl)
        print("\n🔧 Initializing clients...")
        service._init_clients()
        print(f"   Firecrawl: {'✅ Available' if service.firecrawl else '❌ Not available (using free scrape)'}")
        print(f"   Google Search: {'✅ Available' if service.google_search else '❌ Not available'}")
        
        # Scrape main page
        print(f"\n🔍 Scraping main page...")
        main_content = service._free_scrape(url)
        
        if not main_content:
            print("❌ Failed to scrape main page")
            return None
        
        print(f"✅ Scraped {len(main_content)} chars")
        
        # Run extraction
        print(f"\n🔍 Running treatment center extraction...")
        prospects = service._extract_treatment_center(
            main_content=main_content,
            main_url=url,
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
                print(f"   Email: {'✅ ' + p.contact.email if p.contact.email else '❌ NOT FOUND'}")
                print(f"   Phone: {'✅ ' + p.contact.phone if p.contact.phone else '❌ NOT FOUND'}")
            
            # Summary
            total = len(prospects)
            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"Total prospects: {total}")
            print(f"With names: {sum(1 for p in prospects if p.name)} ({sum(1 for p in prospects if p.name)/total*100:.0f}%)")
            print(f"With titles: {sum(1 for p in prospects if p.title)} ({sum(1 for p in prospects if p.title)/total*100:.0f}%)")
            print(f"With emails: {sum(1 for p in prospects if p.contact.email)} ({sum(1 for p in prospects if p.contact.email)/total*100:.0f}%)")
            print(f"With phones: {sum(1 for p in prospects if p.contact.phone)} ({sum(1 for p in prospects if p.contact.phone)/total*100:.0f}%)")
            
            # Target roles found
            target_roles = ['admissions', 'director', 'coordinator', 'clinical', 'intake', 'chief', 'president']
            roles_found = set()
            for p in prospects:
                if p.title:
                    for role in target_roles:
                        if role in p.title.lower():
                            roles_found.add(role)
            
            if roles_found:
                print(f"\n🎯 Target roles found: {', '.join(sorted(roles_found))}")
            
            return prospects
        else:
            print("⚠️  No prospects found")
            return None
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_all_domains():
    """Test multiple treatment center domains"""
    print("=" * 70)
    print("TREATMENT CENTER EXTRACTION - LIVE TEST")
    print("Testing without Firecrawl credits (using free scrape + Google)")
    print("=" * 70)
    
    results = []
    
    for domain in TEST_DOMAINS:
        prospects = await test_treatment_center_domain(domain)
        results.append({
            'domain': domain,
            'prospects': prospects or [],
            'count': len(prospects) if prospects else 0
        })
    
    # Overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    
    total_prospects = sum(r['count'] for r in results)
    total_with_email = sum(sum(1 for p in r['prospects'] if p.contact.email) for r in results)
    total_with_phone = sum(sum(1 for p in r['prospects'] if p.contact.phone) for r in results)
    
    print(f"\nDomains tested: {len(TEST_DOMAINS)}")
    print(f"Total prospects found: {total_prospects}")
    
    if total_prospects > 0:
        print(f"With emails: {total_with_email} ({total_with_email/total_prospects*100:.0f}%)")
        print(f"With phones: {total_with_phone} ({total_with_phone/total_prospects*100:.0f}%)")
        print(f"\nAverage prospects per domain: {total_prospects/len(TEST_DOMAINS):.1f}")
    
    # Per-domain breakdown
    print("\nPer-domain results:")
    for r in results:
        print(f"  {r['domain']}: {r['count']} prospects")

if __name__ == "__main__":
    asyncio.run(test_all_domains())

