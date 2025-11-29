#!/usr/bin/env python3
"""
Analyze saved prospects to see category distribution and data quality
"""
import os
import sys
import json
from firebase_admin import credentials, firestore, initialize_app

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv()

# Initialize Firebase
service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
if service_account_json:
    cred = credentials.Certificate(json.loads(service_account_json))
    if not firestore.client._apps:
        initialize_app(cred)
    db = firestore.client()
else:
    print("❌ FIREBASE_SERVICE_ACCOUNT not set")
    sys.exit(1)

def analyze_prospects():
    user_id = "dev-user"
    prospects_ref = db.collection("users").document(user_id).collection("prospects")
    
    docs = prospects_ref.limit(50).get()
    prospects = [doc.to_dict() for doc in docs]
    
    print(f"\n{'='*60}")
    print(f"PROSPECT ANALYSIS - {len(prospects)} total prospects")
    print(f"{'='*60}\n")
    
    # Category distribution
    category_counts = {}
    for p in prospects:
        tags = p.get("tags", [])
        if tags:
            cat = tags[0] if isinstance(tags, list) else tags
            category_counts[cat] = category_counts.get(cat, 0) + 1
    
    print("📊 CATEGORY DISTRIBUTION:")
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count} prospects")
    
    print(f"\n📋 ALL PROSPECTS:")
    for i, p in enumerate(prospects, 1):
        name = p.get("name", "Unknown")
        company = p.get("company", "—")
        tags = p.get("tags", [])
        email = p.get("email", "N/A")
        phone = p.get("phone", "N/A")
        fit_score = p.get("fit_score", 0)
        
        category = tags[0] if tags else "No category"
        print(f"{i:2d}. {name:30s} | {category:30s} | Org: {company[:25]:25s} | Email: {email[:20]:20s} | Phone: {phone}")
    
    # Data quality metrics
    print(f"\n{'='*60}")
    print("📈 DATA QUALITY METRICS:")
    print(f"{'='*60}")
    
    with_email = sum(1 for p in prospects if p.get("email"))
    with_phone = sum(1 for p in prospects if p.get("phone"))
    with_company = sum(1 for p in prospects if p.get("company") and p.get("company") != "—")
    
    print(f"  Total prospects: {len(prospects)}")
    print(f"  With email: {with_email} ({with_email/len(prospects)*100:.1f}%)")
    print(f"  With phone: {with_phone} ({with_phone/len(prospects)*100:.1f}%)")
    print(f"  With company: {with_company} ({with_company/len(prospects)*100:.1f}%)")
    print(f"  Average fit score: {sum(p.get('fit_score', 0) for p in prospects)/len(prospects):.1f}")

if __name__ == "__main__":
    analyze_prospects()

