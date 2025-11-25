#!/usr/bin/env python3
"""
Test script to monitor LinkedIn scraping success rates.

This script helps you:
1. Test different search queries
2. Monitor which scraping approaches work best
3. Track success rates over time
4. Identify patterns in successful vs failed scrapes

Usage:
    python test_scraping_success.py --query "AI tools" --max-results 5
    python test_scraping_success.py --query "machine learning" --max-results 10 --iterations 3
"""

import argparse
import json
import sys
import time
from typing import Dict, List, Any
import requests

def test_scraping(
    api_url: str,
    query: str,
    max_results: int = 5,
    iterations: int = 1
) -> Dict[str, Any]:
    """Test LinkedIn scraping and return detailed metrics."""
    
    endpoint = f"{api_url}/api/linkedin/test"
    
    all_results = []
    all_stats = []
    
    print(f"\n{'='*60}")
    print(f"Testing LinkedIn Scraping")
    print(f"{'='*60}")
    print(f"Query: {query}")
    print(f"Max Results: {max_results}")
    print(f"Iterations: {iterations}")
    print(f"API URL: {api_url}")
    print(f"{'='*60}\n")
    
    for i in range(iterations):
        print(f"\n--- Iteration {i+1}/{iterations} ---")
        
        try:
            payload = {
                "query": query,
                "max_results": max_results
            }
            
            print(f"  Sending request to {endpoint}...")
            start_time = time.time()
            
            response = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300  # 5 minute timeout for scraping
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                print(f"  ❌ Error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                continue
            
            data = response.json()
            
            if not data.get("success"):
                print(f"  ❌ Request failed: {data.get('error', 'Unknown error')}")
                continue
            
            posts = data.get("posts", [])
            test_metadata = data.get("test_metadata", {})
            scraping_perf = data.get("scraping_performance", {})
            
            print(f"  ✅ Request completed in {elapsed:.1f}s")
            print(f"  Posts found: {len(posts)}")
            
            # Extract stats
            extraction_quality = test_metadata.get("extraction_quality", {})
            scraping_stats = scraping_perf.get("scraping_stats", {}) if isinstance(scraping_perf, dict) else {}
            
            print(f"\n  Extraction Quality:")
            print(f"    - Author extraction: {extraction_quality.get('author_extraction_rate', 0)}%")
            print(f"    - Engagement extraction: {extraction_quality.get('engagement_extraction_rate', 0)}%")
            print(f"    - Company extraction: {extraction_quality.get('company_extraction_rate', 0)}%")
            
            if scraping_stats:
                total_attempts = scraping_stats.get("total_attempts", 0)
                successful = scraping_stats.get("approach_1_success", 0) + \
                            scraping_stats.get("approach_2_success", 0) + \
                            scraping_stats.get("approach_3_success", 0) + \
                            scraping_stats.get("approach_4_success", 0)
                
                print(f"\n  Scraping Performance:")
                print(f"    - Total attempts: {total_attempts}")
                print(f"    - Successful scrapes: {successful}")
                print(f"    - Success rate: {scraping_perf.get('success_rate', 0)}%")
                print(f"    - Approach 1 success: {scraping_stats.get('approach_1_success', 0)}")
                print(f"    - Approach 2 success: {scraping_stats.get('approach_2_success', 0)}")
                print(f"    - Approach 3 success: {scraping_stats.get('approach_3_success', 0)}")
                print(f"    - Approach 4 success: {scraping_stats.get('approach_4_success', 0)}")
                print(f"    - Content too short: {scraping_stats.get('content_too_short', 0)}")
                print(f"    - No LinkedIn indicators: {scraping_stats.get('no_linkedin_indicators', 0)}")
            
            all_results.append({
                "iteration": i + 1,
                "elapsed_seconds": round(elapsed, 2),
                "posts_found": len(posts),
                "extraction_quality": extraction_quality,
                "scraping_performance": scraping_perf,
                "sample_posts": [
                    {
                        "url": p.get("url", ""),
                        "author": p.get("author", "Unknown"),
                        "content_length": p.get("content_length", 0),
                        "engagement_score": p.get("engagement_score"),
                        "has_content": bool(p.get("content") and len(p.get("content", "")) > 100)
                    }
                    for p in posts[:3]  # Sample first 3 posts
                ]
            })
            
            all_stats.append({
                "iteration": i + 1,
                "scraping_stats": scraping_stats,
                "extraction_quality": extraction_quality
            })
            
            # Wait between iterations (except last one)
            if i < iterations - 1:
                wait_time = 5
                print(f"\n  Waiting {wait_time}s before next iteration...")
                time.sleep(wait_time)
        
        except requests.exceptions.Timeout:
            print(f"  ❌ Request timed out after 5 minutes")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Calculate aggregate statistics
    if all_stats:
        print(f"\n{'='*60}")
        print(f"Summary Statistics")
        print(f"{'='*60}")
        
        # Aggregate scraping stats
        total_attempts = sum(s["scraping_stats"].get("total_attempts", 0) for s in all_stats)
        approach_1_total = sum(s["scraping_stats"].get("approach_1_success", 0) for s in all_stats)
        approach_2_total = sum(s["scraping_stats"].get("approach_2_success", 0) for s in all_stats)
        approach_3_total = sum(s["scraping_stats"].get("approach_3_success", 0) for s in all_stats)
        approach_4_total = sum(s["scraping_stats"].get("approach_4_success", 0) for s in all_stats)
        
        if total_attempts > 0:
            print(f"\nOverall Scraping Success Rates:")
            print(f"  Total attempts: {total_attempts}")
            print(f"  Approach 1 (v2 + auto): {approach_1_total} ({approach_1_total/total_attempts*100:.1f}%)")
            print(f"  Approach 2 (scroll): {approach_2_total} ({approach_2_total/total_attempts*100:.1f}%)")
            print(f"  Approach 3 (stealth): {approach_3_total} ({approach_3_total/total_attempts*100:.1f}%)")
            print(f"  Approach 4 (v1 fallback): {approach_4_total} ({approach_4_total/total_attempts*100:.1f}%)")
        
        # Average extraction quality
        avg_author_rate = sum(s["extraction_quality"].get("author_extraction_rate", 0) for s in all_stats) / len(all_stats)
        avg_engagement_rate = sum(s["extraction_quality"].get("engagement_extraction_rate", 0) for s in all_stats) / len(all_stats)
        
        print(f"\nAverage Extraction Quality:")
        print(f"  Author extraction: {avg_author_rate:.1f}%")
        print(f"  Engagement extraction: {avg_engagement_rate:.1f}%")
        
        avg_posts = sum(r["posts_found"] for r in all_results) / len(all_results)
        avg_time = sum(r["elapsed_seconds"] for r in all_results) / len(all_results)
        
        print(f"\nPerformance:")
        print(f"  Average posts per request: {avg_posts:.1f}")
        print(f"  Average time per request: {avg_time:.1f}s")
    
    return {
        "query": query,
        "max_results": max_results,
        "iterations": iterations,
        "results": all_results,
        "summary": {
            "total_iterations": len(all_results),
            "average_posts": round(sum(r["posts_found"] for r in all_results) / len(all_results), 1) if all_results else 0,
            "average_time": round(sum(r["elapsed_seconds"] for r in all_results) / len(all_results), 1) if all_results else 0,
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Test LinkedIn scraping success rates")
    parser.add_argument(
        "--query",
        type=str,
        default="AI tools",
        help="Search query to test (default: 'AI tools')"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of results to fetch (default: 5)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of test iterations to run (default: 1)"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8080",
        help="API base URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file to save results as JSON (optional)"
    )
    
    args = parser.parse_args()
    
    # Remove trailing slash from API URL
    api_url = args.api_url.rstrip("/")
    
    try:
        results = test_scraping(
            api_url=api_url,
            query=args.query,
            max_results=args.max_results,
            iterations=args.iterations
        )
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\n✅ Results saved to {args.output}")
        
        print(f"\n{'='*60}")
        print(f"Test Complete!")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

