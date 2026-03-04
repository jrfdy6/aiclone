# Firestore Setup

1. **Create/obtain a Firebase service account** with Firestore access and download the JSON key.
2. **Provide credentials to the app**:
   - Preferred: set `FIREBASE_SERVICE_ACCOUNT` to the JSON string (escape quotes), *or*
   - Save the file to `secrets/firebase-service-account.json` and set `FIREBASE_SERVICE_ACCOUNT_PATH` to that path.
3. **Install dependencies** (already listed in `requirements.txt`): `google-cloud-firestore`, `google-auth`.
4. **Seed collections** (optional but recommended):
   ```bash
   cd downloads/aiclone/backend
   python3 seed_collections.py
   ```
   This script pushes the locally ingested knowledge/playbooks/prospects into Firestore so the API serves real data instead of the fallback cache.
5. **Run the API**:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```
   The `/health` endpoint reports whether Firestore is reachable.
