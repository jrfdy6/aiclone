#!/usr/bin/env python3
"""
Test all relevant queries from README goals until we achieve 20-25% success rate.
"""

import subprocess
import json
import time
from typing import Dict, List

# Relevant queries based on README goals - COMPREHENSIVE LIST
# From README: Goals, Audience, Content Strategy, and Unique Differentiation
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

def test_query(query: str) -> Dict:
    """Test a single query and return results."""
    print(f"\n{'='*60}")
    print(f"Testing: {query}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [
                "python3", "test_scraping_success.py",
                "--query", query,
                "--max-results", "3",
                "--api-url", API_URL,
                "--iterations", "1"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Parse output to extract success rate
        output = result.stdout
        success_rate = None
        
        for line in output.split('\n'):
            if "Success rate:" in line:
                try:
                    # Extract percentage
                    parts = line.split("Success rate:")
                    if len(parts) > 1:
                        rate_str = parts[1].strip().split('%')[0]
                        success_rate = float(rate_str)
                except:
                    pass
        
        return {
            "query": query,
            "success_rate": success_rate,
            "output": output,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "query": query,
            "success_rate": None,
            "output": "Timeout",
            "success": False
        }
    except Exception as e:
        return {
            "query": query,
            "success_rate": None,
            "output": str(e),
            "success": False
        }

def main():
    results = []
    target_rate = 20.0  # Target 20-25%
    
    print(f"\n{'='*60}")
    print(f"Testing {len(RELEVANT_QUERIES)} relevant queries")
    print(f"Target success rate: {target_rate}%")
    print(f"{'='*60}\n")
    
    for query in RELEVANT_QUERIES:
        result = test_query(query)
        results.append(result)
        
        if result["success_rate"] is not None:
            status = "✅" if result["success_rate"] >= target_rate else "❌"
            print(f"{status} {query}: {result['success_rate']}%")
        else:
            print(f"⚠️  {query}: No data")
        
        # Wait between queries to avoid rate limiting
        time.sleep(5)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    successful_queries = [r for r in results if r["success_rate"] and r["success_rate"] >= target_rate]
    failed_queries = [r for r in results if not r["success_rate"] or r["success_rate"] < target_rate]
    
    print(f"\n✅ Queries meeting {target_rate}% target: {len(successful_queries)}/{len(results)}")
    for r in successful_queries:
        print(f"   - {r['query']}: {r['success_rate']}%")
    
    print(f"\n❌ Queries below {target_rate}% target: {len(failed_queries)}/{len(results)}")
    for r in failed_queries:
        if r["success_rate"] is not None:
            print(f"   - {r['query']}: {r['success_rate']}%")
        else:
            print(f"   - {r['query']}: No data")
    
    # Save results
    with open("query_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Results saved to query_test_results.json")
    print(f"\n🎯 Goal: {len(successful_queries)}/{len(results)} queries at {target_rate}%+ success rate")

if __name__ == "__main__":
    main()

