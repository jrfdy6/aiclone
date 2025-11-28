"""
Debug: Check actual HTML structure
"""
import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.prospect_discovery_service import ProspectDiscoveryService
from bs4 import BeautifulSoup

service = ProspectDiscoveryService()
team_url = "https://www.newportacademy.com/meet-the-team/"

content = service._free_scrape(team_url)
print(f"Content length: {len(content)} chars\n")

if content:
    soup = BeautifulSoup(content, 'html.parser')
    
    # Check all h2, h3, h4 tags
    all_headings = soup.find_all(['h2', 'h3', 'h4'])
    print(f"Total h2/h3/h4 tags: {len(all_headings)}\n")
    
    for i, h in enumerate(all_headings[:10], 1):
        classes = h.get('class', [])
        text = h.get_text(strip=True)[:50]
        print(f"{i}. <{h.name}> classes={classes}")
        print(f"   Text: {text}")
    
    # Look for any divs/sections that might contain team info
    print("\n" + "=" * 60)
    print("Looking for team/staff related divs...")
    
    team_divs = soup.find_all(['div', 'section'], class_=re.compile(r'team|staff|member|leadership', re.I))
    print(f"Found {len(team_divs)} team/staff divs\n")
    
    for i, div in enumerate(team_divs[:5], 1):
        classes = div.get('class', [])
        print(f"{i}. Classes: {classes}")
        # Look for names inside
        names = re.findall(r'\b([A-Z][a-z]{2,12}\s+[A-Z][a-z]{2,12})\b', div.get_text())
        if names:
            print(f"   Names found: {names[:3]}")

