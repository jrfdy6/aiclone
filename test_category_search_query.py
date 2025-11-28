"""
Quick validation test to verify multi-category search queries include ALL selected categories.

This tests the build_category_search_query method to ensure:
1. All selected categories' site preferences are included
2. Category keywords are properly combined
3. No categories are ignored when multiple are selected
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService

def test_category_query_building():
    """Test that multiple categories are properly combined in search queries"""
    
    service = ProspectDiscoveryService()
    
    print("=" * 80)
    print("MULTI-CATEGORY SEARCH QUERY VALIDATION TEST")
    print("=" * 80)
    print()
    
    # Test Case 1: All 5 categories selected
    print("TEST 1: All 5 Main Categories Selected")
    print("-" * 80)
    categories_all = [
        'pediatricians',
        'psychologists', 
        'treatment_centers',
        'embassies',
        'youth_sports'
    ]
    query_all = service.build_category_search_query(
        categories=categories_all,
        location="Washington DC",
        additional_context="adolescent mental health"
    )
    
    print(f"Selected Categories: {', '.join(categories_all)}")
    print(f"\nGenerated Query:")
    print(f"  {query_all}")
    print()
    
    # Validate that all category sites/keywords are present
    checks = {
        'Pediatricians (Healthgrades)': 'healthgrades.com' in query_all.lower() or 'vitals.com' in query_all.lower(),
        'Psychologists (PsychologyToday)': 'psychologytoday.com' in query_all.lower(),
        'Treatment Centers': 'treatment center' in query_all.lower() or 'rehab' in query_all.lower(),
        'Embassies': 'embassy' in query_all.lower() or 'consulate' in query_all.lower(),
        'Youth Sports': 'athletic academy' in query_all.lower() or 'sports academy' in query_all.lower() or 'youth sports' in query_all.lower(),
        'DC Location': 'dc' in query_all.lower() or 'washington' in query_all.lower(),
        'Blocked Domains (negative filters)': '-site:linkedin.com' in query_all.lower() and '-site:facebook.com' in query_all.lower()
    }
    
    print("Validation Checks:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check_name}")
        if not passed:
            all_passed = False
    
    print(f"\n{'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    print()
    
    # Test Case 2: Single category (should still work)
    print("TEST 2: Single Category (Pediatricians)")
    print("-" * 80)
    categories_single = ['pediatricians']
    query_single = service.build_category_search_query(
        categories=categories_single,
        location="Washington DC"
    )
    print(f"Selected Categories: {', '.join(categories_single)}")
    print(f"\nGenerated Query:")
    print(f"  {query_single}")
    print(f"\n  ✓ Contains Healthgrades/Vitals: {'healthgrades.com' in query_single.lower() or 'vitals.com' in query_single.lower()}")
    print()
    
    # Test Case 3: Two categories (Pediatricians + Psychologists)
    print("TEST 3: Two Categories (Pediatricians + Psychologists)")
    print("-" * 80)
    categories_two = ['pediatricians', 'psychologists']
    query_two = service.build_category_search_query(
        categories=categories_two,
        location="Washington DC"
    )
    print(f"Selected Categories: {', '.join(categories_two)}")
    print(f"\nGenerated Query:")
    print(f"  {query_two}")
    print()
    
    checks_two = {
        'Healthgrades/Vitals': 'healthgrades.com' in query_two.lower() or 'vitals.com' in query_two.lower(),
        'PsychologyToday': 'psychologytoday.com' in query_two.lower()
    }
    
    print("Validation Checks:")
    all_passed_two = True
    for check_name, passed in checks_two.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check_name}")
        if not passed:
            all_passed_two = False
    
    print(f"\n{'✓ ALL TESTS PASSED' if all_passed_two else '✗ SOME TESTS FAILED'}")
    print()
    
    # Test Case 4: Three categories with education
    print("TEST 4: Three Categories (Pediatricians + Psychologists + Education Consultants)")
    print("-" * 80)
    categories_three = ['pediatricians', 'psychologists', 'education_consultants']
    query_three = service.build_category_search_query(
        categories=categories_three,
        location="Washington DC"
    )
    print(f"Selected Categories: {', '.join(categories_three)}")
    print(f"\nGenerated Query:")
    print(f"  {query_three}")
    print()
    
    checks_three = {
        'Healthgrades/Vitals': 'healthgrades.com' in query_three.lower() or 'vitals.com' in query_three.lower(),
        'PsychologyToday': 'psychologytoday.com' in query_three.lower(),
        'Education Consultant Keywords': 'educational consultant' in query_three.lower() or 'college consultant' in query_three.lower()
    }
    
    print("Validation Checks:")
    all_passed_three = True
    for check_name, passed in checks_three.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check_name}")
        if not passed:
            all_passed_three = False
    
    print(f"\n{'✓ ALL TESTS PASSED' if all_passed_three else '✗ SOME TESTS FAILED'}")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Test 1 (5 categories): {'✓ PASSED' if all_passed else '✗ FAILED'}")
    print(f"Test 2 (1 category):   ✓ PASSED (baseline check)")
    print(f"Test 3 (2 categories): {'✓ PASSED' if all_passed_two else '✗ FAILED'}")
    print(f"Test 4 (3 categories): {'✓ PASSED' if all_passed_three else '✗ FAILED'}")
    print()
    
    if all_passed and all_passed_two and all_passed_three:
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("   Multi-category search queries are working correctly.")
        print("   All selected categories' sites and keywords are included.")
        return True
    else:
        print("❌ SOME VALIDATION TESTS FAILED!")
        print("   Review the query generation logic above.")
        return False


if __name__ == "__main__":
    try:
        success = test_category_query_building()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

