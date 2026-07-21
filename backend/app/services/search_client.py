"""
Google Custom Search Client

Client for performing Google Custom Search API queries.
"""

import os
import time
from dataclasses import dataclass
from typing import List, Optional
import requests


@dataclass
class SearchResult:
    """Represents a single Google search result."""
    link: str
    title: Optional[str] = None
    snippet: Optional[str] = None


class SearchClientError(Exception):
    """Base exception for search client errors."""
    pass


class SearchConfigurationError(SearchClientError):
    """Raised when search client is not properly configured."""
    pass


class GoogleSearchClient:
    """Client for Google Custom Search API."""
    
    BASE_URL = "https://www.googleapis.com/customsearch/v1"
    
    def __init__(self):
        """Initialize the Google Custom Search client."""
        self.api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
        self.engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
        
        if not self.api_key:
            raise SearchConfigurationError(
                "GOOGLE_CUSTOM_SEARCH_API_KEY environment variable is not set. "
                "Please configure your Google Custom Search API key."
            )
        
        if not self.engine_id:
            raise SearchConfigurationError(
                "GOOGLE_CUSTOM_SEARCH_ENGINE_ID environment variable is not set. "
                "Please configure your Google Custom Search Engine ID."
            )
    
    def search(
        self,
        query: str,
        num_results: int = 10,
        max_retries: int = 3,
        delay_between_retries: float = 1.0
    ) -> List[SearchResult]:
        """
        Perform a Google Custom Search query.
        
        Args:
            query: The search query string
            num_results: Maximum number of results to return (1-100)
            max_retries: Maximum number of retry attempts on failure
            delay_between_retries: Seconds to wait between retries
            
        Returns:
            List of SearchResult objects
            
        Raises:
            SearchClientError: If the search fails after all retries
        """
        # Clamp num_results to valid range (1-100 for Google Custom Search)
        num_results = max(1, min(100, num_results))
        
        results = []
        start_index = 1
        
        # Google Custom Search returns up to 10 results per request
        # So we may need multiple requests to get all results
        while len(results) < num_results:
            # Calculate how many results we need in this batch
            results_needed = num_results - len(results)
            results_per_batch = min(10, results_needed)  # Max 10 per request
            
            for attempt in range(max_retries):
                try:
                    params = {
                        "key": self.api_key,
                        "cx": self.engine_id,
                        "q": query,
                        "num": results_per_batch,
                        "start": start_index,
                    }
                    
                    response = requests.get(
                        self.BASE_URL,
                        params=params,
                        timeout=10
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    # Extract search results
                    items = data.get("items", [])
                    for item in items:
                        results.append(SearchResult(
                            link=item.get("link", ""),
                            title=item.get("title"),
                            snippet=item.get("snippet")
                        ))
                    
                    # Break out of retry loop on success
                    break
                    
                except requests.exceptions.HTTPError as e:
                    error_msg = str(e)
                    
                    # Check for quota/rate limit errors
                    if response.status_code == 429 or "quotaExceeded" in error_msg or "rateLimitExceeded" in error_msg:
                        raise SearchClientError(
                            f"Google Custom Search quota/rate limit exceeded: {error_msg}"
                        )
                    
                    # Check for invalid API key or engine ID
                    if response.status_code == 400:
                        error_data = response.json() if response.content else {}
                        error_info = error_data.get("error", {})
                        if "invalid" in error_msg.lower():
                            raise SearchConfigurationError(
                                f"Invalid Google Custom Search configuration: {error_info.get('message', error_msg)}"
                            )
                    
                    # For other HTTP errors, retry
                    if attempt < max_retries - 1:
                        time.sleep(delay_between_retries * (attempt + 1))
                    else:
                        raise SearchClientError(
                            f"Google Custom Search failed after {max_retries} attempts: {error_msg}"
                        )
                
                except requests.exceptions.RequestException as e:
                    # Network errors - retry
                    if attempt < max_retries - 1:
                        time.sleep(delay_between_retries * (attempt + 1))
                    else:
                        raise SearchClientError(
                            f"Google Custom Search network error after {max_retries} attempts: {str(e)}"
                        )
            
            # Check if we've got all results or if there are no more pages
            if not items or len(items) < results_per_batch:
                break
            
            # Move to next page (Google returns 10 results per page)
            start_index += 10
            
            # Small delay between paginated requests to be respectful
            if len(results) < num_results:
                time.sleep(0.5)
        
        return results[:num_results]


# Singleton instance
_search_client: Optional[GoogleSearchClient] = None


def get_search_client() -> GoogleSearchClient:
    """
    Get or create the singleton Google Search client instance.
    
    Returns:
        GoogleSearchClient instance
        
    Raises:
        SearchConfigurationError: If the client cannot be configured
    """
    global _search_client
    
    if _search_client is None:
        _search_client = GoogleSearchClient()
    
    return _search_client
