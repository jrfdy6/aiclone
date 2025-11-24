"""
Create Firestore Indexes Automatically

This script creates the required composite indexes for the Enhanced Metrics endpoints.
"""

import os
import sys
from google.cloud import firestore_admin_v1
from google.cloud.firestore_admin_v1 import CreateIndexRequest, Index, IndexField

def create_indexes():
    """Create required Firestore composite indexes."""
    
    project_id = os.getenv("FIREBASE_PROJECT_ID", "aiclone-14ccc")
    
    print(f"🔧 Creating Firestore indexes for project: {project_id}")
    print("=" * 60)
    
    # Initialize Firestore Admin client
    try:
        client = firestore_admin_v1.FirestoreAdminClient()
        parent = f"projects/{project_id}/databases/(default)/collectionGroups"
    except Exception as e:
        print(f"❌ Error initializing Firestore Admin client: {e}")
        print("\nNote: This script requires the Firebase Admin SDK.")
        print("If you don't have it installed, you can:")
        print("1. Click the index creation links in the error messages")
        print("2. Or install firebase-tools and use: firebase deploy --only firestore:indexes")
        return False
    
    indexes_to_create = [
        {
            "collection": "content_metrics",
            "name": "Content Metrics - content_id + created_at",
            "fields": [
                IndexField(field_path="content_id", order=IndexField.Order.ASCENDING),
                IndexField(field_path="created_at", order=IndexField.Order.DESCENDING),
            ]
        },
        {
            "collection": "prospect_metrics",
            "name": "Prospect Metrics - prospect_id + created_at",
            "fields": [
                IndexField(field_path="prospect_id", order=IndexField.Order.ASCENDING),
                IndexField(field_path="created_at", order=IndexField.Order.DESCENDING),
            ]
        }
    ]
    
    created = 0
    skipped = 0
    
    for index_config in indexes_to_create:
        try:
            collection_group = index_config["collection"]
            index_name = index_config["name"]
            fields = index_config["fields"]
            
            print(f"\n📋 Creating index: {index_name}")
            print(f"   Collection: {collection_group}")
            
            # Create index definition
            index = Index(
                query_scope=Index.QueryScope.COLLECTION,
                fields=fields
            )
            
            # Create the index
            request = CreateIndexRequest(
                parent=f"{parent}/{collection_group}",
                index=index
            )
            
            try:
                operation = client.create_index(request=request)
                print(f"   ✅ Index creation started (operation: {operation.name})")
                print(f"   ⏳ Index will be ready in 2-5 minutes")
                created += 1
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"   ⚠️  Index already exists, skipping")
                    skipped += 1
                else:
                    raise
            
        except Exception as e:
            print(f"   ❌ Error creating index: {e}")
            print(f"   📝 Manual creation link will be provided below")
    
    print("\n" + "=" * 60)
    print(f"✅ Created: {created} indexes")
    print(f"⚠️  Skipped (already exist): {skipped} indexes")
    print("\n💡 Indexes take 2-5 minutes to build. Check status in Firebase Console:")
    print(f"   https://console.firebase.google.com/project/{project_id}/firestore/indexes")
    
    return True


def print_manual_links():
    """Print manual index creation links as fallback."""
    print("\n" + "=" * 60)
    print("🔗 Manual Index Creation Links (if script doesn't work)")
    print("=" * 60)
    print("\n1. Content Metrics Index:")
    print("   https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClVwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9jb250ZW50X21ldHJpY3MvaW5kZXhlcy9fEAEaDgoKY29udGVudF9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC")
    print("\n2. Prospect Metrics Index:")
    print("   https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClZwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9wcm9zcGVjdF9tZXRyaWNzL2luZGV4ZXMvXxABGg8KC3Byb3NwZWN0X2lkEAEaDgoKY3JlYXRlZF9hdBACGgwKCF9fbmFtZV9fEAI")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("🚀 Firestore Index Creation Script")
    print("=" * 60)
    
    try:
        success = create_indexes()
        if not success:
            print_manual_links()
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        print("\n💡 Alternative: Use manual links below or Firebase CLI")
        print_manual_links()
        sys.exit(1)

