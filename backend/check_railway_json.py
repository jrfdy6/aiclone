#!/usr/bin/env python3
"""
Check if the JSON we generated is valid and provide Railway-specific instructions.
"""
import json
import sys

json_file = "keys/firebase-service-account.json"

try:
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Convert to single-line JSON
    single_line = json.dumps(data)
    
    print("=" * 70)
    print("JSON Validation & Railway Instructions")
    print("=" * 70)
    print(f"\n✅ JSON is valid")
    print(f"📏 Total length: {len(single_line)} characters")
    print(f"📋 Number of fields: {len(data)}")
    
    # Check if it's too long for Railway (some systems have limits)
    if len(single_line) > 10000:
        print(f"\n⚠️  WARNING: JSON is {len(single_line)} characters long")
        print("   Railway might have character limits. Consider using base64 encoding.")
    
    print("\n" + "=" * 70)
    print("HOW TO SET IN RAILWAY:")
    print("=" * 70)
    print("\nOption 1: Direct Paste (Recommended)")
    print("-" * 70)
    print("1. Go to Railway Dashboard → Your Service → Variables")
    print("2. Click 'Edit' on FIREBASE_SERVICE_ACCOUNT (or 'Add Variable')")
    print("3. In the 'Value' field, paste this ENTIRE line:")
    print("\n" + single_line[:100] + "...")
    print(f"\n   (Full JSON is {len(single_line)} characters - make sure you copy ALL of it)")
    print("\n4. Click 'Save'")
    print("\n⚠️  IMPORTANT:")
    print("   - Copy the ENTIRE line (use Cmd+A to select all)")
    print("   - Make sure there are NO line breaks in the middle")
    print("   - Don't add quotes around it (Railway handles that)")
    print("   - If Railway shows a character limit, use Option 2")
    
    print("\n" + "=" * 70)
    print("Option 2: Base64 Encoding (if direct paste fails)")
    print("-" * 70)
    import base64
    base64_encoded = base64.b64encode(single_line.encode('utf-8')).decode('utf-8')
    print("If Railway has character limits, you can base64 encode it:")
    print(f"Base64 length: {len(base64_encoded)} characters")
    print("\n(We'd need to update the code to decode base64 first)")
    
    print("\n" + "=" * 70)
    print("TROUBLESHOOTING:")
    print("=" * 70)
    print("If you get 'Unterminated string' error:")
    print("  1. The JSON was likely truncated when pasting")
    print("  2. Make sure you copied the ENTIRE line")
    print("  3. Try copying in smaller chunks and pasting together")
    print("  4. Check Railway's variable value - does it end with '}'?")
    print("  5. Railway might have a character limit - check their docs")
    
    # Save to file for easy copying
    output_file = "/tmp/railway_firebase_json.txt"
    with open(output_file, 'w') as f:
        f.write(single_line)
    print(f"\n✅ Full JSON saved to: {output_file}")
    print("   You can open this file and copy the entire line")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)


