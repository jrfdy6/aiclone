"""
Debug: Check if team page scraping works
"""
import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService

service = ProspectDiscoveryService()
base_url = "https://www.newportacademy.com"

# Test scraping team page directly
team_url = f"{base_url}/meet-the-team/"
print(f"Scraping: {team_url}")

team_content = service._free_scrape(team_url)
print(f"Content length: {len(team_content) if team_content else 0}")

if team_content:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(team_content, 'html.parser')
    
    print(f"\n✅ Team page scraped successfully!")
    
    # Look for entry-title headings
    headings = soup.find_all(['h2', 'h3', 'h4'], class_=re.compile(r'entry-title', re.I))
    print(f"\nFound {len(headings)} entry-title headings:")
    for h in headings[:5]:
        print(f"  - {h.get_text(strip=True)}")
    
    # Look for position fields
    positions = soup.find_all(['p', 'div', 'span'], class_=re.compile(r'position|team_member_position', re.I))
    print(f"\nFound {len(positions)} position fields:")
    for p in positions[:5]:
        text = p.get_text(strip=True)
        if text and len(text) > 3:
            print(f"  - {text[:80]}")

