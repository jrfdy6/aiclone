#!/usr/bin/env python3
"""
Script to verify FIREBASE_SERVICE_ACCOUNT JSON format.
This helps ensure the JSON is valid before setting it in Railway.
"""
import os
import json
import sys

def verify_json_format():
    """Verify the Firebase service account JSON format."""
    print("🔍 Verifying FIREBASE_SERVICE_ACCOUNT JSON Format")
    print("=" * 60)
    
    # Check if provided as argument (file path)
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        print(f"\n📁 Reading from file: {json_file}")
        try:
            with open(json_file, 'r') as f:
                json_str = f.read()
        except Exception as e:
            print(f"❌ Failed to read file: {e}")
            return False
    else:
        # Check environment variable
        json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT")
        if not json_str:
            print("\n⚠️  FIREBASE_SERVICE_ACCOUNT not set in environment")
            print("\nUsage:")
            print("  Option 1: Set environment variable")
            print("    export FIREBASE_SERVICE_ACCOUNT='{...}'")
            print("    python verify_firestore_json.py")
            print("")
            print("  Option 2: Provide JSON file path")
            print("    python verify_firestore_json.py /path/to/service-account.json")
            return False
        print("\n📋 Reading from FIREBASE_SERVICE_ACCOUNT environment variable")
    
    # Try to parse JSON
    print("\n1️⃣ Validating JSON format...")
    try:
        data = json.loads(json_str)
        print("   ✅ JSON is valid")
    except json.JSONDecodeError as e:
        print(f"   ❌ Invalid JSON: {e}")
        print("\n   Common issues:")
        print("   - Missing quotes around the JSON string in Railway")
        print("   - Newlines not escaped (\\n)")
        print("   - Special characters not escaped")
        return False
    
    # Check required fields
    print("\n2️⃣ Checking required fields...")
    required_fields = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url"
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    
    if missing_fields:
        print(f"   ❌ Missing required fields: {', '.join(missing_fields)}")
        return False
    else:
        print("   ✅ All required fields present")
    
    # Display key info (without sensitive data)
    print("\n3️⃣ Service Account Info:")
    print(f"   Project ID: {data.get('project_id', 'N/A')}")
    print(f"   Client Email: {data.get('client_email', 'N/A')}")
    print(f"   Type: {data.get('type', 'N/A')}")
    
    # Check if private key looks valid
    private_key = data.get('private_key', '')
    if private_key.startswith('-----BEGIN PRIVATE KEY-----'):
        print("   ✅ Private key format looks correct")
    else:
        print("   ⚠️  Private key format might be incorrect")
    
    # Instructions for Railway
    print("\n" + "=" * 60)
    print("✅ JSON is valid and ready for Railway!")
    print("\n📋 To set in Railway:")
    print("   1. Go to Railway Dashboard → Your Service → Variables")
    print("   2. Add/Edit variable: FIREBASE_SERVICE_ACCOUNT")
    print("   3. Paste the ENTIRE JSON as a single-line string")
    print("   4. Make sure it's wrapped in quotes if Railway requires it")
    print("\n💡 Tip: If the JSON has newlines, you can:")
    print("   - Remove all newlines (make it one line)")
    print("   - Or escape them as \\n")
    print("   - Railway usually handles both formats")
    
    return True

if __name__ == "__main__":
    success = verify_json_format()
    sys.exit(0 if success else 1)


