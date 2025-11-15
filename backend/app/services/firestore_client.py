import json
import os

import firebase_admin
from firebase_admin import credentials, firestore


_service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")

if _service_account_json:
    service_account_dict = json.loads(_service_account_json)
    credential = credentials.Certificate(service_account_dict)
else:
    credential = credentials.ApplicationDefault()

if not firebase_admin._apps:
    firebase_admin.initialize_app(credential)


db = firestore.client()
