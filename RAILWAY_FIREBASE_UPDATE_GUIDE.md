# Step-by-Step: Update Firebase Service Account Key in Railway

## 🎯 What You Need to Do

You have a new Firebase service account key file. Now you need to update the Railway environment variable.

## 📋 Step-by-Step Instructions

### Step 1: Get the Formatted Key

The Firebase key JSON needs to be converted to a **single-line string** for Railway.

**Run this command to get the formatted key:**
```bash
cd /Users/johnniefields/Desktop/Cursor/aiclone
python3 << 'PYEOF'
import json
with open("/Users/johnniefields/Downloads/aiclone-14ccc-firebase-adminsdk-fbsvc-df8b187505.json", 'r') as f:
    key_data = json.load(f)
single_line_json = json.dumps(key_data, separators=(',', ':'))
print(single_line_json)
PYEOF
```

**Copy the entire output** (it's one long line).

### Step 2: Update Railway Variable

1. **In Railway Dashboard:**
   - Go to your `aiclone-backend` service
   - Click on the **"Variables"** tab (you're already there!)

2. **Find the FIREBASE_SERVICE_ACCOUNT variable:**
   - Look for `FIREBASE_SERVICE_ACCOUNT` in the list

3. **Click the three dots (⋯) on the right** of that variable

4. **Select "Update" or "Edit"**

5. **In the Value field:**
   - Delete the old value (the masked *******)
   - Paste the **entire single-line JSON string** you copied in Step 1

6. **Click "Save" or "Update"**

### Step 3: Verify

Railway will automatically redeploy your backend after you save. You should see:
- A new deployment starting
- The backend should reconnect to Firebase successfully

## ✅ Your Firebase Data is SAFE

- ✅ No data will be deleted
- ✅ All your Firestore collections remain intact
- ✅ All your documents remain intact
- ✅ This only updates the authentication credential

## 🔍 Quick Formatting Command

If you need to format the key again, use:

```bash
python3 -c "import json; print(json.dumps(json.load(open('/Users/johnniefields/Downloads/aiclone-14ccc-firebase-adminsdk-fbsvc-df8b187505.json')), separators=(',', ':')))"
```

This will output the properly formatted single-line JSON string ready to paste into Railway.

## ⚠️ Important Notes

1. **The value should be ONE long line** - no line breaks
2. **Copy the ENTIRE string** - from `{` to `}`
3. **Don't add quotes** - Railway handles that automatically
4. **After saving**, Railway will automatically redeploy

