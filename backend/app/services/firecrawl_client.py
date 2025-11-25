"""
Firecrawl API Client

Provides web scraping and crawling capabilities using Firecrawl API.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time


@dataclass
class ScrapedContent:
    """Scraped content from a URL."""
    url: str
    title: str
    content: str
    markdown: Optional[str] = None
    links: List[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class SiteMapResult:
    """Site map crawl result."""
    urls: List[str]
    total_pages: int


class FirecrawlClient:
    """Client for interacting with Firecrawl API."""
    
    BASE_URL = "https://api.firecrawl.dev"
    
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY environment variable not set. "
                "Get your API key from https://firecrawl.dev"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def scrape_url(
        self,
        url: str,
        formats: List[str] = None,
        include_tags: List[str] = None,
        exclude_tags: List[str] = None,
        only_main_content: bool = True,
        wait_for: Optional[int] = None,
        use_v2: bool = True,
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> ScrapedContent:
        """
        Scrape a single URL with enhanced options for difficult sites like LinkedIn.
        
        Args:
            url: URL to scrape
            formats: Output formats (e.g., ['markdown', 'html'])
            include_tags: HTML tags to include
            exclude_tags: HTML tags to exclude
            only_main_content: Filter to main content only
            wait_for: Milliseconds to wait for JavaScript
            use_v2: Use Firecrawl v2 API (better anti-bot features)
            actions: List of browser actions (click, scroll, wait, etc.)
            
        Returns:
            ScrapedContent with content and metadata
        """
        if formats is None:
            formats = ["markdown", "html"]
        
        # Use v2 API for better anti-bot features (default)
        endpoint = f"{self.BASE_URL}/v2/scrape" if use_v2 else f"{self.BASE_URL}/v1/scrape"
        
        payload = {
            "url": url,
            "formats": formats,
            "onlyMainContent": only_main_content,
        }
        
        if include_tags:
            payload["includeTags"] = include_tags
        if exclude_tags:
            payload["excludeTags"] = exclude_tags
        if wait_for:
            payload["waitFor"] = wait_for
        if actions:
            payload["actions"] = actions
        
        try:
            response = self.session.post(endpoint, json=payload, timeout=60)
            
            # Handle specific HTTP status codes
            if response.status_code == 403:
                error_detail = response.text
                # Try to get more details from response
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", error_detail)
                except:
                    error_message = error_detail
                
                raise Exception(
                    f"Firecrawl API returned 403 Forbidden for {url}. "
                    f"This may indicate: API key restrictions, rate limiting, or LinkedIn blocking. "
                    f"Details: {error_message[:200]}"
                )
            
            if response.status_code == 429:
                raise Exception(
                    f"Firecrawl API rate limit exceeded for {url}. "
                    f"Please wait before retrying."
                )
            
            response.raise_for_status()
            data = response.json()
            
            result = data.get("data", {})
            
            return ScrapedContent(
                url=url,
                title=result.get("title", ""),
                content=result.get("markdown", result.get("html", "")),
                markdown=result.get("markdown"),
                links=result.get("links", []),
                metadata={
                    "description": result.get("description"),
                    "language": result.get("language"),
                    "author": result.get("author"),
                }
            )
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 403:
                error_detail = e.response.text[:200] if e.response.text else "No details"
                raise Exception(
                    f"Firecrawl API 403 Forbidden for {url}. "
                    f"Possible causes: Invalid API key, expired key, rate limit, or LinkedIn blocking. "
                    f"Details: {error_detail}"
                )
            raise Exception(f"Firecrawl scrape failed for {url}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Firecrawl scrape failed for {url}: {str(e)}")
    
    def crawl_url(
        self,
        url: str,
        max_depth: int = 2,
        max_pages: int = 10,
        limit: int = 10,
        include_paths: List[str] = None,
        exclude_paths: List[str] = None,
    ) -> List[ScrapedContent]:
        """
        Crawl a website starting from a URL.
        
        Args:
            url: Starting URL
            max_depth: Maximum crawl depth
            max_pages: Maximum pages to crawl
            limit: Limit number of pages per depth level
            include_paths: Paths to include (e.g., ['/guides', '/blog'])
            exclude_paths: Paths to exclude (e.g., ['/admin', '/api'])
            
        Returns:
            List of ScrapedContent objects
        """
        endpoint = f"{self.BASE_URL}/v1/crawl"
        
        payload = {
            "url": url,
            "crawlerOptions": {
                "maxDepth": max_depth,
                "limit": limit,
            },
            "pageOptions": {
                "onlyMainContent": True,
            }
        }
        
        if include_paths:
            payload["crawlerOptions"]["includePaths"] = include_paths
        if exclude_paths:
            payload["crawlerOptions"]["excludePaths"] = exclude_paths
        
        try:
            # Start crawl job
            response = self.session.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()
            job_data = response.json()
            
            job_id = job_data.get("jobId")
            if not job_id:
                raise Exception("No jobId returned from Firecrawl")
            
            # Poll for completion
            max_attempts = 60  # 5 minutes max
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)  # Wait 5 seconds between checks
                status_response = self.session.get(
                    f"{self.BASE_URL}/v1/crawl/status/{job_id}",
                    timeout=30
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                
                status = status_data.get("status")
                
                if status == "completed":
                    # Get results
                    results_data = status_data.get("data", [])
                    scraped_content = []
                    
                    for page_data in results_data[:max_pages]:
                        scraped_content.append(ScrapedContent(
                            url=page_data.get("url", ""),
                            title=page_data.get("title", ""),
                            content=page_data.get("markdown", page_data.get("html", "")),
                            markdown=page_data.get("markdown"),
                            links=page_data.get("links", []),
                            metadata=page_data.get("metadata", {})
                        ))
                    
                    return scraped_content
                
                elif status == "failed":
                    error = status_data.get("error", "Unknown error")
                    raise Exception(f"Firecrawl crawl failed: {error}")
                
                attempt += 1
            
            raise Exception("Firecrawl crawl timed out")
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Firecrawl crawl request failed: {str(e)}")
    
    def build_sitemap(
        self,
        url: str,
        max_pages: int = 50,
        include_paths: List[str] = None,
    ) -> SiteMapResult:
        """
        Build a sitemap by crawling a website.
        
        Args:
            url: Base URL
            max_pages: Maximum pages to discover
            include_paths: Paths to include (e.g., ['/guides', '/blog'])
            
        Returns:
            SiteMapResult with list of URLs
        """
        scraped = self.crawl_url(
            url=url,
            max_depth=3,
            max_pages=max_pages,
            limit=max_pages,
            include_paths=include_paths,
        )
        
        urls = [content.url for content in scraped]
        
        return SiteMapResult(
            urls=urls,
            total_pages=len(urls)
        )
    
    def scrape_multiple_urls(
        self,
        urls: List[str],
        max_concurrent: int = 5,
    ) -> List[ScrapedContent]:
        """
        Scrape multiple URLs (with rate limiting).
        
        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of ScrapedContent objects
        """
        results = []
        
        # Process in batches to avoid rate limits
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i:i + max_concurrent]
            
            for url in batch:
                try:
                    content = self.scrape_url(url)
                    results.append(content)
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    print(f"Failed to scrape {url}: {e}", flush=True)
                    continue
        
        return results


# Singleton instance
_firecrawl_client: Optional[FirecrawlClient] = None


def get_firecrawl_client() -> FirecrawlClient:
    """Get or create Firecrawl client instance."""
    global _firecrawl_client
    if _firecrawl_client is None:
        _firecrawl_client = FirecrawlClient()
    return _firecrawl_client



