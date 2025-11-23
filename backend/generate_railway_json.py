#!/usr/bin/env python3
"""
Generate single-line JSON for Railway FIREBASE_SERVICE_ACCOUNT variable.
"""
import json
import sys

if len(sys.argv) < 2:
    print("Usage: python generate_railway_json.py <path-to-service-account.json>")
    sys.exit(1)

json_file = sys.argv[1]

try:
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Convert to single-line JSON
    single_line = json.dumps(data)
    
    print("=" * 70)
    print("Single-line JSON for Railway FIREBASE_SERVICE_ACCOUNT:")
    print("=" * 70)
    print(single_line)
    print("=" * 70)
    print("\n📋 Instructions:")
    print("1. Copy the JSON above (the entire single line)")
    print("2. Go to Railway Dashboard → Your Service → Variables")
    print("3. Edit FIREBASE_SERVICE_ACCOUNT")
    print("4. Paste the single-line JSON")
    print("5. Save and Railway will redeploy automatically")
    print("\n✅ This ensures proper formatting without newline issues")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)


