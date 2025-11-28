"""
Automated production test script for all 5 prospect categories
Tests via API endpoints and outputs comprehensive summary table

Usage:
    python test_production_all_categories.py [--save-results] [--location LOCATION] [--max-results N]
    
Options:
    --save-results      Save results to a timestamped file
    --location LOCATION Location to search (default: "Washington DC")
    --max-results N     Max results per category (default: 10)
"""
import asyncio
import sys
import os
import argparse
import json
from typing import Dict, List, Any
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test all 5 prospect discovery categories')
parser.add_argument('--save-results', action='store_true', help='Save results to file')
parser.add_argument('--location', default='Washington DC', help='Location to search (default: Washington DC)')
parser.add_argument('--max-results', type=int, default=10, help='Max results per category (default: 10)')
args = parser.parse_args()

# Test configuration
LOCATION = args.location
MAX_RESULTS = args.max_results
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
    
    # Save results to file if requested
    if args.save_results:
        save_results_to_file(results)
    
    return results

def save_results_to_file(results: List[Dict[str, Any]]):
    """Save test results to a timestamped file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results_{timestamp}.txt"
    json_filename = f"test_results_{timestamp}.json"
    
    # Create output directory if it doesn't exist
    os.makedirs("test_results", exist_ok=True)
    filepath = os.path.join("test_results", filename)
    json_filepath = os.path.join("test_results", json_filename)
    
    # Generate summary stats
    total_prospects = sum(r["prospects_found"] for r in results)
    total_names = sum(r["with_names"] for r in results)
    total_titles = sum(r["with_titles"] for r in results)
    total_emails = sum(r["with_emails"] for r in results)
    total_phones = sum(r["with_phones"] for r in results)
    successful = sum(1 for r in results if r["prospects_found"] >= 3)
    
    # Calculate overall extraction rate
    overall_rate = 0.0
    if total_prospects > 0:
        total_possible = total_prospects * 4
        total_extracted = total_names + total_titles + total_emails + total_phones
        overall_rate = (total_extracted / total_possible) * 100
    
    # Write text file with summary
    with open(filepath, 'w') as f:
        f.write("=" * 100 + "\n")
        f.write("PROSPECT DISCOVERY TEST RESULTS\n")
        f.write("=" * 100 + "\n")
        f.write(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Location: {LOCATION}\n")
        f.write(f"Max Results per Category: {MAX_RESULTS}\n\n")
        
        # Summary table
        f.write("SUMMARY TABLE\n")
        f.write("-" * 100 + "\n")
        f.write(f"{'Category':<20} | {'Total':<6} | {'Names':<6} | {'Titles':<7} | {'Emails':<7} | {'Phones':<7} | {'Rate':<6}\n")
        f.write("-" * 100 + "\n")
        
        for r in results:
            status_icon = "✅" if r["prospects_found"] >= 3 else "❌"
            f.write(
                f"{r['category_name']:<20} | "
                f"{r['prospects_found']:<6} | "
                f"{r['with_names']:<6} | "
                f"{r['with_titles']:<7} | "
                f"{r['with_emails']:<7} | "
                f"{r['with_phones']:<7} | "
                f"{r['extraction_rate']:<5.1f}%\n"
            )
        
        f.write("-" * 100 + "\n")
        f.write(
            f"{'TOTALS':<20} | "
            f"{total_prospects:<6} | "
            f"{total_names:<6} | "
            f"{total_titles:<7} | "
            f"{total_emails:<7} | "
            f"{total_phones:<7} | "
            f"{overall_rate:<5.1f}%\n"
        )
        f.write("=" * 100 + "\n")
        
        # Detailed samples
        f.write("\nDETAILED SAMPLE PROSPECTS\n")
        f.write("=" * 100 + "\n")
        for r in results:
            if r["sample_prospects"]:
                f.write(f"\n{r['category_name']}:\n")
                f.write("-" * 100 + "\n")
                for i, prospect in enumerate(r["sample_prospects"], 1):
                    email_status = "✅" if prospect["has_email"] else "❌"
                    phone_status = "✅" if prospect["has_phone"] else "❌"
                    f.write(f"  {i}. {prospect['name']}\n")
                    f.write(f"     Title: {prospect['title']}\n")
                    f.write(f"     Org: {prospect['org']}\n")
                    f.write(f"     Email: {email_status} | Phone: {phone_status}\n")
                if r["error"]:
                    f.write(f"\n  ⚠️  Error: {r['error']}\n")
        
        # Summary
        f.write("\n" + "=" * 100 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 100 + "\n")
        f.write(f"\nTotal prospects found: {total_prospects}\n")
        f.write(f"Successful categories: {successful}/{len(results)}\n")
        f.write(f"Overall extraction rate: {overall_rate:.1f}%\n")
        f.write(f"Overall status: {'✅ PASS' if successful >= 3 else '⚠️ NEEDS ATTENTION'}\n")
    
    # Write JSON file for programmatic access
    json_data = {
        "test_date": datetime.now().isoformat(),
        "location": LOCATION,
        "max_results": MAX_RESULTS,
        "results": results,
        "summary": {
            "total_prospects": total_prospects,
            "total_names": total_names,
            "total_titles": total_titles,
            "total_emails": total_emails,
            "total_phones": total_phones,
            "overall_extraction_rate": overall_rate,
            "successful_categories": successful,
            "total_categories": len(results)
        }
    }
    
    with open(json_filepath, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"\n💾 Results saved to:")
    print(f"   Text: {filepath}")
    print(f"   JSON: {json_filepath}")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())

