# 🔧 Firestore Index Setup Guide

## Quick Setup

Two methods to create the required Firestore indexes:

---

## Method 1: Automatic Script (Recommended)

### Option A: Python Script

```bash
cd backend
python create_firestore_indexes.py
```

**Requirements:**
- Firebase Admin SDK (usually already installed)
- `FIREBASE_PROJECT_ID` environment variable (defaults to "aiclone-14ccc")

### Option B: Firebase CLI Script

```bash
cd backend
./create_indexes_simple.sh
```

**Requirements:**
- Firebase CLI installed: `npm install -g firebase-tools`
- Firebase project logged in: `firebase login`

---

## Method 2: Manual Links (Fastest - No Setup Required)

Just click these links to create indexes automatically:

### 1. Content Metrics Index
[Create Index →](https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClVwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9jb250ZW50X21ldHJpY3MvaW5kZXhlcy9fEAEaDgoKY29udGVudF9pZBABGg4KCmNyZWF0ZWRfYXQQAhoMCghfX25hbWVfXxAC)

**Collection:** `users/{userId}/content_metrics`  
**Fields:**
- `content_id` (Ascending)
- `created_at` (Descending)

### 2. Prospect Metrics Index
[Create Index →](https://console.firebase.google.com/v1/r/project/aiclone-14ccc/firestore/indexes?create_composite=ClZwcm9qZWN0cy9haWNsb25lLTE0Y2NjL2RhdGFiYXNlcy8oZGVmYXVsdCkvY29sbGVjdGlvbkdyb3Vwcy9wcm9zcGVjdF9tZXRyaWNzL2luZGV4ZXMvXxABGg8KC3Byb3NwZWN0X2lkEAEaDgoKY3JlYXRlZF9hdBACGgwKCF9fbmFtZV9fEAI)

**Collection:** `users/{userId}/prospect_metrics`  
**Fields:**
- `prospect_id` (Ascending)
- `created_at` (Descending)

---

## Method 3: Firebase Console (Manual)

1. Go to [Firebase Console - Firestore Indexes](https://console.firebase.google.com/project/aiclone-14ccc/firestore/indexes)
2. Click **"Create Index"**
3. Select collection group: `content_metrics` or `prospect_metrics`
4. Add fields:
   - Field 1: `content_id` (or `prospect_id`) - Ascending
   - Field 2: `created_at` - Descending
5. Click **"Create"**

Repeat for the second index.

---

## Verification

After creating indexes:

1. **Wait 2-5 minutes** for indexes to build
2. Check status: [Firebase Console - Indexes](https://console.firebase.google.com/project/aiclone-14ccc/firestore/indexes)
3. Indexes show as "Enabled" when ready

---

## Test After Index Creation

Once indexes are ready, test the endpoints:

```bash
# Test content metrics GET endpoint
curl "https://aiclone-production-32dc.up.railway.app/api/metrics/enhanced/content/draft/{draft_id}?user_id=your_user_id"

# Test prospect metrics GET endpoint  
curl "https://aiclone-production-32dc.up.railway.app/api/metrics/enhanced/prospects/{prospect_id}?user_id=your_user_id"
```

---

## What These Indexes Enable

### Content Metrics Index
- **Endpoint:** `GET /api/metrics/enhanced/content/draft/{draft_id}`
- **Query:** Filter by `content_id` and order by `created_at`
- **Use Case:** Get all metrics for a specific content/draft

### Prospect Metrics Index
- **Endpoint:** `GET /api/metrics/enhanced/prospects/{prospect_id}`
- **Query:** Filter by `prospect_id` and order by `created_at`
- **Use Case:** Get all metrics for a specific prospect

---

## Troubleshooting

### Index Creation Failed
- Check Firebase Console for error messages
- Ensure you have proper permissions
- Try manual creation via Firebase Console

### Indexes Not Building
- Can take 2-5 minutes (sometimes up to 10 minutes for large collections)
- Check index status in Firebase Console
- Ensure fields exist in documents (empty collections might have issues)

### Still Getting Index Errors After Creation
- Wait longer (index building can take time)
- Check index status is "Enabled" (not "Building")
- Verify collection path matches: `users/{userId}/content_metrics` or `users/{userId}/prospect_metrics`

---

## Status

✅ **Warning suppression added** - Firestore warnings now filtered from logs  
⏳ **Index creation** - Use one of the methods above

---

## Files Created

- `backend/create_firestore_indexes.py` - Python script for automatic index creation
- `backend/create_indexes_simple.sh` - Shell script using Firebase CLI
- `FIRESTORE_INDEX_SETUP.md` - This guide

