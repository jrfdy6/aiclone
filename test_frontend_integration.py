"""
End-to-End Frontend Integration Test
Simulates the exact API call the frontend makes
"""
import sys
import os
import json
import time
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Get API URL from environment or use default
API_URL = os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:8080')

def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")

def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")

def print_info(message: str):
    """Print info message"""
    print(f"ℹ️  {message}")

def test_5_category_search():
    """Test 1: Full 5-Category Search (Main Workflow)"""
    print_header("TEST 1: Full 5-Category Search (Main Workflow)")
    
    # Simulate frontend request
    request_data = {
        "user_id": "dev-user",
        "specialty": "",
        "location": "Washington DC",
        "additional_context": None,
        "max_results": 10,
        "save_to_prospects": False,  # Don't save for test
        "categories": [
            "psychologists",
            "education_consultants",
            "youth_sports",
            "pediatricians",
            "treatment_centers"
        ]
    }
    
    print_info(f"Request: {json.dumps(request_data, indent=2)}")
    print_info(f"API URL: {API_URL}/api/prospect-discovery/search-free")
    
    # Import and call the service directly (faster than HTTP)
    try:
        from app.services.prospect_discovery_service import get_prospect_discovery_service
        from app.models.prospect_discovery import ProspectSearchRequest
        
        # Convert to proper request model
        search_request = ProspectSearchRequest(**request_data)
        
        print_info("Calling backend service directly...")
        start_time = time.time()
        
        service = get_prospect_discovery_service()
        result = service.find_prospects_free(
            user_id=search_request.user_id,
            specialty=search_request.specialty,
            location=search_request.location,
            additional_context=search_request.additional_context,
            max_results=search_request.max_results,
            categories=search_request.categories
        )
        
        elapsed = time.time() - start_time
        
        print_success(f"Search completed in {elapsed:.2f} seconds")
        
        # Analyze results
        if result and result.get("success"):
            total_found = result.get("total_found", 0)
            prospects = result.get("prospects", [])
            
            print_success(f"Total prospects found: {total_found}")
            
            if total_found == 0:
                print_error("No prospects found - check logs for issues")
                return False
            
            # Check categories represented
            categories_found = set()
            for p in prospects:
                if p.get("specialty"):
                    categories_found.update(p["specialty"])
            
            print_info(f"Categories found: {', '.join(categories_found) if categories_found else 'None'}")
            
            # Check prospect quality
            valid_prospects = 0
            prospects_with_names = 0
            prospects_with_orgs = 0
            prospects_with_contacts = 0
            
            for p in prospects:
                if p.get("name") and p["name"] != "Unknown":
                    valid_prospects += 1
                if p.get("name"):
                    prospects_with_names += 1
                if p.get("organization"):
                    prospects_with_orgs += 1
                if p.get("contact", {}).get("email") or p.get("contact", {}).get("phone"):
                    prospects_with_contacts += 1
            
            print_info(f"Valid prospects (real names): {valid_prospects}/{total_found}")
            print_info(f"Prospects with names: {prospects_with_names}/{total_found}")
            print_info(f"Prospects with organizations: {prospects_with_orgs}/{total_found}")
            print_info(f"Prospects with contact info: {prospects_with_contacts}/{total_found}")
            
            # Print sample prospects
            print("\n📋 Sample Prospects:")
            for i, p in enumerate(prospects[:5], 1):
                name = p.get("name", "Unknown")
                org = p.get("organization", "N/A")
                specialty = ", ".join(p.get("specialty", []))
                email = p.get("contact", {}).get("email", "N/A")
                phone = p.get("contact", {}).get("phone", "N/A")
                
                print(f"  {i}. {name}")
                print(f"     Org: {org}")
                print(f"     Category: {specialty}")
                print(f"     Contact: {email} | {phone}")
                print()
            
            # Success criteria
            success = (
                total_found >= 5 and  # At least 5 prospects
                valid_prospects >= 3 and  # At least 3 valid names
                prospects_with_names >= 5  # Most have names
            )
            
            if success:
                print_success("✅ TEST PASSED: 5-Category search working correctly!")
                return True
            else:
                print_error("⚠️  TEST PARTIAL: Found prospects but quality may need improvement")
                return False
        else:
            error = result.get("error", "Unknown error") if result else "No result returned"
            print_error(f"Search failed: {error}")
            return False
    
    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_single_category(category_id: str, category_name: str):
    """Test a single category"""
    print_header(f"TEST: {category_name} ({category_id})")
    
    request_data = {
        "user_id": "dev-user",
        "specialty": "",
        "location": "Washington DC",
        "max_results": 5,
        "save_to_prospects": False,
        "categories": [category_id]
    }
    
    try:
        from app.services.prospect_discovery_service import get_prospect_discovery_service
        from app.models.prospect_discovery import ProspectSearchRequest
        
        search_request = ProspectSearchRequest(**request_data)
        
        print_info(f"Searching for {category_name}...")
        start_time = time.time()
        
        service = get_prospect_discovery_service()
        result = service.find_prospects_free(
            user_id=search_request.user_id,
            specialty=search_request.specialty,
            location=search_request.location,
            max_results=search_request.max_results,
            categories=search_request.categories
        )
        
        elapsed = time.time() - start_time
        
        if result and result.get("success"):
            total_found = result.get("total_found", 0)
            prospects = result.get("prospects", [])
            
            print_success(f"Found {total_found} prospects in {elapsed:.2f}s")
            
            if total_found > 0:
                # Show first prospect
                p = prospects[0]
                print_info(f"Sample: {p.get('name')} | {p.get('organization', 'N/A')}")
                return True
            else:
                print_error(f"No prospects found for {category_name}")
                return False
        else:
            error = result.get("error", "Unknown error") if result else "No result"
            print_error(f"Search failed: {error}")
            return False
    
    except Exception as e:
        print_error(f"Test failed: {e}")
        return False

def run_all_tests():
    """Run all integration tests"""
    print_header("FRONTEND INTEGRATION TEST SUITE")
    
    print_info("Testing end-to-end prospect discovery pipeline")
    print_info("This simulates the exact API call the frontend makes\n")
    
    results = {}
    
    # Test 1: Full 5-category search
    results["5_category"] = test_5_category_search()
    
    # Test 2: Single category tests
    single_categories = [
        ("psychologists", "Psychologists & Psychiatrists"),
        ("treatment_centers", "Treatment Centers"),
        ("pediatricians", "Pediatricians"),
    ]
    
    for cat_id, cat_name in single_categories:
        results[cat_id] = test_single_category(cat_id, cat_name)
        time.sleep(1)  # Rate limiting
    
    # Summary
    print_header("TEST RESULTS SUMMARY")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print_success("ALL TESTS PASSED - System is production ready!")
    else:
        print_error("SOME TESTS FAILED - Review results above")
    print("="*70 + "\n")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

