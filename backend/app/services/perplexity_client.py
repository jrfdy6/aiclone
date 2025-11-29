"""
Perplexity API Client

Client for interacting with Perplexity AI API for research and search.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
import requests


@dataclass
class PerplexityResponse:
    """Response from Perplexity API."""
    answer: Optional[str] = None
    citations: Optional[list] = None
    metadata: Optional[Dict[str, Any]] = None


class PerplexityClientError(Exception):
    """Base exception for Perplexity client errors."""
    pass


class PerplexityConfigurationError(PerplexityClientError):
    """Raised when Perplexity client is not properly configured."""
    pass


class PerplexityClient:
    """Client for Perplexity AI API."""
    
    BASE_URL = "https://api.perplexity.ai/chat/completions"
    
    def __init__(self):
        """Initialize the Perplexity client."""
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        
        if not self.api_key:
            raise PerplexityConfigurationError(
                "PERPLEXITY_API_KEY environment variable is not set. "
                "Please configure your Perplexity API key."
            )
    
    def search(self, query: str, model: str = "llama-3.1-sonar-small-128k-online") -> Optional[PerplexityResponse]:
        """
        Perform a search query using Perplexity.
        
        Args:
            query: The search query string
            model: The Perplexity model to use
            
        Returns:
            PerplexityResponse with answer and citations, or None on error
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 1000,
            }
            
            response = requests.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract answer from response
            answer = None
            if "choices" in data and len(data["choices"]) > 0:
                answer = data["choices"][0].get("message", {}).get("content")
            
            # Extract citations if available
            citations = None
            if "citations" in data:
                citations = data["citations"]
            
            return PerplexityResponse(
                answer=answer,
                citations=citations,
                metadata=data
            )
            
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            
            # Check for authentication errors
            if response.status_code == 401:
                raise PerplexityConfigurationError(
                    f"Invalid Perplexity API key: {error_msg}"
                )
            
            # Check for rate limit errors
            if response.status_code == 429:
                raise PerplexityClientError(
                    f"Perplexity API rate limit exceeded: {error_msg}"
                )
            
            # For other errors, return None (fail gracefully)
            print(f"⚠️ Perplexity API error: {error_msg}", flush=True)
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Perplexity API network error: {str(e)}", flush=True)
            return None
    
    def research_topic(
        self,
        topic: str,
        num_results: int = 5,
        include_comparison: bool = False,
        model: str = "llama-3.1-sonar-large-128k-online"
    ) -> Optional[PerplexityResponse]:
        """
        Research a topic using Perplexity with more comprehensive analysis.
        
        Args:
            topic: The topic to research
            num_results: Number of results to include (affects prompt)
            include_comparison: Whether to include comparative analysis
            model: The Perplexity model to use (larger model for research)
            
        Returns:
            PerplexityResponse with comprehensive research, or None on error
        """
        # Build research query
        query = f"Research and provide comprehensive information about: {topic}"
        
        if include_comparison:
            query += ". Include comparisons with similar topics or alternatives."
        
        query += f" Provide detailed insights, key points, and relevant information."
        
        return self.search(query=query, model=model)


# Singleton instance
_perplexity_client: Optional[PerplexityClient] = None


def get_perplexity_client() -> Optional[PerplexityClient]:
    """
    Get or create the singleton Perplexity client instance.
    
    Returns:
        PerplexityClient instance, or None if not configured (graceful degradation)
    """
    global _perplexity_client
    
    if _perplexity_client is None:
        try:
            _perplexity_client = PerplexityClient()
        except PerplexityConfigurationError as e:
            # Fail gracefully - return None if not configured
            print(f"⚠️ Perplexity client not available: {e}", flush=True)
            return None
    
    return _perplexity_client
