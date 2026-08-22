from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.services import firestore_client


PROSPECT_SCHEMA_VERSION = "firestore_prospect/v1"
PROSPECT_MIGRATION_PLAN_SCHEMA_VERSION = "firestore_prospect_migration_plan/v1"
CANONICAL_PROSPECT_PARENT_COLLECTION = "users"
CANONICAL_PROSPECT_COLLECTION = "prospects"
LEGACY_TOP_LEVEL_PROSPECT_COLLECTION = "prospects"

_SAFE_FIRESTORE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_CLIENT_UNSET = object()


class FirestoreProspectAuthorityError(RuntimeError):
    """A sanitized failure at the canonical prospect storage boundary."""


class FirestoreProspectNotFoundError(FirestoreProspectAuthorityError):
    """The requested prospect does not exist in the canonical nested store."""


@dataclass(frozen=True)
class ProspectAuthorityReadResult:
    documents: tuple[dict[str, Any], ...]
    state: str
    source: str
    reason_codes: tuple[str, ...]
    canonical_count: int
    legacy_count: int
    legacy_only_count: int
    conflict_count: int


def _resolve_client(client: Any) -> Any:
    if client is _CLIENT_UNSET:
        return firestore_client.get_firestore_client()
    return client


def _require_user_id(user_id: str) -> str:
    normalized = str(user_id or "").strip()
    if not _SAFE_FIRESTORE_ID.fullmatch(normalized):
        raise ValueError("user_id is not a valid canonical Firestore document identifier")
    return normalized


def _safe_document_id(value: Any, *, payload: Mapping[str, Any] | None = None) -> str:
    candidate = str(value or "").strip()
    if _SAFE_FIRESTORE_ID.fullmatch(candidate):
        return candidate
    stable_payload = json.dumps(dict(payload or {}), sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(f"{candidate}\n{stable_payload}".encode("utf-8")).hexdigest()[:24]
    return f"prospect-{digest}"


def canonical_prospect_collection(client: Any, user_id: str) -> Any:
    """Return the one writable Firestore prospect collection."""

    if client is None:
        raise FirestoreProspectAuthorityError("canonical prospect authority is unavailable")
    normalized_user_id = _require_user_id(user_id)
    return (
        client.collection(CANONICAL_PROSPECT_PARENT_COLLECTION)
        .document(normalized_user_id)
        .collection(CANONICAL_PROSPECT_COLLECTION)
    )


def canonicalize_prospect_document(
    payload: Mapping[str, Any],
    *,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Normalize legacy flat and canonical prospect shapes without mutating input."""

    raw = dict(payload)
    resolved_id = _safe_document_id(document_id or raw.get("id"), payload=raw)
    raw_contact = raw.get("contact") if isinstance(raw.get("contact"), Mapping) else {}

    email = raw_contact.get("email") or raw.get("email")
    phone = raw_contact.get("phone") or raw.get("phone")
    website = raw_contact.get("website") or raw.get("website")
    linkedin = raw_contact.get("linkedin") or raw.get("linkedin")

    confidence = raw.get("confidence")
    if confidence is None:
        confidence = raw.get("fit_score")
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100.0

    tags = raw.get("tags")
    if not isinstance(tags, list):
        tags = []

    normalized: dict[str, Any] = {
        "schema_version": PROSPECT_SCHEMA_VERSION,
        "id": resolved_id,
        "name": raw.get("name"),
        "title": raw.get("title") or raw.get("job_title"),
        "organization": raw.get("organization") or raw.get("company"),
        "category": raw.get("category"),
        "source": raw.get("source"),
        "url": raw.get("url") or raw.get("source_url"),
        "confidence": confidence,
        "tags": [str(item) for item in tags if str(item).strip()],
        "contact": {
            "email": email,
            "phone": phone,
        },
    }
    if raw.get("created_at") is not None:
        normalized["created_at"] = raw.get("created_at")

    # These bounded operational fields are part of the existing prospect-product
    # contract. They remain optional and do not create a second storage shape.
    optional_fields = {
        "status": raw.get("status"),
        "location": raw.get("location"),
        "website": website,
        "linkedin": linkedin,
        "bio_snippet": raw.get("bio_snippet"),
        "last_action": raw.get("last_action"),
        "notes": raw.get("notes"),
        "summary": raw.get("summary"),
        "pain_points": raw.get("pain_points"),
    }
    normalized.update({key: value for key, value in optional_fields.items() if value is not None})
    return normalized


def legacy_pipeline_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project the canonical record into the existing flat read-only UI shape."""

    canonical = canonicalize_prospect_document(payload, document_id=str(payload.get("id") or ""))
    contact = canonical.get("contact") or {}
    confidence = canonical.get("confidence")
    fit_score = confidence * 100 if isinstance(confidence, (int, float)) and confidence <= 1 else confidence
    return {
        "id": canonical["id"],
        "name": canonical.get("name"),
        "company": canonical.get("organization"),
        "job_title": canonical.get("title"),
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "website": canonical.get("website"),
        "fit_score": fit_score,
        "status": canonical.get("status") or "new",
        "category": canonical.get("category"),
        "location": canonical.get("location"),
        "tags": canonical.get("tags") or [],
        "last_action": canonical.get("last_action"),
        "notes": canonical.get("notes"),
        "summary": canonical.get("summary"),
        "pain_points": canonical.get("pain_points") or [],
        "source": canonical.get("source"),
        "source_url": canonical.get("url"),
        "created_at": canonical.get("created_at"),
    }


def _snapshot_documents(snapshots: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        rows.append(canonicalize_prospect_document(data, document_id=str(snapshot.id)))
    return rows


def _identity_key(payload: Mapping[str, Any]) -> str:
    canonical = canonicalize_prospect_document(payload, document_id=str(payload.get("id") or ""))
    contact = canonical.get("contact") or {}
    email = str(contact.get("email") or "").strip().casefold()
    if email:
        return f"email:{email}"
    url = str(canonical.get("url") or "").strip().casefold()
    if url:
        return f"url:{url}"
    name = str(canonical.get("name") or "").strip().casefold()
    organization = str(canonical.get("organization") or "").strip().casefold()
    if name:
        return f"name:{name}|organization:{organization}"
    return f"id:{canonical['id']}"


def _materially_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    ignored = {"schema_version", "id", "created_at"}
    left_value = {key: value for key, value in canonicalize_prospect_document(left).items() if key not in ignored}
    right_value = {key: value for key, value in canonicalize_prospect_document(right).items() if key not in ignored}
    return left_value == right_value


def read_prospects(
    user_id: str,
    *,
    client: Any = _CLIENT_UNSET,
    include_legacy_top_level: bool = True,
) -> ProspectAuthorityReadResult:
    """Read canonical prospects and merge legacy-only rows without writing either path."""

    resolved_client = _resolve_client(client)
    _require_user_id(user_id)
    if resolved_client is None:
        return ProspectAuthorityReadResult(
            documents=(),
            state="degraded",
            source="unavailable",
            reason_codes=("firestore_unavailable",),
            canonical_count=0,
            legacy_count=0,
            legacy_only_count=0,
            conflict_count=0,
        )

    reason_codes: list[str] = []
    canonical_rows: list[dict[str, Any]] = []
    legacy_rows: list[dict[str, Any]] = []
    try:
        canonical_rows = _snapshot_documents(canonical_prospect_collection(resolved_client, user_id).stream())
    except Exception:
        reason_codes.append("canonical_prospects_read_failed")

    if include_legacy_top_level:
        try:
            legacy_rows = _snapshot_documents(
                resolved_client.collection(LEGACY_TOP_LEVEL_PROSPECT_COLLECTION).stream()
            )
        except Exception:
            reason_codes.append("legacy_prospects_compatibility_read_failed")

    merged = list(canonical_rows)
    canonical_by_identity = {_identity_key(row): row for row in canonical_rows}
    legacy_only_count = 0
    conflict_count = 0
    for legacy in legacy_rows:
        identity = _identity_key(legacy)
        existing = canonical_by_identity.get(identity)
        if existing is None:
            merged.append(legacy)
            legacy_only_count += 1
            continue
        if not _materially_equal(existing, legacy):
            conflict_count += 1

    if legacy_rows:
        reason_codes.append("legacy_top_level_prospects_present")
    if conflict_count:
        reason_codes.append("legacy_prospect_conflicts_present")

    if any(code.endswith("read_failed") for code in reason_codes):
        state = "degraded"
    elif legacy_rows:
        state = "compatibility"
    else:
        state = "ready"

    if canonical_rows and legacy_only_count:
        source = "canonical_plus_legacy_read_only"
    elif canonical_rows:
        source = "canonical"
    elif legacy_rows:
        source = "legacy_top_level_read_only"
    else:
        source = "canonical"

    return ProspectAuthorityReadResult(
        documents=tuple(merged),
        state=state,
        source=source,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        canonical_count=len(canonical_rows),
        legacy_count=len(legacy_rows),
        legacy_only_count=legacy_only_count,
        conflict_count=conflict_count,
    )


def write_canonical_prospect(
    user_id: str,
    document_id: str,
    payload: Mapping[str, Any],
    *,
    client: Any = _CLIENT_UNSET,
) -> dict[str, Any]:
    """Write only the nested canonical path; no top-level or local dual-write."""

    resolved_client = _resolve_client(client)
    if resolved_client is None:
        raise FirestoreProspectAuthorityError("canonical prospect authority is unavailable")
    normalized = canonicalize_prospect_document(payload, document_id=document_id)
    try:
        canonical_prospect_collection(resolved_client, user_id).document(normalized["id"]).set(
            normalized,
            merge=True,
        )
    except Exception as exc:
        raise FirestoreProspectAuthorityError("canonical prospect write failed") from exc
    return normalized


def write_canonical_prospects(
    user_id: str,
    payloads: Iterable[Mapping[str, Any]],
    *,
    client: Any = _CLIENT_UNSET,
) -> tuple[dict[str, Any], ...]:
    """Atomically merge a bounded batch into the one nested prospect authority."""

    resolved_client = _resolve_client(client)
    if resolved_client is None:
        raise FirestoreProspectAuthorityError("canonical prospect authority is unavailable")
    collection = canonical_prospect_collection(resolved_client, user_id)
    normalized_rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        row = canonicalize_prospect_document(payload, document_id=str(payload.get("id") or ""))
        existing = by_id.get(row["id"])
        if existing is not None and not _materially_equal(existing, row):
            raise ValueError("batch contains conflicting duplicate prospect identifiers")
        if existing is None:
            by_id[row["id"]] = row
            normalized_rows.append(row)

    if not normalized_rows:
        raise ValueError("at least one prospect is required")

    try:
        batch = resolved_client.batch()
        for row in normalized_rows:
            batch.set(collection.document(row["id"]), row, merge=True)
        batch.commit()
    except Exception as exc:
        raise FirestoreProspectAuthorityError("canonical prospect batch write failed") from exc
    return tuple(normalized_rows)


def update_canonical_prospect(
    user_id: str,
    document_id: str,
    updates: Mapping[str, Any],
    *,
    client: Any = _CLIENT_UNSET,
) -> dict[str, Any]:
    """Update allowlisted operational fields without creating a second record shape."""

    resolved_client = _resolve_client(client)
    if resolved_client is None:
        raise FirestoreProspectAuthorityError("canonical prospect authority is unavailable")
    safe_document_id = _safe_document_id(document_id)
    allowed = {"status", "notes", "last_action"}
    bounded_updates = {key: value for key, value in updates.items() if key in allowed and value is not None}
    if not bounded_updates:
        raise ValueError("at least one allowlisted prospect field is required")
    try:
        document = canonical_prospect_collection(resolved_client, user_id).document(safe_document_id)
        snapshot = document.get()
        if not snapshot.exists:
            raise FirestoreProspectNotFoundError("canonical prospect was not found")
        current = canonicalize_prospect_document(snapshot.to_dict() or {}, document_id=safe_document_id)
        document.set(bounded_updates, merge=True)
    except FirestoreProspectNotFoundError:
        raise
    except Exception as exc:
        raise FirestoreProspectAuthorityError("canonical prospect update failed") from exc
    return canonicalize_prospect_document({**current, **bounded_updates}, document_id=safe_document_id)


def build_read_only_legacy_migration_plan(
    user_id: str,
    *,
    canonical_documents: Iterable[Mapping[str, Any]],
    legacy_documents: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic compatibility plan. This function never contacts Firestore."""

    normalized_user_id = _require_user_id(user_id)
    canonical_rows = [canonicalize_prospect_document(row, document_id=str(row.get("id") or "")) for row in canonical_documents]
    legacy_rows = [canonicalize_prospect_document(row, document_id=str(row.get("id") or "")) for row in legacy_documents]
    canonical_by_identity = {_identity_key(row): row for row in canonical_rows}

    mappings: list[dict[str, Any]] = []
    counts = {"create": 0, "already_present": 0, "conflict": 0}
    for legacy in sorted(legacy_rows, key=lambda row: str(row["id"])):
        identity = _identity_key(legacy)
        existing = canonical_by_identity.get(identity)
        if existing is None:
            action = "create"
            target_id = legacy["id"]
        elif _materially_equal(existing, legacy):
            action = "already_present"
            target_id = existing["id"]
        else:
            action = "conflict"
            target_id = existing["id"]
        counts[action] += 1
        mappings.append(
            {
                "legacy_document_id": legacy["id"],
                "legacy_path": f"{LEGACY_TOP_LEVEL_PROSPECT_COLLECTION}/{legacy['id']}",
                "canonical_document_id": target_id,
                "canonical_path": (
                    f"{CANONICAL_PROSPECT_PARENT_COLLECTION}/{normalized_user_id}/"
                    f"{CANONICAL_PROSPECT_COLLECTION}/{target_id}"
                ),
                "identity_key": identity,
                "action": action,
                "canonical_payload": legacy,
            }
        )

    return {
        "schema_version": PROSPECT_MIGRATION_PLAN_SCHEMA_VERSION,
        "mode": "read_only",
        "writes_performed": 0,
        "canonical_authority": (
            f"{CANONICAL_PROSPECT_PARENT_COLLECTION}/{normalized_user_id}/"
            f"{CANONICAL_PROSPECT_COLLECTION}"
        ),
        "legacy_authority": LEGACY_TOP_LEVEL_PROSPECT_COLLECTION,
        "counts": {**counts, "total": len(mappings)},
        "mappings": mappings,
    }
