#!/usr/bin/env python3
"""
Clear all prospects from the pipeline via API.
"""
import requests
import sys
import os

# Get API URL from environment or use default
API_URL = os.environ.get('API_URL', 'https://aiclone-production-32dc.up.railway.app')
USER_ID = 'dev-user'  # Default user ID

def clear_all_prospects():
    """Clear all prospects for the user"""
    url = f"{API_URL}/api/prospects/clear-all"
    params = {"user_id": USER_ID}
    
    try:
        print(f"Calling: {url}?user_id={USER_ID}")
        response = requests.delete(url, params=params, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Success! Deleted {result.get('deleted', 0)} prospects")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        USER_ID = sys.argv[1]
    
    success = clear_all_prospects()
    sys.exit(0 if success else 1)

