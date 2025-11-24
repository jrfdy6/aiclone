"""
Google Custom Search API Client

Provides search capabilities for prospect discovery.
Implements best practices: exponential backoff, error handling, quota management.
"""

import os
import time
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class SearchResult:
    """Result from Google Custom Search"""
    title: str
    link: str
    snippet: str
    display_link: str


class GoogleCustomSearchClient:
    """Client for interacting with Google Custom Search API."""
    
    BASE_URL = "https://www.googleapis.com/customsearch/v1"
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
        
        if not self.api_key:
            raise ValueError(
                "GOOGLE_CUSTOM_SEARCH_API_KEY environment variable not set. "
                "Get your API key from https://console.cloud.google.com/apis/credentials"
            )
        if not self.search_engine_id:
            raise ValueError(
                "GOOGLE_CUSTOM_SEARCH_ENGINE_ID environment variable not set. "
                "Create a Custom Search Engine at https://programmablesearchengine.google.com/"
            )
        
        self.session = requests.Session()
        # Enable gzip compression for better performance
        self.session.headers.update({
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "aiclone-backend/1.0"
        })
    
    def _handle_rate_limit_error(self, response_data: Dict, attempt: int, max_attempts: int = 3) -> bool:
        """
        Handle rate limit and quota errors with exponential backoff.
        
        Returns:
            True if should retry, False otherwise
        """
        error = response_data.get("error", {})
        error_code = error.get("code")
        error_message = error.get("message", "")
        
        # Rate limit errors that can be retried
        retryable_errors = [
            "userRateLimitExceeded",
            "rateLimitExceeded",
            "quotaExceeded",
            "backendError",
            "internalError"
        ]
        
        if error_code == 429 or any(err in error_message for err in retryable_errors):
            if attempt < max_attempts:
                # Exponential backoff: 2^attempt seconds
                wait_time = 2 ** attempt
                print(f"  [Search] Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_attempts}...", flush=True)
                time.sleep(wait_time)
                return True
            else:
                print(f"  [Search] Max retries reached for rate limit error", flush=True)
                return False
        
        # Quota exceeded - don't retry
        if error_code == 403 and "quotaExceeded" in error_message:
            print(f"  [Search] Daily quota exceeded (100 free queries/day). Enable billing or wait 24h.", flush=True)
            return False
        
        return False
    
    def search(
        self,
        query: str,
        num_results: int = 10,
        start_index: int = 1,
        max_retries: int = 3,
    ) -> List[SearchResult]:
        """
        Search using Google Custom Search API with retry logic and error handling.
        
        Args:
            query: Search query
            num_results: Number of results to return (max 10 per request)
            start_index: Starting index for pagination
            max_retries: Maximum number of retry attempts for rate-limited requests
            
        Returns:
            List of SearchResult objects
            
        Raises:
            Exception: If API request fails after all retries
        """
        url = self.BASE_URL
        
        # Optimize query - ensure it's properly formatted
        optimized_query = query.strip()
        
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": optimized_query,
            "num": min(num_results, 10),  # Google limits to 10 per request
            "start": start_index,
            # Request only fields we need (best practice)
            "fields": "items(title,link,snippet,displayLink)",
        }
        
        attempt = 0
        while attempt < max_retries:
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                # Handle HTTP errors
                if response.status_code == 429:
                    # Rate limited
                    try:
                        error_data = response.json()
                        if self._handle_rate_limit_error(error_data, attempt, max_retries):
                            attempt += 1
                            continue
                    except:
                        pass
                    raise Exception(f"Rate limit exceeded (HTTP 429). Please slow down requests.")
                
                if response.status_code == 403:
                    # Check if it's a quota error
                    try:
                        error_data = response.json()
                        error = error_data.get("error", {})
                        error_message = error.get("message", "")
                        
                        if "quotaExceeded" in error_message or "userRateLimitExceeded" in error_message:
                            if attempt < max_retries:
                                if self._handle_rate_limit_error(error_data, attempt, max_retries):
                                    attempt += 1
                                    continue
                        
                        # Other 403 errors
                        raise Exception(f"Access forbidden (HTTP 403): {error_message}. Check API key permissions.")
                    except json.JSONDecodeError:
                        raise Exception(f"Access forbidden (HTTP 403). Check API key permissions and restrictions.")
                
                response.raise_for_status()
                data = response.json()
                
                # Check for API-level errors in response
                if "error" in data:
                    error_data = data["error"]
                    error_code = error_data.get("code")
                    error_message = error_data.get("message", "")
                    
                    # Try to handle rate limit errors
                    if self._handle_rate_limit_error(data, attempt, max_retries):
                        attempt += 1
                        continue
                    
                    raise Exception(f"Google Custom Search API error ({error_code}): {error_message}")
                
                # Parse results
                results = []
                items = data.get("items", [])
                
                for item in items:
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        link=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        display_link=item.get("displayLink", "")
                    ))
                
                return results
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"  [Search] Request timeout, retrying ({attempt + 1}/{max_retries})...", flush=True)
                    attempt += 1
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise Exception(f"Request timeout after {max_retries} attempts")
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1 and "429" in str(e) or "503" in str(e):
                    print(f"  [Search] Transient error, retrying ({attempt + 1}/{max_retries})...", flush=True)
                    attempt += 1
                    time.sleep(2 ** attempt)
                    continue
                raise Exception(f"Google Custom Search API request failed: {str(e)}")
            
            attempt += 1
        
        raise Exception(f"Search failed after {max_retries} attempts")
    
    def search_companies(
        self,
        industry: Optional[str] = None,
        location: Optional[str] = None,
        company_name: Optional[str] = None,
        max_results: int = 50,
    ) -> List[SearchResult]:
        """
        Search for companies based on criteria.
        
        Args:
            industry: Industry filter
            location: Location filter
            company_name: Specific company name
            max_results: Maximum results to return
            
        Returns:
            List of SearchResult objects
        """
        # Build search query
        query_parts = []
        
        if company_name:
            query_parts.append(f'"{company_name}"')
        else:
            query_parts.append("companies")
        
        if industry:
            query_parts.append(industry)
        
        if location:
            query_parts.append(location)
        
        query_parts.append("team about contact")
        
        query = " ".join(query_parts)
        
        # Google Custom Search allows up to 100 results total
        # We need to paginate if max_results > 10
        all_results = []
        start_index = 1
        
        while len(all_results) < max_results and start_index <= 91:  # Max 100 results
            batch_size = min(10, max_results - len(all_results))
            
            try:
                results = self.search(query, num_results=batch_size, start_index=start_index)
                all_results.extend(results)
                
                if len(results) < 10:  # No more results
                    break
                
                start_index += 10
                
            except Exception as e:
                print(f"Error fetching batch starting at {start_index}: {e}", flush=True)
                break
        
        return all_results[:max_results]


# Singleton instance
_search_client: Optional[GoogleCustomSearchClient] = None


def get_search_client() -> GoogleCustomSearchClient:
    """Get or create Google Custom Search client instance."""
    global _search_client
    if _search_client is None:
        _search_client = GoogleCustomSearchClient()
    return _search_client



