#!/usr/bin/env python3
"""
Test all 34 relevant queries from README goals until we achieve 20-25% success rate for ALL.
"""

import subprocess
import json
import time
from typing import Dict, List

# All 34 relevant queries from README
RELEVANT_QUERIES = [
    # Enrollment Management & Admissions (Core Role - Goal 1)
    "enrollment management K-12",
    "K-12 admissions",
    "admissions private school",
    "post-secondary enrollment",
    "enrollment management education",
    
    # Neurodivergent Students & One-to-One Care (Core Focus)
    "neurodivergent students education",
    "one-to-one care model",
    "neurodivergent support education",
    "private school neurodivergent",
    
    # AI in Education & EdTech (Positioning Goal 2)
    "AI in education",
    "EdTech tools",
    "education technology",
    "AI tools education",
    "AI EdTech",
    "artificial intelligence education",
    
    # Referral Networks (Relationship Building - Half of Work)
    "referral networks education",
    "private school referral networks",
    "mental health professionals education",
    "treatment center administrators",
    
    # Fashion Tech App (Goal 3)
    "fashion tech app",
    "fashion app development",
    "closet organization app",
    "outfit coordination app",
    
    # Entrepreneurship & Operations (Long-term Goal)
    "entrepreneurship education",
    "operations education",
    "program management education",
    "scalable solutions education",
    
    # Content Marketing & LinkedIn (Current Challenge)
    "content marketing education",
    "LinkedIn optimization education",
    "LinkedIn content strategy",
    "personal branding education",
    
    # Bridge Building (Unique Differentiation)
    "education technology operations",
    "AI operations education",
    "tech builder education"
]

API_URL = "https://aiclone-production-32dc.up.railway.app"
TARGET_RATE = 20.0

def test_query(query: str) -> Dict:
    """Test a single query and return success rate."""
    try:
        result = subprocess.run(
            ["python3", "test_scraping_success.py",
             "--query", query,
             "--max-results", "3",
             "--api-url", API_URL,
             "--iterations", "1"],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        output = result.stdout
        success_rate = None
        
        for line in output.split('\n'):
            if "Success rate:" in line:
                try:
                    rate_str = line.split("Success rate:")[1].strip().split('%')[0]
                    success_rate = float(rate_str)
                except:
                    pass
        
        return {
            "query": query,
            "success_rate": success_rate,
            "success": result.returncode == 0,
            "has_data": success_rate is not None
        }
    except subprocess.TimeoutExpired:
        return {"query": query, "success_rate": None, "success": False, "has_data": False, "error": "timeout"}
    except Exception as e:
        return {"query": query, "success_rate": None, "success": False, "has_data": False, "error": str(e)}

def main():
    print(f"\n{'='*70}")
    print(f"TESTING ALL 34 RELEVANT QUERIES")
    print(f"Target: {TARGET_RATE}% success rate for ALL queries")
    print(f"{'='*70}\n")
    
    results = []
    successful_queries = []
    failed_queries = []
    
    for i, query in enumerate(RELEVANT_QUERIES, 1):
        print(f"[{i}/{len(RELEVANT_QUERIES)}] Testing: {query}...", end=" ", flush=True)
        result = test_query(query)
        results.append(result)
        
        if result["has_data"]:
            if result["success_rate"] >= TARGET_RATE:
                print(f"✅ {result['success_rate']}%")
                successful_queries.append(result)
            else:
                print(f"❌ {result['success_rate']}%")
                failed_queries.append(result)
        else:
            print("⚠️  No data/timeout")
            failed_queries.append(result)
        
        # Small delay between queries
        if i < len(RELEVANT_QUERIES):
            time.sleep(3)
    
    # Summary
    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print(f"{'='*70}\n")
    
    total_with_data = [r for r in results if r["has_data"]]
    
    print(f"✅ Queries meeting {TARGET_RATE}% target: {len(successful_queries)}/{len(total_with_data)}")
    if successful_queries:
        print("\nSuccessful queries:")
        for r in successful_queries:
            print(f"   - {r['query']}: {r['success_rate']}%")
    
    print(f"\n❌ Queries below {TARGET_RATE}% target: {len(failed_queries)}/{len(RELEVANT_QUERIES)}")
    if failed_queries:
        print("\nFailed queries:")
        for r in failed_queries:
            if r["has_data"]:
                print(f"   - {r['query']}: {r['success_rate']}%")
            else:
                print(f"   - {r['query']}: No data ({r.get('error', 'unknown')})")
    
    if len(total_with_data) > 0:
        avg_rate = sum(r["success_rate"] for r in total_with_data) / len(total_with_data)
        print(f"\n📊 Average success rate: {avg_rate:.1f}%")
    
    # Save results
    with open("all_34_queries_results.json", "w") as f:
        json.dump({
            "total_queries": len(RELEVANT_QUERIES),
            "queries_with_data": len(total_with_data),
            "successful_queries": len(successful_queries),
            "failed_queries": len(failed_queries),
            "target_rate": TARGET_RATE,
            "results": results,
            "summary": {
                "average_success_rate": round(avg_rate, 1) if total_with_data else 0,
                "meeting_target": len(successful_queries),
                "below_target": len(failed_queries)
            }
        }, f, indent=2)
    
    print(f"\n📊 Results saved to all_34_queries_results.json")
    
    # Goal check
    if len(successful_queries) == len(RELEVANT_QUERIES):
        print(f"\n🎉 SUCCESS! All {len(RELEVANT_QUERIES)} queries achieved {TARGET_RATE}%+ success rate!")
    else:
        print(f"\n⚠️  Goal not yet achieved: {len(successful_queries)}/{len(RELEVANT_QUERIES)} queries at {TARGET_RATE}%+")
        print(f"   Need to optimize {len(failed_queries)} more queries")

if __name__ == "__main__":
    main()

