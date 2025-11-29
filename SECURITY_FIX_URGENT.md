# ⚠️ CRITICAL SECURITY FIX - URGENT ACTION REQUIRED

## Problem
Service account keys were exposed in the public GitHub repository:
- `keys/firebase-service-account.json` - EXPOSED and will be disabled by Google
- `keys/aiclone-drive-ingest-e717f9932b2b.json` - EXPOSED

## ✅ IMPORTANT: Your Data is SAFE!

**Rotating service account keys does NOT delete or modify any Firebase data!**

- Service account keys are just authentication credentials (like passwords)
- Your Firebase data (Firestore collections, documents, etc.) is stored separately
- Rotating keys only replaces the credential used to access Firebase
- All your data remains completely intact
- This is like changing your password - it doesn't delete your account

**You will NOT lose any Firebase data.**

## ✅ Immediate Fixes Applied
1. ✅ Removed `keys/` directory from git tracking
2. ✅ Added `keys/` to `.gitignore` 
3. ✅ Added patterns to prevent future key commits

## 🔴 CRITICAL: You MUST Do These Steps NOW

### Step 1: Remove Keys from Git History
The keys are still in git history. We need to remove them completely:

```bash
# Remove keys from entire git history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch keys/*.json' \
  --prune-empty --tag-name-filter cat -- --all

# Force push (WARNING: This rewrites history)
git push origin main --force
```

### Step 2: Rotate the Firebase Service Account Key

1. **Go to Google Cloud Console:**
   - https://console.cloud.google.com/iam-admin/serviceaccounts
   - Select project: `aiclone-14ccc`

2. **Find the service account:**
   - `firebase-adminsdk-fbsvc@aiclone-14ccc.iam.gserviceaccount.com`

3. **Delete the exposed key:**
   - Click on the service account
   - Go to "Keys" tab
   - Delete key ID: `5bf7a3ac5a0c89b166ddce5bf16271af1bbf45ea`

4. **Create a new key:**
   - Click "Add Key" → "Create new key"
   - Choose JSON format
   - Download the new key

5. **Update Railway Environment Variable:**
   - Go to Railway → aiclone-backend → Variables
   - Update `FIREBASE_SERVICE_ACCOUNT` with the NEW key JSON (as a string)
   - The value should be the entire JSON file content as a single-line string

### Step 3: Rotate the Google Drive Service Account Key

1. **Find the Drive service account:**
   - Look for the service account that matches `aiclone-drive-ingest-*.json`

2. **Delete the exposed key and create a new one** (same process as above)

3. **Update Railway Environment Variable:**
   - Update `GOOGLE_DRIVE_SERVICE_ACCOUNT` with the NEW key JSON

### Step 4: Verify Security

```bash
# Check that keys are no longer tracked
git ls-files | grep -i "service.*account\|\.json" | grep -v package | grep -v tsconfig

# Should return nothing (or only safe files)
```

## 🔒 Prevention for Future

1. **Never commit keys to git**
2. **Always use environment variables** in Railway
3. **Use `.gitignore` patterns** (already added)
4. **Before committing, run:**
   ```bash
   git status
   # Check that no .json files in keys/ are shown
   ```

## Current Status

- ✅ Keys removed from working directory tracking
- ✅ `.gitignore` updated
- ⚠️ **Keys still in git history** - need to clean with filter-branch
- ⚠️ **Keys need to be rotated** in Google Cloud Console
- ⚠️ **Railway env vars need updating** with new keys

## Next Commit

The next commit will:
- Remove keys from git tracking
- Update .gitignore
- Force push to clean history (after you run filter-branch)

**DO NOT commit any new keys!** Use environment variables only.

