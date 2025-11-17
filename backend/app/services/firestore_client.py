import json
import os

import firebase_admin
from firebase_admin import credentials, firestore


_service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
_service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if _service_account_json:
    # Use inline JSON string
    service_account_dict = json.loads(_service_account_json)
    credential = credentials.Certificate(service_account_dict)
elif _service_account_file and os.path.exists(_service_account_file):
    # Use file path
    credential = credentials.Certificate(_service_account_file)
else:
    # Fall back to Application Default Credentials
    credential = credentials.ApplicationDefault()

if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app(credential)
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}", flush=True)
        raise

try:
    db = firestore.client()
except Exception as e:
    print(f"❌ Firestore client creation failed: {e}", flush=True)
    raise
