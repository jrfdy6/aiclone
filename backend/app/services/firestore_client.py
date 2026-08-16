from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

try:
    from google.cloud import firestore  # type: ignore
    from google.oauth2 import service_account  # type: ignore
except Exception:  # pragma: no cover
    firestore = None  # type: ignore
    service_account = None  # type: ignore


def _load_credentials_dict() -> Optional[dict[str, Any]]:
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if raw and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "secrets/firebase-service-account.json")
    candidate = Path(path)
    if candidate.exists():
        try:
            return json.loads(candidate.read_text())
        except json.JSONDecodeError:
            return None
    return None


@lru_cache(maxsize=1)
def get_firestore_client():
    if firestore is None or service_account is None:
        return None

    creds_dict = _load_credentials_dict()
    if not creds_dict:
        return None

    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    return firestore.Client(credentials=credentials, project=creds_dict.get("project_id"))


def write_document(collection: str, document_id: str, payload: dict[str, Any]) -> None:
    client = get_firestore_client()
    if client is None:
        return
    client.collection(collection).document(document_id).set(payload)


def list_documents(collection: str) -> list[dict[str, Any]]:
    client = get_firestore_client()
    if client is None:
        return []
    docs = client.collection(collection).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def get_document(collection: str, document_id: str) -> Optional[dict[str, Any]]:
    client = get_firestore_client()
    if client is None:
        return None
    snap = client.collection(collection).document(document_id).get()
    if not snap.exists:
        return None
    return {"id": snap.id, **snap.to_dict()}


def append_document(collection: str, payload: dict[str, Any]) -> str:
    client = get_firestore_client()
    if client is None:
        return ""
    ref = client.collection(collection).document()
    ref.set(payload)
    return ref.id


# Compatibility export for older routes/services that still import `db` directly.
db = get_firestore_client()
