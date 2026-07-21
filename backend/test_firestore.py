#!/usr/bin/env python3
"""
Test script to verify Firestore connectivity.
Run this locally to see if Firestore works, then compare with Railway.
"""
import os
import sys
import json
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app.services.firestore_client import db
    print("✅ Firestore client imported successfully")
except Exception as e:
    print(f"❌ Failed to import Firestore client: {e}")
    sys.exit(1)

def test_firestore_connection():
    """Test basic Firestore operations."""
    print("\n🔍 Testing Firestore Connection...")
    print("=" * 50)
    
    # Test 1: List collections
    print("\n1️⃣ Testing: List collections...")
    try:
        collections = db.collections()
        collection_list = list(collections)
        print(f"   ✅ Successfully listed collections: {len(collection_list)} found")
        for col in collection_list[:5]:  # Show first 5
            print(f"      - {col.id}")
    except Exception as e:
        print(f"   ❌ Failed to list collections: {e}")
        return False
    
    # Test 2: Try to read from a test collection
    print("\n2️⃣ Testing: Read from test collection...")
    test_user_id = "test-user"
    try:
        collection = db.collection("users").document(test_user_id).collection("memory_chunks")
        print(f"   📁 Accessing: users/{test_user_id}/memory_chunks")
        
        # Try to get documents with a small limit
        query = collection.limit(1)
        print("   ⏳ Executing query (limit 1)...")
        print("   ⚠️  Note: If this hangs, it's the same issue as Railway")
        
        import concurrent.futures
        
        try:
            # Use ThreadPoolExecutor with timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(query.get)
                docs = future.result(timeout=5.0)  # 5 second timeout
            
            print(f"   ✅ Query completed! Found {len(docs)} documents")
            if len(docs) > 0:
                doc = docs[0]
                data = doc.to_dict()
                print(f"      Sample doc ID: {doc.id}")
                print(f"      Has embedding: {'embedding' in data}")
        except concurrent.futures.TimeoutError:
            print("   ❌ Query timed out after 5 seconds (same issue as Railway)")
            print("   This suggests a Firestore connectivity/network issue")
            return False
        except Exception as e:
            print(f"   ❌ Query failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"   ❌ Failed to access collection: {e}")
        return False
    
    # Test 3: Try to write a test document
    print("\n3️⃣ Testing: Write test document...")
    try:
        test_collection = db.collection("_test")
        test_doc = test_collection.document("connectivity_test")
        test_doc.set({
            "timestamp": datetime.utcnow().isoformat(),
            "test": True
        })
        print("   ✅ Successfully wrote test document")
        
        # Clean up
        test_doc.delete()
        print("   ✅ Cleaned up test document")
    except Exception as e:
        print(f"   ❌ Failed to write test document: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All Firestore tests passed!")
    print("\nIf this works locally but fails on Railway, it's likely:")
    print("  - Network connectivity issue (Railway can't reach Firestore)")
    print("  - Firestore credentials issue (different credentials on Railway)")
    print("  - Firestore region/endpoint configuration issue")
    return True

if __name__ == "__main__":
    success = test_firestore_connection()
    sys.exit(0 if success else 1)

