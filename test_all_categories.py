"""
Comprehensive test of all 5 prospect discovery categories
Tests extraction logic and optionally API endpoints
"""
import sys
import os
import asyncio
from typing import Dict, List, Any
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService
from app.models.prospect_discovery import ProspectSource

# Test configuration
LOCATION = "Washington DC"
MAX_RESULTS = 10

CATEGORIES = {
    "pediatricians": {
        "name": "Pediatricians",
        "test_url": "https://www.healthgrades.com/physician/dr-jane-smith-xxxxx",  # Example
        "expected_roles": ["pediatrician", "md", "doctor"]
    },
    "psychologists": {
        "name": "Psychologists & Psychiatrists",
        "test_url": "https://www.psychologytoday.com/us/therapists/dc/washington",
        "expected_roles": ["psychologist", "therapist", "lcsw", "phd"]
    },
    "treatment_centers": {
        "name": "Treatment Centers",
        "test_url": "https://www.newportacademy.com/",
        "expected_roles": ["director", "admissions", "clinical"]
    },
    "embassies": {
        "name": "Embassies",
        "test_url": "https://www.ambafrance-us.org/",  # French Embassy example
        "expected_roles": ["education officer", "cultural", "attaché"]
    },
    "youth_sports": {
        "name": "Youth Sports",
        "test_url": "https://www.dcelitesoccer.com/",  # Example
        "expected_roles": ["coach", "director", "program"]
    }
}

async def test_category_extraction(category_id: str, category_info: Dict[str, Any]) -> Dict[str, Any]:
    """Test extraction for a single category"""
    print("\n" + "=" * 70)
    print(f"TESTING: {category_info['name']}")
    print("=" * 70)
    
    service = ProspectDiscoveryService()
    results = {
        "category": category_id,
        "name": category_info["name"],
        "success": False,
        "prospects_found": 0,
        "with_names": 0,
        "with_titles": 0,
        "with_emails": 0,
        "with_phones": 0,
        "with_orgs": 0,
        "errors": [],
        "sample_prospects": []
    }
    
    try:
        # Initialize clients
        service._init_clients()
        
        # Try to scrape test URL
        test_url = category_info.get("test_url")
        if not test_url:
            results["errors"].append("No test URL provided")
            return results
        
        print(f"\n📁 Testing URL: {test_url}")
        
        # Scrape main page
        print("🔍 Scraping...")
        main_content = service._free_scrape(test_url)
        
        if not main_content:
            # Try Firecrawl if available
            if service.firecrawl:
                try:
                    scraped = service.firecrawl.scrape_url(test_url)
                    if scraped and scraped.get('success'):
                        main_content = scraped.get('markdown', '') or scraped.get('content', '')
                except:
                    pass
        
        if not main_content:
            results["errors"].append(f"Failed to scrape {test_url}")
            print("❌ Failed to scrape")
            return results
        
        print(f"✅ Scraped {len(main_content)} chars")
        
        # Determine source based on category
        source_map = {
            "pediatricians": ProspectSource.GENERAL_SEARCH,
            "psychologists": ProspectSource.PSYCHOLOGY_TODAY,
            "treatment_centers": ProspectSource.TREATMENT_CENTERS,
            "embassies": ProspectSource.GENERAL_SEARCH,
            "youth_sports": ProspectSource.GENERAL_SEARCH
        }
        source = source_map.get(category_id, ProspectSource.GENERAL_SEARCH)
        
        # Run extraction
        print("🔍 Extracting prospects...")
        prospects = service.extract_prospects_from_content(
            content=main_content,
            url=test_url,
            source=source
        )
        
        results["prospects_found"] = len(prospects)
        results["with_names"] = sum(1 for p in prospects if p.name)
        results["with_titles"] = sum(1 for p in prospects if p.title)
        results["with_emails"] = sum(1 for p in prospects if p.contact.email)
        results["with_phones"] = sum(1 for p in prospects if p.contact.phone)
        results["with_orgs"] = sum(1 for p in prospects if p.organization)
        results["success"] = len(prospects) > 0
        
        # Get sample prospects
        for p in prospects[:3]:
            results["sample_prospects"].append({
                "name": p.name,
                "title": p.title,
                "organization": p.organization,
                "email": bool(p.contact.email),
                "phone": bool(p.contact.phone)
            })
        
        # Print results
        print(f"\n📊 Results:")
        print(f"   Prospects found: {len(prospects)}")
        print(f"   With names: {results['with_names']}")
        print(f"   With titles: {results['with_titles']}")
        print(f"   With emails: {results['with_emails']}")
        print(f"   With phones: {results['with_phones']}")
        
        if prospects:
            print(f"\n   Sample prospects:")
            for i, p in enumerate(prospects[:3], 1):
                print(f"   {i}. {p.name}")
                print(f"      Title: {p.title or 'N/A'}")
                print(f"      Org: {p.organization or 'N/A'}")
                print(f"      Email: {'✅' if p.contact.email else '❌'}")
                print(f"      Phone: {'✅' if p.contact.phone else '❌'}")
        else:
            print("   ⚠️  No prospects found")
        
    except Exception as e:
        results["errors"].append(str(e))
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return results

async def test_all_categories():
    """Test all categories"""
    print("=" * 70)
    print("COMPREHENSIVE PROSPECT DISCOVERY TEST")
    print("Testing All 5 Categories")
    print("=" * 70)
    
    all_results = []
    
    for category_id, category_info in CATEGORIES.items():
        results = await test_category_extraction(category_id, category_info)
        all_results.append(results)
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    total_prospects = sum(r["prospects_found"] for r in all_results)
    total_with_email = sum(r["with_emails"] for r in all_results)
    total_with_phone = sum(r["with_phones"] for r in all_results)
    
    print(f"\nCategories tested: {len(all_results)}")
    print(f"Total prospects found: {total_prospects}")
    print(f"Total with emails: {total_with_email}")
    print(f"Total with phones: {total_with_phone}")
    
    print("\nPer-category breakdown:")
    for r in all_results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['name']}: {r['prospects_found']} prospects")
        if r["errors"]:
            for error in r["errors"]:
                print(f"     Error: {error}")
    
    # Overall success rate
    successful = sum(1 for r in all_results if r["success"])
    print(f"\nOverall success rate: {successful}/{len(all_results)} categories ({successful/len(all_results)*100:.0f}%)")
    
    return all_results

if __name__ == "__main__":
    asyncio.run(test_all_categories())

