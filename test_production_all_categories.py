"""
Automated production test script for all 5 prospect categories
Tests via API endpoints and outputs comprehensive summary table
"""
import asyncio
import sys
import os
from typing import Dict, List, Any
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService

# Test configuration
LOCATION = "Washington DC"
MAX_RESULTS = 10
USER_ID = "test-user"

CATEGORIES = [
    {
        "id": "pediatricians",
        "name": "Pediatricians",
        "expected_min": 3,
        "priority": 1
    },
    {
        "id": "psychologists",
        "name": "Psychologists",
        "expected_min": 3,
        "priority": 2
    },
    {
        "id": "treatment_centers",
        "name": "Treatment Centers",
        "expected_min": 3,
        "priority": 3
    },
    {
        "id": "embassies",
        "name": "Embassies",
        "expected_min": 2,
        "priority": 4
    },
    {
        "id": "youth_sports",
        "name": "Youth Sports",
        "expected_min": 2,
        "priority": 5
    }
]

async def test_category(service: ProspectDiscoveryService, category: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single category"""
    category_id = category["id"]
    category_name = category["name"]
    
    result = {
        "category_id": category_id,
        "category_name": category_name,
        "success": False,
        "error": None,
        "prospects_found": 0,
        "with_names": 0,
        "with_titles": 0,
        "with_emails": 0,
        "with_phones": 0,
        "with_orgs": 0,
        "sample_prospects": [],
        "extraction_rate": 0.0
    }
    
    try:
        print(f"  Testing {category_name}...", end=" ", flush=True)
        
        response = await service.find_prospects_free(
            user_id=USER_ID,
            specialty="",
            location=LOCATION,
            max_results=MAX_RESULTS,
            categories=[category_id]
        )
        
        if not response.success:
            result["error"] = response.error or "Unknown error"
            print(f"❌ Failed: {result['error']}")
            return result
        
        prospects = response.prospects
        result["prospects_found"] = len(prospects)
        result["with_names"] = sum(1 for p in prospects if p.name)
        result["with_titles"] = sum(1 for p in prospects if p.title)
        result["with_emails"] = sum(1 for p in prospects if p.contact.email)
        result["with_phones"] = sum(1 for p in prospects if p.contact.phone)
        result["with_orgs"] = sum(1 for p in prospects if p.organization)
        result["success"] = True
        
        # Calculate extraction rate (names + titles + contacts / total possible)
        if prospects:
            total_possible = len(prospects) * 4  # name, title, email, phone
            extracted = (
                result["with_names"] +
                result["with_titles"] +
                result["with_emails"] +
                result["with_phones"]
            )
            result["extraction_rate"] = (extracted / total_possible) * 100
        
        # Store sample prospects
        for p in prospects[:3]:
            result["sample_prospects"].append({
                "name": p.name,
                "title": p.title or "N/A",
                "org": p.organization or "N/A",
                "has_email": bool(p.contact.email),
                "has_phone": bool(p.contact.phone)
            })
        
        # Status indicator
        if result["prospects_found"] >= category["expected_min"]:
            print(f"✅ {result['prospects_found']} prospects")
        elif result["prospects_found"] > 0:
            print(f"⚠️  {result['prospects_found']} prospects (expected {category['expected_min']}+)")
        else:
            print(f"❌ 0 prospects")
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Exception: {e}")
        return result

def print_summary_table(results: List[Dict[str, Any]]):
    """Print a formatted summary table"""
    print("\n" + "=" * 100)
    print("COMPREHENSIVE TEST RESULTS SUMMARY")
    print("=" * 100)
    print(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Location: {LOCATION}")
    print(f"Max Results per Category: {MAX_RESULTS}\n")
    
    # Header
    header = f"{'Category':<20} | {'Total':<6} | {'Names':<6} | {'Titles':<7} | {'Emails':<7} | {'Phones':<7} | {'Rate':<6} | {'Status'}"
    print(header)
    print("-" * 100)
    
    # Results rows
    for r in results:
        status_icon = "✅" if r["prospects_found"] > 0 else "❌"
        if r["error"]:
            status = f"❌ ERROR"
        elif r["prospects_found"] >= 3:
            status = f"✅ PASS"
        elif r["prospects_found"] > 0:
            status = f"⚠️  PARTIAL"
        else:
            status = f"❌ FAIL"
        
        row = (
            f"{r['category_name']:<20} | "
            f"{r['prospects_found']:<6} | "
            f"{r['with_names']:<6} | "
            f"{r['with_titles']:<7} | "
            f"{r['with_emails']:<7} | "
            f"{r['with_phones']:<7} | "
            f"{r['extraction_rate']:<5.1f}% | "
            f"{status}"
        )
        print(row)
    
    # Totals
    print("-" * 100)
    total_prospects = sum(r["prospects_found"] for r in results)
    total_names = sum(r["with_names"] for r in results)
    total_titles = sum(r["with_titles"] for r in results)
    total_emails = sum(r["with_emails"] for r in results)
    total_phones = sum(r["with_phones"] for r in results)
    
    overall_rate = 0.0
    if total_prospects > 0:
        total_possible = total_prospects * 4
        total_extracted = total_names + total_titles + total_emails + total_phones
        overall_rate = (total_extracted / total_possible) * 100
    
    totals_row = (
        f"{'TOTALS':<20} | "
        f"{total_prospects:<6} | "
        f"{total_names:<6} | "
        f"{total_titles:<7} | "
        f"{total_emails:<7} | "
        f"{total_phones:<7} | "
        f"{overall_rate:<5.1f}% | "
        f"{'N/A'}"
    )
    print(totals_row)
    print("=" * 100)
    
    # Success summary
    successful = sum(1 for r in results if r["prospects_found"] >= 3)
    partial = sum(1 for r in results if 0 < r["prospects_found"] < 3)
    failed = sum(1 for r in results if r["prospects_found"] == 0)
    
    print(f"\n📊 Success Summary:")
    print(f"   ✅ Fully Successful: {successful}/{len(results)} categories")
    print(f"   ⚠️  Partially Successful: {partial}/{len(results)} categories")
    print(f"   ❌ Failed: {failed}/{len(results)} categories")
    
    if successful >= 3:
        print(f"\n✅ OVERALL: PASS - At least 3 categories are working well")
    elif successful + partial >= 3:
        print(f"\n⚠️  OVERALL: PARTIAL - Some categories need optimization")
    else:
        print(f"\n❌ OVERALL: FAIL - Most categories need attention")

def print_detailed_samples(results: List[Dict[str, Any]]):
    """Print detailed sample prospects for each category"""
    print("\n" + "=" * 100)
    print("DETAILED SAMPLE PROSPECTS")
    print("=" * 100)
    
    for r in results:
        if not r["sample_prospects"]:
            continue
        
        print(f"\n{r['category_name']}:")
        print("-" * 100)
        
        for i, prospect in enumerate(r["sample_prospects"], 1):
            email_status = "✅" if prospect["has_email"] else "❌"
            phone_status = "✅" if prospect["has_phone"] else "❌"
            
            print(f"  {i}. {prospect['name']}")
            print(f"     Title: {prospect['title']}")
            print(f"     Org: {prospect['org']}")
            print(f"     Email: {email_status} | Phone: {phone_status}")
        
        if r["error"]:
            print(f"\n  ⚠️  Error: {r['error']}")

async def run_comprehensive_test():
    """Run comprehensive test for all categories"""
    print("=" * 100)
    print("AUTOMATED PRODUCTION TEST - ALL 5 CATEGORIES")
    print("=" * 100)
    print(f"\nLocation: {LOCATION}")
    print(f"Max Results per Category: {MAX_RESULTS}")
    print(f"\nTesting categories...\n")
    
    # Initialize service
    service = ProspectDiscoveryService()
    service._init_clients()
    
    # Check if Google Search is available
    if not service.google_search:
        print("❌ ERROR: Google Custom Search API not configured")
        print("   Please set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in Railway")
        return
    
    print("✅ Google Search API configured")
    if service.firecrawl:
        print("✅ Firecrawl available")
    else:
        print("⚠️  Firecrawl not available (will use free scraping)")
    print()
    
    # Test each category
    results = []
    for category in CATEGORIES:
        result = await test_category(service, category)
        results.append(result)
        # Small delay between tests
        await asyncio.sleep(1)
    
    # Print summary table
    print_summary_table(results)
    
    # Print detailed samples
    print_detailed_samples(results)
    
    # Recommendations
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)
    
    for r in results:
        if r["prospects_found"] == 0:
            print(f"\n❌ {r['category_name']}:")
            if r["error"]:
                print(f"   - Error: {r['error']}")
            else:
                print(f"   - No prospects found - check search queries and extraction patterns")
        elif r["prospects_found"] < r.get("expected_min", 3):
            print(f"\n⚠️  {r['category_name']}:")
            print(f"   - Found {r['prospects_found']} prospects (expected {r.get('expected_min', 3)}+)")
            if r["with_emails"] == 0 and r["with_phones"] == 0:
                print(f"   - Consider improving contact enrichment")
        elif r["extraction_rate"] < 50:
            print(f"\n⚠️  {r['category_name']}:")
            print(f"   - Low extraction rate ({r['extraction_rate']:.1f}%)")
            print(f"   - Consider improving name/title/contact extraction")
    
    print("\n" + "=" * 100)
    print("Test Complete!")
    print("=" * 100)

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())

