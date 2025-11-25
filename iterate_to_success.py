#!/usr/bin/env python3
"""
Iteratively test and optimize until we achieve 20-25% success rate for all relevant queries.
"""

import subprocess
import json
import time
from typing import Dict, List

RELEVANT_QUERIES = [
    "enrollment management K-12",
    "admissions private school",
    "neurodivergent students education",
    "AI in education",
    "EdTech tools",
    "education technology",
    "K-12 admissions",
    "post-secondary enrollment",
    "fashion tech app",
    "entrepreneurship education",
    "referral networks education",
    "one-to-one care model",
    "AI tools education",
    "content marketing education",
    "LinkedIn optimization education"
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
            timeout=180  # 3 minute timeout
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
        return {"query": query, "success_rate": None, "success": False, "has_data": False}
    except Exception as e:
        return {"query": query, "success_rate": None, "success": False, "has_data": False, "error": str(e)}

def main():
    print(f"\n{'='*70}")
    print(f"ITERATIVE OPTIMIZATION: Target {TARGET_RATE}% success rate")
    print(f"{'='*70}\n")
    
    iteration = 1
    all_results = []
    
    while True:
        print(f"\n{'='*70}")
        print(f"ITERATION {iteration}")
        print(f"{'='*70}\n")
        
        iteration_results = []
        
        for query in RELEVANT_QUERIES:
            print(f"Testing: {query}...", end=" ", flush=True)
            result = test_query(query)
            iteration_results.append(result)
            
            if result["has_data"]:
                status = "✅" if result["success_rate"] >= TARGET_RATE else "❌"
                print(f"{status} {result['success_rate']}%")
            else:
                print("⚠️  No data/timeout")
            
            time.sleep(3)  # Small delay between queries
        
        all_results.append({
            "iteration": iteration,
            "results": iteration_results
        })
        
        # Calculate summary
        successful = [r for r in iteration_results if r["has_data"] and r["success_rate"] >= TARGET_RATE]
        total_with_data = [r for r in iteration_results if r["has_data"]]
        
        print(f"\n📊 Iteration {iteration} Summary:")
        print(f"   Queries meeting {TARGET_RATE}% target: {len(successful)}/{len(total_with_data)}")
        
        if len(total_with_data) > 0:
            avg_rate = sum(r["success_rate"] for r in total_with_data) / len(total_with_data)
            print(f"   Average success rate: {avg_rate:.1f}%")
        
        # Check if we've achieved goal
        if len(total_with_data) == len(RELEVANT_QUERIES) and len(successful) == len(RELEVANT_QUERIES):
            print(f"\n🎉 SUCCESS! All queries achieved {TARGET_RATE}%+ success rate!")
            break
        
        # Save progress
        with open(f"iteration_{iteration}_results.json", "w") as f:
            json.dump(all_results, f, indent=2)
        
        print(f"\n⏳ Waiting 30s before next iteration...")
        time.sleep(30)
        iteration += 1
        
        if iteration > 10:  # Safety limit
            print(f"\n⚠️  Reached 10 iterations. Stopping.")
            break
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}\n")
    
    final_results = all_results[-1]["results"]
    successful_final = [r for r in final_results if r["has_data"] and r["success_rate"] >= TARGET_RATE]
    
    print(f"✅ Queries meeting target: {len(successful_final)}/{len([r for r in final_results if r['has_data']])}")
    print(f"\nSuccessful queries:")
    for r in successful_final:
        print(f"   - {r['query']}: {r['success_rate']}%")
    
    print(f"\n❌ Queries below target:")
    for r in final_results:
        if r["has_data"] and r["success_rate"] < TARGET_RATE:
            print(f"   - {r['query']}: {r['success_rate']}%")
        elif not r["has_data"]:
            print(f"   - {r['query']}: No data/timeout")

if __name__ == "__main__":
    main()

