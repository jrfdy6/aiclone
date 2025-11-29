"""
Comprehensive extractor system test - validates all extractors + factory + orchestrator
"""
import sys
import os
import asyncio
from typing import List, Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.models.prospect_discovery import ProspectSource, DiscoveredProspect
from app.services.prospect_discovery.extractors.factory import extract_prospects_with_factory, get_extractor_for_url
from app.services.prospect_discovery.extractors import (
    PsychologyTodayExtractor,
    DoctorDirectoryExtractor,
    TreatmentCenterExtractor,
    EmbassyExtractor,
    YouthSportsExtractor,
    GenericExtractor,
)

# Test URLs (sample HTML snippets - in production these would be real scraped content)
TEST_HTML = {
    "psychology_today": """
    <html>
        <h1 class="provider-name">Dr. Jane Smith</h1>
        <span class="credentials">PhD, LCSW</span>
        <a href="tel:+1-202-555-1234">(202) 555-1234</a>
        <a href="https://example.com">Visit Website</a>
        <p>Licensed therapist specializing in adolescent mental health.</p>
    </html>
    """,
    "doctor_directory": """
    <html>
        <div data-qa-target="provider-phone">(202) 555-5678</div>
        <h2>John Doe, MD</h2>
        <p>Pediatrician at Children's Hospital</p>
    </html>
    """,
    "treatment_center": """
    <html>
        <div class="team-member">
            <h3>Sarah Johnson</h3>
            <p>Admissions Director</p>
            <p>Email: sjohnson@example.com</p>
            <p>Phone: (202) 555-9012</p>
        </div>
        <div class="team-member">
            <h3>Mike Williams</h3>
            <p>Clinical Director</p>
        </div>
    </html>
    """,
    "embassy": """
    <html>
        <table>
            <tr>
                <td>Education Officer</td>
                <td>Maria Garcia</td>
                <td>mgarcia@embassy.gov</td>
            </tr>
        </table>
    </html>
    """,
    "youth_sports": """
    <html>
        <div class="coach-card">
            <h3>Coach Tom Brown</h3>
            <p>Head Coach - Youth Soccer</p>
            <p>t.brown@sportsclub.com</p>
        </div>
    </html>
    """,
    "generic": """
    <html>
        <h1>Dr. Robert Lee, PhD</h1>
        <p>Educational Consultant</p>
        <p>Contact: rlee@consulting.com</p>
        <p>Phone: (202) 555-3456</p>
    </html>
    """
}

TEST_URLS = {
    "psychology_today": "https://www.psychologytoday.com/us/therapists/jane-smith-washington-dc/123456",
    "doctor_directory": "https://www.healthgrades.com/physician/dr-john-doe-abc123",
    "treatment_center": "https://example-treatment-center.com/team",
    "embassy": "https://embassy.example.gov/education",
    "youth_sports": "https://elitesocceracademy.com/coaches",
    "generic": "https://example-consultant.com/about",
}

def test_extractor_factory_routing():
    """Test that factory correctly routes URLs to extractors"""
    print("\n" + "="*60)
    print("TEST 1: Factory Routing")
    print("="*60)
    
    test_cases = [
        ("psychology_today", PsychologyTodayExtractor),
        ("doctor_directory", DoctorDirectoryExtractor),
        ("treatment_center", TreatmentCenterExtractor),
        ("embassy", EmbassyExtractor),
        ("youth_sports", YouthSportsExtractor),
        ("generic", GenericExtractor),
    ]
    
    all_passed = True
    for name, expected_class in test_cases:
        url = TEST_URLS[name]
        extractor = get_extractor_for_url(url, TEST_HTML[name], ProspectSource.GENERAL_SEARCH)
        
        if extractor is None:
            # Should use generic extractor
            extractor = GenericExtractor()
        
        actual_class = extractor.__class__.__name__
        expected_name = expected_class.__name__
        
        passed = actual_class == expected_name or (name == "generic" and actual_class == "GenericExtractor")
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"{status} {name:20} → {actual_class:30} (expected: {expected_name})")
        
        if not passed:
            all_passed = False
    
    return all_passed


def test_extractor_extraction():
    """Test that each extractor can extract prospects"""
    print("\n" + "="*60)
    print("TEST 2: Extractor Extraction")
    print("="*60)
    
    all_passed = True
    
    for name in TEST_HTML.keys():
        url = TEST_URLS[name]
        html = TEST_HTML[name]
        
        try:
            prospects = extract_prospects_with_factory(
                content=html,
                url=url,
                source=ProspectSource.GENERAL_SEARCH,
                category=None
            )
            
            has_prospects = len(prospects) > 0
            has_valid_names = any(p.name and p.name != "Unknown" for p in prospects)
            
            status = "✅ PASS" if has_prospects else "❌ FAIL"
            print(f"{status} {name:20} → {len(prospects)} prospects | Valid names: {has_valid_names}")
            
            if not has_prospects:
                all_passed = False
            else:
                # Print first prospect details
                if prospects:
                    p = prospects[0]
                    print(f"       └─ {p.name} | {p.title or 'No title'} | {p.organization or 'No org'}")
        
        except Exception as e:
            print(f"❌ FAIL {name:20} → Exception: {e}")
            all_passed = False
    
    return all_passed


def test_prospect_structure():
    """Test that extracted prospects have correct structure"""
    print("\n" + "="*60)
    print("TEST 3: Prospect Structure Validation")
    print("="*60)
    
    all_passed = True
    
    for name in ["generic", "treatment_center"]:  # Test with simpler cases
        url = TEST_URLS[name]
        html = TEST_HTML[name]
        
        try:
            prospects = extract_prospects_with_factory(
                content=html,
                url=url,
                source=ProspectSource.GENERAL_SEARCH,
                category=None
            )
            
            if not prospects:
                print(f"⚠️  SKIP {name:20} → No prospects extracted")
                continue
            
            p = prospects[0]
            
            # Check required fields
            has_name = bool(p.name and p.name != "Unknown")
            has_source_url = bool(p.source_url)
            has_source = p.source is not None
            has_contact = p.contact is not None
            
            all_valid = has_name and has_source_url and has_source and has_contact
            
            status = "✅ PASS" if all_valid else "❌ FAIL"
            print(f"{status} {name:20} → Structure valid: {all_valid}")
            print(f"       └─ name={has_name} source_url={has_source_url} source={has_source} contact={has_contact}")
            
            if not all_valid:
                all_passed = False
        
        except Exception as e:
            print(f"❌ FAIL {name:20} → Exception: {e}")
            all_passed = False
    
    return all_passed


def test_category_tagging():
    """Test that category tagging works"""
    print("\n" + "="*60)
    print("TEST 4: Category Tagging")
    print("="*60)
    
    all_passed = True
    
    test_categories = [
        ("pediatricians", "Pediatricians"),
        ("psychologists", "Psychologists & Psychiatrists"),
        ("treatment_centers", "Treatment Centers"),
    ]
    
    for category_id, expected_name in test_categories:
        url = TEST_URLS["generic"]
        html = TEST_HTML["generic"]
        
        try:
            prospects = extract_prospects_with_factory(
                content=html,
                url=url,
                source=ProspectSource.GENERAL_SEARCH,
                category=category_id
            )
            
            if not prospects:
                print(f"⚠️  SKIP {category_id:20} → No prospects extracted")
                continue
            
            p = prospects[0]
            has_category = len(p.specialty) > 0 and expected_name in p.specialty
            
            status = "✅ PASS" if has_category else "❌ FAIL"
            print(f"{status} {category_id:20} → Tagged: {p.specialty}")
            
            if not has_category:
                all_passed = False
        
        except Exception as e:
            print(f"❌ FAIL {category_id:20} → Exception: {e}")
            all_passed = False
    
    return all_passed


def test_error_handling():
    """Test that extractors handle errors gracefully"""
    print("\n" + "="*60)
    print("TEST 5: Error Handling")
    print("="*60)
    
    all_passed = True
    
    error_cases = [
        ("empty_html", ""),
        ("invalid_html", "<invalid>unclosed"),
        ("no_content", "<html><body></body></html>"),
    ]
    
    for name, html in error_cases:
        try:
            prospects = extract_prospects_with_factory(
                content=html,
                url="https://example.com",
                source=ProspectSource.GENERAL_SEARCH,
                category=None
            )
            
            # Should not crash, return empty list or handle gracefully
            is_list = isinstance(prospects, list)
            
            status = "✅ PASS" if is_list else "❌ FAIL"
            print(f"{status} {name:20} → Returned list: {is_list} | {len(prospects)} prospects")
            
            if not is_list:
                all_passed = False
        
        except Exception as e:
            print(f"❌ FAIL {name:20} → Exception not handled: {e}")
            all_passed = False
    
    return all_passed


def run_all_tests():
    """Run all tests and generate report"""
    print("\n" + "="*60)
    print("COMPREHENSIVE EXTRACTOR SYSTEM TEST")
    print("="*60)
    
    results = {
        "Factory Routing": test_extractor_factory_routing(),
        "Extractor Extraction": test_extractor_extraction(),
        "Prospect Structure": test_prospect_structure(),
        "Category Tagging": test_category_tagging(),
        "Error Handling": test_error_handling(),
    }
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

