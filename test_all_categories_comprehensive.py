#!/usr/bin/env python3
"""
Comprehensive Test Script for All Categories
Tests all prospect discovery categories sequentially and generates a detailed report.
"""
import requests
import json
import sys
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

API_URL = 'https://aiclone-production-32dc.up.railway.app'
USER_ID = 'dev-user'

CATEGORIES = {
    "education_consultants": "🎓 Education Consultants",
    "pediatricians": "👨‍⚕️ Pediatricians",
    "psychologists_psychiatrists": "🧠 Psychologists & Psychiatrists",
    "treatment_centers": "🏥 Treatment Centers",
    "embassies": "🏛️ Embassies & Diplomats",
    "youth_sports": "⚽ Youth Sports Programs",
    "mom_groups": "👨‍👩‍👧 Mom Groups & Parent Networks",
    "international_students": "🌍 International Student Services",
}

QUALITY_THRESHOLD = 80  # Target quality score


def clear_prospects():
    """Clear all prospects from pipeline"""
    try:
        response = requests.delete(
            f"{API_URL}/api/prospects/clear-all",
            params={"user_id": USER_ID},
            timeout=30
        )
        if response.status_code == 200:
            deleted = response.json().get("deleted", 0)
            return deleted
        return 0
    except Exception as e:
        print(f"⚠️  Error clearing prospects: {e}")
        return 0


def run_search(category: str, max_results: int = 10):
    """Run a prospect discovery search for a category"""
    url = f"{API_URL}/api/prospect-discovery/search-free"
    payload = {
        "user_id": USER_ID,
        "categories": [category],
        "location": "Washington DC",
        "max_results": max_results,
        "save_to_prospects": True
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=180)
        elapsed = time.time() - start_time
        
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            prospects = data.get("prospects", [])
            return {
                "success": True,
                "prospects": prospects,
                "total_found": len(prospects),
                "search_query": data.get("search_query_used", ""),
                "elapsed_time": elapsed
            }
        else:
            return {
                "success": False,
                "error": data.get("error", "Unknown error"),
                "prospects": [],
                "total_found": 0,
                "elapsed_time": elapsed
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "prospects": [],
            "total_found": 0,
            "elapsed_time": 0
        }


def get_saved_prospects():
    """Get prospects from the pipeline"""
    url = f"{API_URL}/api/prospects/"
    params = {"user_id": USER_ID, "limit": 500}  # API max is 500
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            return data.get("prospects", [])
        return []
    except Exception as e:
        print(f"❌ Error fetching prospects: {e}")
        return []


def analyze_prospect(prospect: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single prospect for quality issues"""
    issues = []
    warnings = []
    
    name = prospect.get("name", "").strip()
    org = (prospect.get("company") or prospect.get("organization") or "").strip()
    email = prospect.get("email", "") or ""
    phone = prospect.get("phone", "") or ""
    tags = prospect.get("tags", []) or []
    
    # Name validation
    if not name:
        issues.append("Missing name")
    else:
        words = name.split()
        
        if len(words) < 2:
            issues.append(f"Single word name: '{name}'")
        
        location_phrases = ["capitol heights", "north bethesda", "silver spring"]
        if name.lower() in location_phrases:
            issues.append(f"Location phrase, not a person: '{name}'")
        
        role_words = ["counselor", "clinical", "director", "therapist"]
        if words and words[-1].lower() in role_words:
            issues.append(f"Name ends with role word: '{name}'")
        
        descriptor_words = ["bilingual", "clinical"]
        if any(w.lower() in descriptor_words for w in words):
            warnings.append(f"Name contains descriptor: '{name}'")
        
        bad_words = ["janak", "scadmoa", "information", "accreditation"]
        if any(w.lower() in bad_words for w in words):
            issues.append(f"Name contains invalid word: '{name}'")
    
    # Organization validation
    if not org or org == "—":
        warnings.append("Missing organization name")
    else:
        org_lower = org.lower()
        org_words = org.split()
        
        if len(org_words) > 10:
            issues.append(f"Organization too long (sentence): '{org[:60]}...'")
        elif len(org_words) > 6:
            issues.append(f"Organization too many words ({len(org_words)}): '{org[:60]}...'")
        
        template_phrases = [
            "may also be known", "and hospital", "pediatricians may",
            "where children come first", "powered by", "observation hours"
        ]
        if any(phrase in org_lower for phrase in template_phrases):
            issues.append(f"Organization contains template phrase: '{org[:60]}...'")
        
        directory_sites = ["pmc", "ncbi", "savannahmastercalendar", "royaltyinstitute"]
        if any(site in org_lower for site in directory_sites):
            issues.append(f"Directory site as organization: '{org}'")
    
    # Contact info
    has_email = bool(email)
    has_phone = bool(phone)
    
    if not has_email and not has_phone:
        warnings.append("No contact information")
    
    # Category tags
    if not tags:
        warnings.append("No category tags")
    
    return {
        "name": name,
        "organization": org,
        "email": email,
        "phone": phone,
        "tags": tags,
        "issues": issues,
        "warnings": warnings,
        "has_contact": has_email or has_phone,
        "score": prospect.get("fit_score", 0)
    }


def analyze_category_results(prospects: List[Dict[str, Any]], category: str) -> Dict[str, Any]:
    """Analyze all prospects for a category"""
    analyzed = [analyze_prospect(p) for p in prospects]
    
    total_issues = sum(len(a["issues"]) for a in analyzed)
    total_warnings = sum(len(a["warnings"]) for a in analyzed)
    
    good_prospects = [a for a in analyzed if not a["issues"]]
    bad_prospects = [a for a in analyzed if a["issues"]]
    warning_prospects = [a for a in analyzed if a["warnings"] and not a["issues"]]
    
    issue_counts = defaultdict(int)
    for a in analyzed:
        for issue in a["issues"]:
            issue_type = issue.split(":")[0] if ":" in issue else issue
            issue_counts[issue_type] += 1
    
    warning_counts = defaultdict(int)
    for a in analyzed:
        for warning in a["warnings"]:
            warning_type = warning.split(":")[0] if ":" in warning else warning
            warning_counts[warning_type] += 1
    
    quality_score = (len(good_prospects) / max(len(prospects), 1)) * 100
    contact_coverage = (sum(1 for a in analyzed if a["has_contact"]) / max(len(prospects), 1)) * 100
    
    return {
        "category": category,
        "total": len(prospects),
        "good": len(good_prospects),
        "bad": len(bad_prospects),
        "warnings": len(warning_prospects),
        "total_issues": total_issues,
        "total_warnings": total_warnings,
        "quality_score": quality_score,
        "contact_coverage": contact_coverage,
        "good_prospects": good_prospects,
        "bad_prospects": bad_prospects,
        "warning_prospects": warning_prospects,
        "issue_counts": dict(issue_counts),
        "warning_counts": dict(warning_counts)
    }


def print_category_report(analysis: Dict[str, Any], search_result: Dict[str, Any]):
    """Print detailed report for a category"""
    category_name = CATEGORIES.get(analysis['category'], analysis['category'])
    status = "✅" if analysis['quality_score'] >= QUALITY_THRESHOLD else "⚠️" if analysis['quality_score'] >= 70 else "❌"
    
    print(f"\n{status} {category_name}")
    print(f"   Quality Score: {analysis['quality_score']:.1f}%")
    print(f"   Total Prospects: {analysis['total']}")
    print(f"   Good: {analysis['good']} | Bad: {analysis['bad']} | Warnings: {analysis['warnings']}")
    print(f"   Contact Coverage: {analysis['contact_coverage']:.1f}%")
    print(f"   Search Time: {search_result.get('elapsed_time', 0):.1f}s")
    
    if analysis['issue_counts']:
        print(f"   Issues: {', '.join(f'{k}({v})' for k, v in sorted(analysis['issue_counts'].items(), key=lambda x: x[1], reverse=True)[:3])}")
    
    if analysis['bad_prospects']:
        print(f"   ❌ Bad Examples:")
        for p in analysis['bad_prospects'][:2]:
            print(f"      • {p['name']} | {p['organization'][:50]} - {', '.join(p['issues'][:2])}")


def test_all_categories(clear_between: bool = True, max_results: int = 10):
    """Test all categories sequentially"""
    print("="*80)
    print("🚀 COMPREHENSIVE CATEGORY TEST SUITE")
    print("="*80)
    print(f"\nTesting {len(CATEGORIES)} categories with max {max_results} results each")
    print(f"Quality Threshold: {QUALITY_THRESHOLD}%")
    print(f"Clear between tests: {clear_between}\n")
    
    results = {}
    overall_start = time.time()
    
    for i, (category, category_name) in enumerate(CATEGORIES.items(), 1):
        print(f"\n[{i}/{len(CATEGORIES)}] Testing: {category_name}")
        print("-" * 80)
        
        # Clear prospects before each test
        if clear_between:
            cleared = clear_prospects()
            if cleared > 0:
                print(f"🧹 Cleared {cleared} prospects")
        
        # Run search
        print(f"🔍 Running search...")
        search_result = run_search(category, max_results)
        
        if not search_result["success"]:
            print(f"❌ Search failed: {search_result.get('error', 'Unknown error')}")
            results[category] = {
                "success": False,
                "error": search_result.get("error"),
                "analysis": None
            }
            continue
        
        print(f"✅ Found {search_result['total_found']} prospects in search results")
        print(f"   Query: {search_result.get('search_query', 'N/A')[:80]}...")
        
        # Wait for prospects to save
        if search_result['total_found'] > 0:
            print("⏳ Waiting for prospects to save...")
            time.sleep(3)
        
        # Get saved prospects
        saved_prospects = get_saved_prospects()
        
        if not saved_prospects:
            print("⚠️  No saved prospects found. Using search results...")
            saved_prospects = search_result['prospects']
        
        print(f"📥 Retrieved {len(saved_prospects)} saved prospects")
        
        # Analyze
        analysis = analyze_category_results(saved_prospects, category)
        
        # Print report
        print_category_report(analysis, search_result)
        
        results[category] = {
            "success": True,
            "search_result": search_result,
            "analysis": analysis
        }
        
        # Pause between categories
        if i < len(CATEGORIES):
            print("\n⏸️  Pausing before next category...")
            time.sleep(2)
    
    total_time = time.time() - overall_start
    
    # Generate summary
    print_summary(results, total_time)
    
    return results


def print_summary(results: Dict[str, Dict[str, Any]], total_time: float):
    """Print overall summary"""
    print("\n" + "="*80)
    print("📊 COMPREHENSIVE TEST SUMMARY")
    print("="*80)
    
    successful = [r for r in results.values() if r.get("success") and r.get("analysis")]
    failed = [r for r in results.values() if not r.get("success")]
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total Categories Tested: {len(results)}")
    print(f"   Successful: {len(successful)}")
    print(f"   Failed: {len(failed)}")
    print(f"   Total Test Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    
    if successful:
        total_prospects = sum(r["analysis"]["total"] for r in successful)
        total_good = sum(r["analysis"]["good"] for r in successful)
        total_bad = sum(r["analysis"]["bad"] for r in successful)
        avg_quality = sum(r["analysis"]["quality_score"] for r in successful) / len(successful)
        avg_contact = sum(r["analysis"]["contact_coverage"] for r in successful) / len(successful)
        
        print(f"\n📊 Prospect Statistics:")
        print(f"   Total Prospects: {total_prospects}")
        print(f"   Good Prospects: {total_good} ({total_good/max(total_prospects,1)*100:.1f}%)")
        print(f"   Bad Prospects: {total_bad} ({total_bad/max(total_prospects,1)*100:.1f}%)")
        print(f"   Average Quality Score: {avg_quality:.1f}%")
        print(f"   Average Contact Coverage: {avg_contact:.1f}%")
        
        print(f"\n📋 Results by Category:")
        for category, result in results.items():
            if result.get("success") and result.get("analysis"):
                analysis = result["analysis"]
                status = "✅" if analysis['quality_score'] >= QUALITY_THRESHOLD else "⚠️" if analysis['quality_score'] >= 70 else "❌"
                print(f"   {status} {CATEGORIES[category]}: {analysis['quality_score']:.1f}% ({analysis['good']}/{analysis['total']} good)")
            else:
                print(f"   ❌ {CATEGORIES[category]}: FAILED - {result.get('error', 'Unknown error')}")
        
        # Categories meeting threshold
        passing = [r for r in successful if r["analysis"]["quality_score"] >= QUALITY_THRESHOLD]
        print(f"\n✅ Categories Meeting {QUALITY_THRESHOLD}% Threshold: {len(passing)}/{len(successful)}")
        
        if len(passing) == len(successful):
            print("🎉 ALL CATEGORIES PASSED! System is ready for production!")
        elif len(passing) >= len(successful) * 0.8:
            print("✅ Most categories passed. System is in good shape.")
        else:
            print("⚠️  Some categories need improvement. Review results above.")
    
    if failed:
        print(f"\n❌ Failed Categories:")
        for category, result in results.items():
            if not result.get("success"):
                print(f"   • {CATEGORIES[category]}: {result.get('error', 'Unknown error')}")
    
    print("="*80)


def save_report(results: Dict[str, Dict[str, Any]], filename: str = None):
    """Save detailed report to file"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_report_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed report saved to: {filename}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test all prospect discovery categories")
    parser.add_argument("--category", help="Test single category only")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear prospects between tests")
    parser.add_argument("--max-results", type=int, default=10, help="Max results per category")
    parser.add_argument("--save-report", action="store_true", help="Save detailed report to JSON")
    
    args = parser.parse_args()
    
    if args.category:
        # Test single category
        if args.category not in CATEGORIES:
            print(f"❌ Unknown category: {args.category}")
            print(f"Available: {', '.join(CATEGORIES.keys())}")
            return
        
        print(f"Testing single category: {CATEGORIES[args.category]}\n")
        cleared = clear_prospects()
        search_result = run_search(args.category, args.max_results)
        
        if search_result["success"]:
            time.sleep(3)
            saved_prospects = get_saved_prospects() or search_result['prospects']
            analysis = analyze_category_results(saved_prospects, args.category)
            print_category_report(analysis, search_result)
        else:
            print(f"❌ Failed: {search_result.get('error')}")
    else:
        # Test all categories
        results = test_all_categories(
            clear_between=not args.no_clear,
            max_results=args.max_results
        )
        
        if args.save_report:
            save_report(results)


if __name__ == "__main__":
    main()

