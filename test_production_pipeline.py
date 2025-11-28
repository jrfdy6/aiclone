"""
Test the full prospect discovery pipeline via API
This tests the complete flow: Google Search -> Scraping -> Extraction -> Saving
"""
import sys
import os
import asyncio
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService

# Test configuration
LOCATION = "Washington DC"
MAX_RESULTS = 10

CATEGORIES = [
    "pediatricians",
    "psychologists", 
    "treatment_centers",
    "embassies",
    "youth_sports"
]

async def test_category_search(category: str):
    """Test a single category via the full search pipeline"""
    print("\n" + "=" * 70)
    print(f"TESTING: {category.replace('_', ' ').title()}")
    print("=" * 70)
    
    service = ProspectDiscoveryService()
    
    try:
        print(f"\n🔍 Searching for {category} in {LOCATION}...")
        
        # Use the full pipeline
        response = await service.find_prospects_free(
            user_id="test-user",
            specialty="",  # Not used when categories provided
            location=LOCATION,
            max_results=MAX_RESULTS,
            categories=[category]
        )
        
        if not response.success:
            print(f"❌ Search failed: {response.error}")
            return {
                "category": category,
                "success": False,
                "error": response.error,
                "prospects": 0
            }
        
        prospects = response.prospects
        print(f"\n✅ Search complete!")
        print(f"📊 Found {len(prospects)} prospects")
        
        if prospects:
            print(f"\n   Names: {sum(1 for p in prospects if p.name)}")
            print(f"   Titles: {sum(1 for p in prospects if p.title)}")
            print(f"   Emails: {sum(1 for p in prospects if p.contact.email)}")
            print(f"   Phones: {sum(1 for p in prospects if p.contact.phone)}")
            
            print(f"\n   Sample prospects:")
            for i, p in enumerate(prospects[:3], 1):
                print(f"   {i}. {p.name}")
                print(f"      Title: {p.title or 'N/A'}")
                print(f"      Org: {p.organization or 'N/A'}")
                print(f"      Email: {'✅ ' + p.contact.email if p.contact.email else '❌'}")
                print(f"      Phone: {'✅ ' + p.contact.phone if p.contact.phone else '❌'}")
        else:
            print("   ⚠️  No prospects found")
        
        return {
            "category": category,
            "success": response.success,
            "prospects": len(prospects),
            "with_names": sum(1 for p in prospects if p.name),
            "with_titles": sum(1 for p in prospects if p.title),
            "with_emails": sum(1 for p in prospects if p.contact.email),
            "with_phones": sum(1 for p in prospects if p.contact.phone),
            "error": response.error if not response.success else None
        }
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "category": category,
            "success": False,
            "error": str(e),
            "prospects": 0
        }

async def test_all_categories():
    """Test all categories via full pipeline"""
    print("=" * 70)
    print("FULL PIPELINE TEST - ALL CATEGORIES")
    print("=" * 70)
    print(f"\nLocation: {LOCATION}")
    print(f"Max results per category: {MAX_RESULTS}")
    print(f"\nTesting via Google Search + Extraction pipeline...")
    
    results = []
    
    for category in CATEGORIES:
        result = await test_category_search(category)
        results.append(result)
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    total_prospects = sum(r["prospects"] for r in results)
    total_with_email = sum(r.get("with_emails", 0) for r in results)
    total_with_phone = sum(r.get("with_phones", 0) for r in results)
    successful = sum(1 for r in results if r["success"])
    
    print(f"\nCategories tested: {len(results)}")
    print(f"Successful searches: {successful}/{len(results)}")
    print(f"Total prospects found: {total_prospects}")
    print(f"Total with emails: {total_with_email}")
    print(f"Total with phones: {total_with_phone}")
    
    print("\nPer-category breakdown:")
    for r in results:
        status = "✅" if r["success"] and r["prospects"] > 0 else "❌"
        print(f"  {status} {r['category']}: {r['prospects']} prospects")
        if r.get("error"):
            print(f"     Error: {r['error']}")
        elif r["prospects"] > 0:
            print(f"     - Names: {r.get('with_names', 0)}")
            print(f"     - Titles: {r.get('with_titles', 0)}")
            print(f"     - Emails: {r.get('with_emails', 0)}")
            print(f"     - Phones: {r.get('with_phones', 0)}")
    
    # Success criteria check
    print("\n" + "=" * 70)
    print("SUCCESS CRITERIA CHECK")
    print("=" * 70)
    
    min_prospects_per_category = 3
    categories_with_enough = sum(1 for r in results if r["prospects"] >= min_prospects_per_category)
    
    print(f"\n✅ Categories with {min_prospects_per_category}+ prospects: {categories_with_enough}/{len(results)}")
    
    if categories_with_enough >= 3:
        print("✅ Overall: PASS - At least 3 categories are working")
    else:
        print("⚠️  Overall: PARTIAL - Some categories need optimization")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_all_categories())

