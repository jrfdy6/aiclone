from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

try:
    from google.cloud import firestore  # type: ignore
    from google.oauth2 import service_account  # type: ignore
except Exception:  # pragma: no cover
    firestore = None  # type: ignore
    service_account = None  # type: ignore


logger = logging.getLogger(__name__)

TOP_LEVEL_READ_COLLECTIONS = frozenset({"knowledge_docs", "playbooks", "system_logs", "prospects"})
TOP_LEVEL_WRITE_COLLECTIONS = frozenset({"knowledge_docs", "playbooks", "system_logs"})


class FirestoreUnavailableError(RuntimeError):
    """Sanitized error for an unavailable configured Firestore authority."""


@dataclass(frozen=True)
class FirestoreReadResult:
    value: Any
    state: str
    reason_codes: tuple[str, ...]


def _require_top_level_collection(collection: str, *, write: bool) -> str:
    allowlist = TOP_LEVEL_WRITE_COLLECTIONS if write else TOP_LEVEL_READ_COLLECTIONS
    if collection not in allowlist:
        raise ValueError("Firestore collection is not allowlisted for this operation")
    return collection


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
        except (json.JSONDecodeError, OSError):
            return None
    return None


@lru_cache(maxsize=1)
def get_firestore_client():
    if firestore is None or service_account is None:
        return None

    creds_dict = _load_credentials_dict()
    if not creds_dict:
        return None

    try:
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        return firestore.Client(credentials=credentials, project=creds_dict.get("project_id"))
    except Exception as exc:
        logger.warning("Firestore client initialization failed [%s]", type(exc).__name__)
        return None


def write_document(collection: str, document_id: str, payload: dict[str, Any]) -> None:
    _require_top_level_collection(collection, write=True)
    client = get_firestore_client()
    if client is None:
        raise FirestoreUnavailableError("Firestore is unavailable")
    client.collection(collection).document(document_id).set(payload)


def list_documents(collection: str) -> list[dict[str, Any]]:
    _require_top_level_collection(collection, write=False)
    client = get_firestore_client()
    if client is None:
        return []
    docs = client.collection(collection).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def get_document(collection: str, document_id: str) -> Optional[dict[str, Any]]:
    _require_top_level_collection(collection, write=False)
    client = get_firestore_client()
    if client is None:
        return None
    snap = client.collection(collection).document(document_id).get()
    if not snap.exists:
        return None
    return {"id": snap.id, **snap.to_dict()}


def append_document(collection: str, payload: dict[str, Any]) -> str:
    _require_top_level_collection(collection, write=True)
    client = get_firestore_client()
    if client is None:
        raise FirestoreUnavailableError("Firestore is unavailable")
    ref = client.collection(collection).document()
    ref.set(payload)
    return ref.id


def list_documents_with_status(collection: str) -> FirestoreReadResult:
    """Return an explicit degraded state for compatibility reads."""

    _require_top_level_collection(collection, write=False)
    client = get_firestore_client()
    if client is None:
        return FirestoreReadResult(value=[], state="degraded", reason_codes=("firestore_unavailable",))
    try:
        docs = client.collection(collection).stream()
        value = [{"id": doc.id, **(doc.to_dict() or {})} for doc in docs]
        return FirestoreReadResult(value=value, state="ready", reason_codes=())
    except Exception as exc:
        logger.warning("Firestore collection read failed for %s [%s]", collection, type(exc).__name__)
        return FirestoreReadResult(value=[], state="degraded", reason_codes=("firestore_read_failed",))


def get_document_with_status(collection: str, document_id: str) -> FirestoreReadResult:
    """Return a document plus explicit readiness without leaking provider errors."""

    _require_top_level_collection(collection, write=False)
    client = get_firestore_client()
    if client is None:
        return FirestoreReadResult(value=None, state="degraded", reason_codes=("firestore_unavailable",))
    try:
        snap = client.collection(collection).document(document_id).get()
        value = {"id": snap.id, **(snap.to_dict() or {})} if snap.exists else None
        return FirestoreReadResult(value=value, state="ready", reason_codes=())
    except Exception as exc:
        logger.warning("Firestore document read failed for %s [%s]", collection, type(exc).__name__)
        return FirestoreReadResult(value=None, state="degraded", reason_codes=("firestore_read_failed",))


# Compatibility export for older routes/services that still import `db` directly.
# New code should resolve the client per operation so unavailable Firestore can
# be reported as a degraded dependency instead of crashing module import.
db = get_firestore_client()
