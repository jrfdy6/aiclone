"""
Google Custom Search API Client

Provides search capabilities for prospect discovery.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


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
    
    def search(
        self,
        query: str,
        num_results: int = 10,
        start_index: int = 1,
    ) -> List[SearchResult]:
        """
        Search using Google Custom Search API.
        
        Args:
            query: Search query
            num_results: Number of results to return (max 10 per request)
            start_index: Starting index for pagination
            
        Returns:
            List of SearchResult objects
        """
        url = self.BASE_URL
        
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": min(num_results, 10),  # Google limits to 10 per request
            "start": start_index,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
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
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Google Custom Search API request failed: {str(e)}")
    
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


