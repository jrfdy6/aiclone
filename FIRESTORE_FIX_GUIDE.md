# Firestore Connectivity Fix Guide

## Problem
Firestore queries hang indefinitely on Railway, causing chat endpoint timeouts.

## Step-by-Step Diagnosis & Fix

### STEP 1: Test Firestore Locally ✅

First, verify Firestore works on your local machine:

```bash
cd /Users/johnniefields/Desktop/Cursor/aiclone/backend
source ../.venv/bin/activate
set -a && source .env && set +a
python test_firestore.py
```

**What to look for:**
- ✅ If it works locally → Issue is Railway-specific (network/credentials)
- ❌ If it fails locally → Issue is with your Firestore setup/credentials

### STEP 2: Verify Railway Credentials 🔑

1. Go to **Railway Dashboard** → Your Service → **Variables**
2. Check `FIREBASE_SERVICE_ACCOUNT`:
   - Should be a complete JSON string
   - Must include: `project_id`, `private_key`, `client_email`
   - No line breaks or formatting issues

3. Compare with your local `.env`:
   ```bash
   # Check what Railway has vs what you have locally
   cat backend/.env | grep FIREBASE
   ```

### STEP 3: Check Firestore Project Settings 🔍

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Check:
   - **Firestore Database** → Is it created?
   - **Project Settings** → Service Accounts → Is the service account active?
   - **Firestore Rules** → Are they allowing service account access?

### STEP 4: Test Firestore from Railway 🚂

Create a test endpoint to diagnose from Railway:

```python
# Add to backend/app/routes/chat.py or create new test route
@router.get("/test-firestore")
async def test_firestore():
    try:
        from app.services.firestore_client import db
        collections = list(db.collections())
        return {
            "success": True,
            "collections": [c.id for c in collections[:5]],
            "message": "Firestore connection OK"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

Then test: `curl https://aiclone-production-32dc.up.railway.app/api/test-firestore`

### STEP 5: Potential Solutions 🛠️

#### Solution A: Check Network Connectivity
Railway might not be able to reach Firestore due to:
- Firewall rules
- Network restrictions
- Region mismatch

**Fix:** Verify Railway region can access Firestore (usually not an issue, but worth checking)

#### Solution B: Verify Service Account Permissions
The service account needs:
- `Cloud Datastore User` role (for Firestore)
- Access to the correct project

**Fix:** 
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. IAM & Admin → Service Accounts
3. Find your service account
4. Verify it has `Cloud Datastore User` role

#### Solution C: Use Async Firestore Operations
The blocking Firestore SDK might be causing issues. Consider using async operations.

**Fix:** Switch to `google-cloud-firestore` async client (requires code changes)

#### Solution D: Check Firestore Region
If your Firestore is in a specific region, Railway might need to connect to that region.

**Fix:** Verify Firestore location matches Railway region expectations

### STEP 6: Re-enable Firestore Queries 🔄

Once connectivity is fixed, re-enable queries in `backend/app/services/retrieval.py`:

```python
def get_all_embeddings_for_user(...):
    # Remove the temporary workaround:
    # print(f"  [retrieval] ⚠️ Firestore queries temporarily disabled...")
    # return []
    
    # Restore the original Firestore query code
    collection = db.collection("users").document(user_id).collection("memory_chunks")
    query = collection.limit(max_documents)
    documents = query.get()
    # ... rest of the code
```

## Quick Test Checklist

- [ ] Run `test_firestore.py` locally - does it work?
- [ ] Check Railway Variables - is `FIREBASE_SERVICE_ACCOUNT` set correctly?
- [ ] Verify service account has `Cloud Datastore User` role
- [ ] Check Firestore database exists and is accessible
- [ ] Test from Railway using test endpoint
- [ ] Compare local vs Railway behavior

## Next Steps

1. **Start with Step 1** - Run the local test script
2. **Share the results** - Does it work locally?
3. **Check Railway credentials** - Are they correct?
4. **We'll diagnose from there** - Based on what we find

Let me know what you discover in Step 1!


