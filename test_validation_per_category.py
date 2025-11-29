#!/usr/bin/env python3
"""
Per-Category Validation Test Script
Tests each category individually, analyzes results, and suggests improvements.
"""
import requests
import json
import sys
import time
from typing import List, Dict, Any
from datetime import datetime

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


def clear_prospects():
    """Clear all prospects"""
    try:
        response = requests.delete(
            f"{API_URL}/api/prospects/clear-all",
            params={"user_id": USER_ID},
            timeout=30
        )
        if response.status_code == 200:
            deleted = response.json().get("deleted", 0)
            print(f"✅ Cleared {deleted} prospects\n")
            return True
        return False
    except Exception as e:
        print(f"⚠️  Error clearing: {e}\n")
        return False


def run_search(category: str, max_results: int = 10):
    """Run a prospect discovery search for a single category"""
    url = f"{API_URL}/api/prospect-discovery/search-free"
    payload = {
        "user_id": USER_ID,
        "categories": [category],
        "location": "Washington DC",
        "max_results": max_results,
        "save_to_prospects": True
    }
    
    print(f"🔍 Running search: {CATEGORIES.get(category, category)}")
    print(f"   Max results: {max_results}")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            prospects = data.get("prospects", [])
            print(f"✅ Found {len(prospects)} prospects in search results")
            return prospects
        else:
            print(f"❌ Search failed: {data.get('error', 'Unknown error')}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def get_saved_prospects():
    """Get prospects from the pipeline"""
    url = f"{API_URL}/api/prospects/"
    params = {"user_id": USER_ID, "limit": 500}
    
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
    org = prospect.get("company") or prospect.get("organization", "").strip()
    email = prospect.get("email", "")
    phone = prospect.get("phone", "")
    tags = prospect.get("tags", [])
    
    # Check name issues
    if not name:
        issues.append("Missing name")
    else:
        words = name.split()
        
        # Single word names
        if len(words) < 2:
            issues.append(f"Single word name: '{name}'")
        
        # Location phrases
        location_phrases = ["capitol heights", "north bethesda", "silver spring"]
        if name.lower() in location_phrases:
            issues.append(f"Location phrase, not a person: '{name}'")
        
        # Role words at end
        role_words = ["counselor", "clinical", "director", "therapist"]
        if words and words[-1].lower() in role_words:
            issues.append(f"Name ends with role word: '{name}'")
        
        # Descriptor words
        descriptor_words = ["bilingual", "clinical"]
        if any(w.lower() in descriptor_words for w in words):
            warnings.append(f"Name contains descriptor: '{name}'")
        
        # Bad words
        bad_words = ["janak", "scadmoa"]
        if any(w.lower() in bad_words for w in words):
            issues.append(f"Name contains invalid word: '{name}'")
    
    # Check organization issues
    if not org or org == "—":
        warnings.append("Missing organization name")
    else:
        org_lower = org.lower()
        org_words = org.split()
        
        # Too long (likely a sentence)
        if len(org_words) > 10:
            issues.append(f"Organization too long (sentence): '{org[:60]}...'")
        elif len(org_words) > 6:
            issues.append(f"Organization too many words ({len(org_words)}): '{org[:60]}...'")
        
        # Template phrases
        template_phrases = [
            "may also be known",
            "and hospital",
            "pediatricians may",
            "where children come first",
            "powered by"
        ]
        if any(phrase in org_lower for phrase in template_phrases):
            issues.append(f"Organization contains template phrase: '{org[:60]}...'")
        
        # Directory sites
        directory_sites = ["pmc", "ncbi", "savannahmastercalendar", "royaltyinstitute"]
        if any(site in org_lower for site in directory_sites):
            issues.append(f"Directory site as organization: '{org}'")
        
        # Generic/lowercase names
        if org.islower() and len(org_words) <= 3:
            warnings.append(f"Organization might be a directory site: '{org}'")
    
    # Check contact info
    has_email = bool(email)
    has_phone = bool(phone)
    
    if not has_email and not has_phone:
        warnings.append("No contact information")
    
    # Check category tagging
    category_mismatch = False
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
    """Analyze prospects for a specific category"""
    print(f"\n📊 Analyzing {len(prospects)} prospects for {CATEGORIES.get(category, category)}...")
    
    analyzed = [analyze_prospect(p) for p in prospects]
    
    # Count issues
    total_issues = sum(len(a["issues"]) for a in analyzed)
    total_warnings = sum(len(a["warnings"]) for a in analyzed)
    
    # Categorize prospects
    good_prospects = [a for a in analyzed if not a["issues"]]
    bad_prospects = [a for a in analyzed if a["issues"]]
    warning_prospects = [a for a in analyzed if a["warnings"] and not a["issues"]]
    
    # Common issues
    issue_counts = {}
    for a in analyzed:
        for issue in a["issues"]:
            issue_type = issue.split(":")[0] if ":" in issue else issue
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
    
    # Common warnings
    warning_counts = {}
    for a in analyzed:
        for warning in a["warnings"]:
            warning_type = warning.split(":")[0] if ":" in warning else warning
            warning_counts[warning_type] = warning_counts.get(warning_type, 0) + 1
    
    # Quality metrics
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
        "issue_counts": issue_counts,
        "warning_counts": warning_counts
    }


def print_category_report(analysis: Dict[str, Any]):
    """Print detailed analysis report for a category"""
    category_name = CATEGORIES.get(analysis['category'], analysis['category'])
    print("\n" + "="*80)
    print(f"📋 VALIDATION REPORT: {category_name}")
    print("="*80)
    
    print(f"\n📊 Summary:")
    print(f"   Total prospects: {analysis['total']}")
    print(f"   ✅ Good prospects: {analysis['good']} ({analysis['good']/max(analysis['total'],1)*100:.1f}%)")
    print(f"   ❌ Bad prospects: {analysis['bad']} ({analysis['bad']/max(analysis['total'],1)*100:.1f}%)")
    print(f"   ⚠️  With warnings: {analysis['warnings']}")
    print(f"   🎯 Quality Score: {analysis['quality_score']:.1f}%")
    print(f"   📞 Contact Coverage: {analysis['contact_coverage']:.1f}%")
    
    if analysis['issue_counts']:
        print(f"\n❌ Common Issues:")
        for issue, count in sorted(analysis['issue_counts'].items(), key=lambda x: x[1], reverse=True):
            print(f"   • {issue}: {count}")
    
    if analysis['warning_counts']:
        print(f"\n⚠️  Common Warnings:")
        for warning, count in sorted(analysis['warning_counts'].items(), key=lambda x: x[1], reverse=True):
            print(f"   • {warning}: {count}")
    
    if analysis['bad_prospects']:
        print(f"\n❌ Bad Prospects ({len(analysis['bad_prospects'])}):")
        for i, prospect in enumerate(analysis['bad_prospects'][:5], 1):
            print(f"\n   {i}. {prospect['name']} | {prospect['organization']}")
            print(f"      Issues: {', '.join(prospect['issues'][:2])}")
            if prospect['warnings']:
                print(f"      Warnings: {', '.join(prospect['warnings'][:1])}")
    
    if analysis['good_prospects']:
        print(f"\n✅ Good Prospects ({len(analysis['good_prospects'])}):")
        for i, prospect in enumerate(analysis['good_prospects'][:3], 1):
            contact = "✓" if prospect['has_contact'] else "✗"
            tags_str = ", ".join(prospect['tags']) if prospect['tags'] else "None"
            print(f"   {i}. {prospect['name']} | {prospect['organization']} [{contact}]")
            print(f"      Tags: {tags_str} | Score: {prospect['score']}")
    
    print("="*80)


def generate_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on analysis"""
    recommendations = []
    
    issue_counts = analysis['issue_counts']
    warning_counts = analysis['warning_counts']
    
    # Quality threshold
    if analysis['quality_score'] < 80:
        recommendations.append(f"Quality score {analysis['quality_score']:.1f}% is below target (80%). Review bad prospects above.")
    
    # Contact coverage
    if analysis['contact_coverage'] < 70:
        recommendations.append(f"Contact coverage {analysis['contact_coverage']:.1f}% is low. Improve contact extraction.")
    
    # Specific issues
    if 'Organization too many words' in issue_counts:
        recommendations.append("Stricter organization validation: Filter organizations with >6 words")
    
    if 'Organization contains template phrase' in issue_counts:
        recommendations.append("Add more template phrase patterns: 'and hospital', 'may also be known'")
    
    if 'Missing organization name' in warning_counts and warning_counts['Missing organization name'] > analysis['total'] * 0.3:
        recommendations.append(f"Improve organization extraction - {warning_counts['Missing organization name']} missing ({warning_counts['Missing organization name']/analysis['total']*100:.1f}%)")
    
    if 'No contact information' in warning_counts and warning_counts['No contact information'] > analysis['total'] * 0.3:
        recommendations.append(f"Improve contact extraction - {warning_counts['No contact information']} missing ({warning_counts['No contact information']/analysis['total']*100:.1f}%)")
    
    if 'Single word name' in issue_counts:
        recommendations.append("Ensure name validation requires 2-3 words")
    
    return recommendations


def test_category(category: str, max_results: int = 10, clear_first: bool = True):
    """Test a single category and return analysis"""
    print(f"\n{'='*80}")
    print(f"🧪 TESTING: {CATEGORIES.get(category, category)}")
    print(f"{'='*80}\n")
    
    # Clear prospects if requested
    if clear_first:
        clear_prospects()
    
    # Run search
    search_prospects = run_search(category, max_results)
    
    if not search_prospects:
        print("❌ No prospects found in search. Skipping analysis.")
        return None
    
    # Wait for prospects to save
    print("⏳ Waiting for prospects to save...")
    time.sleep(3)
    
    # Get saved prospects
    saved_prospects = get_saved_prospects()
    
    if not saved_prospects:
        print("⚠️  No saved prospects found. Using search results...")
        saved_prospects = search_prospects
    
    # Analyze
    analysis = analyze_category_results(saved_prospects, category)
    
    # Print report
    print_category_report(analysis)
    
    # Generate recommendations
    recommendations = generate_recommendations(analysis)
    if recommendations:
        print("\n💡 Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    
    # Quality assessment
    print(f"\n🎯 Assessment:")
    if analysis['quality_score'] >= 90:
        print("   ✅ Excellent quality! Validation is working well.")
    elif analysis['quality_score'] >= 80:
        print("   ✅ Good quality. Minor improvements possible.")
    elif analysis['quality_score'] >= 70:
        print("   ⚠️  Acceptable quality. Improvements recommended.")
    else:
        print("   ❌ Quality needs improvement. Review issues above.")
    
    return analysis


def main():
    """Main test loop"""
    print("🚀 Per-Category Validation Testing")
    print("="*80)
    print("\nTesting each category individually for focused analysis.\n")
    
    if len(sys.argv) > 1:
        # Test specific category
        category = sys.argv[1]
        if category not in CATEGORIES:
            print(f"❌ Unknown category: {category}")
            print(f"Available categories: {', '.join(CATEGORIES.keys())}")
            return
        
        test_category(category, max_results=10)
    else:
        # Test all categories
        results = {}
        
        for category in CATEGORIES.keys():
            analysis = test_category(category, max_results=10, clear_first=True)
            if analysis:
                results[category] = analysis
            
            # Pause between categories
            print("\n⏸️  Pausing before next category...\n")
            time.sleep(2)
        
        # Overall summary
        if results:
            print("\n" + "="*80)
            print("📊 OVERALL SUMMARY")
            print("="*80)
            
            total_prospects = sum(r['total'] for r in results.values())
            total_good = sum(r['good'] for r in results.values())
            total_bad = sum(r['bad'] for r in results.values())
            avg_quality = sum(r['quality_score'] for r in results.values()) / len(results)
            avg_contact = sum(r['contact_coverage'] for r in results.values()) / len(results)
            
            print(f"\nTotal Categories Tested: {len(results)}")
            print(f"Total Prospects: {total_prospects}")
            print(f"Good Prospects: {total_good} ({total_good/max(total_prospects,1)*100:.1f}%)")
            print(f"Bad Prospects: {total_bad} ({total_bad/max(total_prospects,1)*100:.1f}%)")
            print(f"Average Quality Score: {avg_quality:.1f}%")
            print(f"Average Contact Coverage: {avg_contact:.1f}%")
            
            print(f"\n📋 By Category:")
            for category, analysis in results.items():
                status = "✅" if analysis['quality_score'] >= 80 else "⚠️" if analysis['quality_score'] >= 70 else "❌"
                print(f"   {status} {CATEGORIES[category]}: {analysis['quality_score']:.1f}% ({analysis['good']}/{analysis['total']} good)")


if __name__ == "__main__":
    main()

