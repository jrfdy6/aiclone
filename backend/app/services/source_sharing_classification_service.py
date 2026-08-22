from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import re
import sqlite3
from typing import Any, Iterable, Mapping
import uuid

from app.services.integrated_system_store import (
    IntegratedSystemStore,
    _canonical_json,
    _utcnow,
)
from app.services.source_sharing_policy_service import (
    is_credential_free_public_url,
    source_classification_sharing,
    validate_remote_source_sharing,
)


PLAN_SCHEMA = "source_sharing_classification_plan/v1"
RECEIPT_SCHEMA = "source_sharing_classification_receipt/v1"
ROLLBACK_BINDING_SCHEMA = "source_sharing_classification_rollback_binding/v1"
ROLLBACK_RECEIPT_SCHEMA = "source_sharing_classification_rollback_receipt/v1"
POLICY_ID = "defensible_public_source_sharing/v1"
MAX_CLASSIFICATION_CANDIDATES = 100
PUBLIC_ORIGINS = frozenset(
    {
        "youtube_watchlist",
        "youtube_playlist",
        "rss",
        "reddit",
        "linkedin",
        "podcast",
    }
)
_PRIVATE_STATES = frozenset(
    {
        "blocked",
        "confidential",
        "do_not_share",
        "local",
        "local_only",
        "never_share",
        "private",
        "restricted",
        "sensitive",
    }
)
_PRIVATE_STATE_KEYS = frozenset(
    {
        "classification",
        "content_classification",
        "privacy",
        "privacy_classification",
        "privacy_state",
        "scope",
        "sharing_scope",
        "state",
        "visibility",
    }
)
_REMOTE_BOOLEAN_KEYS = frozenset(
    {"allow_remote", "cloud_shareable", "content_shareable", "remote_shareable"}
)
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


class SourceSharingClassificationConflict(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _strict_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("source metadata is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("source metadata is not a JSON object")
    return parsed


def _has_explicit_local_or_private_block(metadata: Mapping[str, Any]) -> bool:
    if metadata.get("private") is True or metadata.get("local_only") is True:
        return True
    for key in _REMOTE_BOOLEAN_KEYS:
        if key in metadata and metadata.get(key) is False:
            return True
    for key in _PRIVATE_STATE_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and "_".join(value.casefold().split()) in _PRIVATE_STATES:
            return True
        if isinstance(value, Mapping):
            if _has_explicit_local_or_private_block(value):
                return True
    privacy = metadata.get("privacy")
    return isinstance(privacy, Mapping) and _has_explicit_local_or_private_block(privacy)


def _eligibility_reason(
    source: Mapping[str, Any], *, origins: set[str]
) -> str | None:
    if source.get("merged_into_source_id"):
        return "merged_alias"
    if source.get("rights_state") != "permitted":
        return "rights_not_permitted"
    if source.get("admissibility_state") != "admissible":
        return "not_admissible"
    if not origins.intersection(PUBLIC_ORIGINS):
        return "no_public_origin"
    if not is_credential_free_public_url(source.get("canonical_url")):
        return "url_not_public_or_credential_free"
    try:
        metadata = _strict_metadata(source.get("metadata_json"))
    except ValueError:
        return "metadata_invalid"
    if "sharing" in metadata:
        try:
            validate_remote_source_sharing(metadata["sharing"])
        except ValueError:
            return "explicit_sharing_boundary"
        return "already_classified"
    if _has_explicit_local_or_private_block(metadata):
        return "explicit_local_or_private_block"
    return None


def _candidate(source: Mapping[str, Any], *, origins: set[str]) -> dict[str, Any]:
    metadata = _strict_metadata(source.get("metadata_json"))
    identity = {
        "source_id": source["source_id"],
        "canonical_url_sha256": _sha256_text(str(source.get("canonical_url") or "")),
        "rights_state": source.get("rights_state"),
        "admissibility_state": source.get("admissibility_state"),
        "merged_into_source_id": source.get("merged_into_source_id"),
        "metadata_sha256": _sha256_json(metadata),
        "public_origins": sorted(origins.intersection(PUBLIC_ORIGINS)),
    }
    return {
        "source_id": source["source_id"],
        "row_identity_sha256": _sha256_json(identity),
        "before_metadata_sha256": identity["metadata_sha256"],
        "public_origins": identity["public_origins"],
        "target_sharing": source_classification_sharing(),
    }


def _event_id(idempotency_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))


def _validate_idempotency_key(value: str) -> str:
    key = str(value or "").strip()
    if not _IDEMPOTENCY_RE.fullmatch(key):
        raise ValueError("classification idempotency key is invalid")
    return key


class SourceSharingClassificationService:
    """Plan, apply, and reversibly classify a bounded public-source subset."""

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    @contextmanager
    def _read_only_connection(self) -> Any:
        database_input = self.store.database_path.expanduser()
        if database_input.is_symlink():
            raise ValueError("classification planning refuses a symlink database")
        database = database_input.resolve()
        if not database.is_file():
            raise ValueError("classification planning requires an existing canonical SQL file")
        connection = sqlite3.connect(
            f"{database.as_uri()}?mode=ro", uri=True, timeout=10, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _origins(connection: Any, source_id: str) -> set[str]:
        return {
            str(row["origin"])
            for row in connection.execute(
                "SELECT DISTINCT origin FROM discovery_events WHERE source_id=?",
                (source_id,),
            )
        }

    def plan(
        self,
        *,
        source_ids: Iterable[str] | None = None,
        max_candidates: int = MAX_CLASSIFICATION_CANDIDATES,
    ) -> dict[str, Any]:
        if not 1 <= int(max_candidates) <= MAX_CLASSIFICATION_CANDIDATES:
            raise ValueError(
                f"max_candidates must be between 1 and {MAX_CLASSIFICATION_CANDIDATES}"
            )
        requested = sorted({str(item).strip() for item in source_ids or [] if str(item).strip()})
        if len(requested) > max_candidates:
            raise ValueError("requested source set exceeds the classification bound")
        with self._read_only_connection() as connection:
            if requested:
                placeholders = ",".join("?" for _ in requested)
                rows = connection.execute(
                    f"SELECT * FROM sources WHERE source_id IN ({placeholders}) ORDER BY source_id",
                    requested,
                ).fetchall()
                found = {str(row["source_id"]) for row in rows}
                missing = sorted(set(requested) - found)
                if missing:
                    raise ValueError(
                        f"unknown requested source ids: {','.join(missing[:5])}"
                    )
            else:
                rows = connection.execute(
                    "SELECT * FROM sources ORDER BY source_id"
                ).fetchall()
            candidates: list[dict[str, Any]] = []
            exclusions: Counter[str] = Counter()
            for raw_row in rows:
                source = dict(raw_row)
                origins = self._origins(connection, source["source_id"])
                reason = _eligibility_reason(source, origins=origins)
                if reason:
                    exclusions[reason] += 1
                    continue
                candidates.append(_candidate(source, origins=origins))
        if len(candidates) > max_candidates:
            raise ValueError(
                "eligible source set exceeds max_candidates; provide explicit source ids"
            )
        plan: dict[str, Any] = {
            "schema_version": PLAN_SCHEMA,
            "generated_at": _utcnow(),
            "policy_id": POLICY_ID,
            "scope": "explicit_source_ids" if requested else "all_policy_eligible_sources",
            "max_candidates": int(max_candidates),
            "candidate_count": len(candidates),
            "candidates": candidates,
            "excluded_counts": dict(sorted(exclusions.items())),
            "mutation_performed": False,
        }
        plan["plan_sha256"] = _sha256_json(plan)
        return plan

    @staticmethod
    def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
        expected = {
            "schema_version",
            "generated_at",
            "policy_id",
            "scope",
            "max_candidates",
            "candidate_count",
            "candidates",
            "excluded_counts",
            "mutation_performed",
            "plan_sha256",
        }
        if not isinstance(plan, Mapping) or set(plan) != expected:
            raise ValueError("source sharing classification plan is not closed")
        normalized = dict(plan)
        supplied_sha = normalized.pop("plan_sha256", None)
        if (
            plan.get("schema_version") != PLAN_SCHEMA
            or plan.get("policy_id") != POLICY_ID
            or plan.get("mutation_performed") is not False
            or supplied_sha != _sha256_json(normalized)
        ):
            raise ValueError("source sharing classification plan binding is invalid")
        candidates = plan.get("candidates")
        max_candidates = plan.get("max_candidates")
        if (
            not isinstance(max_candidates, int)
            or not 1 <= max_candidates <= MAX_CLASSIFICATION_CANDIDATES
            or not isinstance(candidates, list)
            or len(candidates) != plan.get("candidate_count")
            or len(candidates) > max_candidates
        ):
            raise ValueError("source sharing classification plan exceeds its bounds")
        candidate_fields = {
            "source_id",
            "row_identity_sha256",
            "before_metadata_sha256",
            "public_origins",
            "target_sharing",
        }
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, Mapping) or set(candidate) != candidate_fields:
                raise ValueError("source sharing classification candidate is not closed")
            source_id = str(candidate.get("source_id") or "")
            if not source_id or source_id in seen:
                raise ValueError("source sharing classification candidate identity is invalid")
            seen.add(source_id)
            if (
                len(str(candidate.get("row_identity_sha256") or "")) != 64
                or len(str(candidate.get("before_metadata_sha256") or "")) != 64
                or not isinstance(candidate.get("public_origins"), list)
                or not set(candidate["public_origins"]).issubset(PUBLIC_ORIGINS)
                or validate_remote_source_sharing(candidate.get("target_sharing"))
                != source_classification_sharing()
            ):
                raise ValueError("source sharing classification candidate binding is invalid")
        return dict(plan)

    def _existing_receipt(
        self, connection: Any, *, event_key: str, expected_plan_sha256: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT payload_json FROM system_events WHERE idempotency_key=?",
            (event_key,),
        ).fetchone()
        if not row:
            return None
        payload = _metadata(row["payload_json"])
        if payload.get("plan_sha256") != expected_plan_sha256:
            raise SourceSharingClassificationConflict(
                "classification idempotency key is bound to a different plan"
            )
        return payload

    def apply(
        self, *, plan: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        validated = self.validate_plan(plan)
        key = _validate_idempotency_key(idempotency_key)
        receipt_event_key = f"source-sharing-classification-receipt:{key}"
        target_sharing = source_classification_sharing()
        self.store.migrate()
        with self.store.connection() as connection:
            existing = self._existing_receipt(
                connection,
                event_key=receipt_event_key,
                expected_plan_sha256=validated["plan_sha256"],
            )
            if existing is not None:
                return existing
            connection.execute("BEGIN IMMEDIATE")
            try:
                applied_at = _utcnow()
                rollback_entries: list[dict[str, str]] = []
                for candidate in validated["candidates"]:
                    source_id = candidate["source_id"]
                    row = connection.execute(
                        "SELECT * FROM sources WHERE source_id=?", (source_id,)
                    ).fetchone()
                    if not row:
                        raise SourceSharingClassificationConflict(
                            f"classification source disappeared: {source_id}"
                        )
                    source = dict(row)
                    origins = self._origins(connection, source_id)
                    reason = _eligibility_reason(source, origins=origins)
                    current_candidate = (
                        _candidate(source, origins=origins) if reason is None else None
                    )
                    if current_candidate != dict(candidate):
                        raise SourceSharingClassificationConflict(
                            f"classification source changed after planning: {source_id}"
                        )
                    before_metadata = _strict_metadata(source["metadata_json"])
                    before_sha = _sha256_json(before_metadata)
                    after_metadata = {**before_metadata, "sharing": target_sharing}
                    after_sha = _sha256_json(after_metadata)
                    connection.execute(
                        "UPDATE sources SET metadata_json=?,updated_at=? WHERE source_id=?",
                        (_canonical_json(after_metadata), applied_at, source_id),
                    )
                    source_event_key = f"source-sharing-classified:{key}:{source_id}"
                    connection.execute(
                        """INSERT INTO system_events(
                            event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                            actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            _event_id(source_event_key),
                            "source.sharing_classified",
                            "source",
                            source_id,
                            applied_at,
                            "source_sharing_policy",
                            _canonical_json(
                                {
                                    "schema_version": RECEIPT_SCHEMA,
                                    "policy_id": POLICY_ID,
                                    "plan_sha256": validated["plan_sha256"],
                                    "before_metadata_sha256": before_sha,
                                    "after_metadata_sha256": after_sha,
                                    "sharing": target_sharing,
                                }
                            ),
                            _canonical_json(
                                {
                                    "public_origins": candidate["public_origins"],
                                    "eligibility_revalidated": True,
                                }
                            ),
                            "[]",
                            source_event_key,
                        ),
                    )
                    rollback_entries.append(
                        {
                            "source_id": source_id,
                            "before_metadata_sha256": before_sha,
                            "classified_metadata_sha256": after_sha,
                        }
                    )
                rollback = {
                    "schema_version": ROLLBACK_BINDING_SCHEMA,
                    "operation": "remove_exact_classification_if_unchanged",
                    "entries": rollback_entries,
                }
                receipt: dict[str, Any] = {
                    "schema_version": RECEIPT_SCHEMA,
                    "policy_id": POLICY_ID,
                    "plan_sha256": validated["plan_sha256"],
                    "applied_at": applied_at,
                    "idempotency_key": key,
                    "classified_count": len(rollback_entries),
                    "source_ids": [item["source_id"] for item in rollback_entries],
                    "sharing": target_sharing,
                    "rollback": rollback,
                    "mutation_performed": bool(rollback_entries),
                }
                receipt["receipt_sha256"] = _sha256_json(receipt)
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                        actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        _event_id(receipt_event_key),
                        "source.sharing_classification_receipt",
                        "source_sharing_classification",
                        receipt["receipt_sha256"],
                        applied_at,
                        "source_sharing_policy",
                        _canonical_json(receipt),
                        _canonical_json(
                            {
                                "policy_id": POLICY_ID,
                                "plan_sha256": validated["plan_sha256"],
                            }
                        ),
                        "[]",
                        receipt_event_key,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return receipt

    @staticmethod
    def validate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
        expected = {
            "schema_version",
            "policy_id",
            "plan_sha256",
            "applied_at",
            "idempotency_key",
            "classified_count",
            "source_ids",
            "sharing",
            "rollback",
            "mutation_performed",
            "receipt_sha256",
        }
        if not isinstance(receipt, Mapping) or set(receipt) != expected:
            raise ValueError("source sharing classification receipt is not closed")
        normalized = dict(receipt)
        supplied_sha = normalized.pop("receipt_sha256", None)
        rollback = receipt.get("rollback")
        if (
            receipt.get("schema_version") != RECEIPT_SCHEMA
            or receipt.get("policy_id") != POLICY_ID
            or supplied_sha != _sha256_json(normalized)
            or validate_remote_source_sharing(receipt.get("sharing"))
            != source_classification_sharing()
            or not isinstance(rollback, Mapping)
            or set(rollback) != {"schema_version", "operation", "entries"}
            or rollback.get("schema_version") != ROLLBACK_BINDING_SCHEMA
            or rollback.get("operation")
            != "remove_exact_classification_if_unchanged"
        ):
            raise ValueError("source sharing classification receipt binding is invalid")
        entries = rollback.get("entries")
        source_ids = receipt.get("source_ids")
        if (
            not isinstance(entries, list)
            or not isinstance(source_ids, list)
            or len(entries) != receipt.get("classified_count")
            or [entry.get("source_id") for entry in entries] != source_ids
        ):
            raise ValueError("source sharing rollback binding is invalid")
        for entry in entries:
            if not isinstance(entry, Mapping) or set(entry) != {
                "source_id",
                "before_metadata_sha256",
                "classified_metadata_sha256",
            }:
                raise ValueError("source sharing rollback entry is not closed")
            if any(
                len(str(entry.get(field) or "")) != 64
                for field in ("before_metadata_sha256", "classified_metadata_sha256")
            ):
                raise ValueError("source sharing rollback entry binding is invalid")
        return dict(receipt)

    def rollback(
        self, *, receipt: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        validated = self.validate_receipt(receipt)
        key = _validate_idempotency_key(idempotency_key)
        receipt_event_key = f"source-sharing-classification-rollback-receipt:{key}"
        self.store.migrate()
        with self.store.connection() as connection:
            existing = self._existing_receipt(
                connection,
                event_key=receipt_event_key,
                expected_plan_sha256=validated["plan_sha256"],
            )
            if existing is not None:
                if existing.get("classification_receipt_sha256") != validated["receipt_sha256"]:
                    raise SourceSharingClassificationConflict(
                        "rollback idempotency key is bound to a different receipt"
                    )
                return existing
            connection.execute("BEGIN IMMEDIATE")
            try:
                rolled_back_at = _utcnow()
                source_ids: list[str] = []
                for entry in validated["rollback"]["entries"]:
                    source_id = entry["source_id"]
                    row = connection.execute(
                        "SELECT metadata_json FROM sources WHERE source_id=?", (source_id,)
                    ).fetchone()
                    if not row:
                        raise SourceSharingClassificationConflict(
                            f"rollback source disappeared: {source_id}"
                        )
                    current_metadata = _strict_metadata(row["metadata_json"])
                    if _sha256_json(current_metadata) != entry["classified_metadata_sha256"]:
                        raise SourceSharingClassificationConflict(
                            f"rollback source changed after classification: {source_id}"
                        )
                    if validate_remote_source_sharing(current_metadata.get("sharing")) != validated["sharing"]:
                        raise SourceSharingClassificationConflict(
                            f"rollback source sharing declaration changed: {source_id}"
                        )
                    restored_metadata = dict(current_metadata)
                    restored_metadata.pop("sharing", None)
                    if _sha256_json(restored_metadata) != entry["before_metadata_sha256"]:
                        raise SourceSharingClassificationConflict(
                            f"rollback source no longer reconstructs its prior state: {source_id}"
                        )
                    connection.execute(
                        "UPDATE sources SET metadata_json=?,updated_at=? WHERE source_id=?",
                        (_canonical_json(restored_metadata), rolled_back_at, source_id),
                    )
                    source_event_key = f"source-sharing-classification-rollback:{key}:{source_id}"
                    connection.execute(
                        """INSERT INTO system_events(
                            event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                            actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            _event_id(source_event_key),
                            "source.sharing_classification_rolled_back",
                            "source",
                            source_id,
                            rolled_back_at,
                            "source_sharing_policy",
                            _canonical_json(
                                {
                                    "classification_receipt_sha256": validated[
                                        "receipt_sha256"
                                    ],
                                    "restored_metadata_sha256": entry[
                                        "before_metadata_sha256"
                                    ],
                                }
                            ),
                            _canonical_json({"rollback_revalidated": True}),
                            "[]",
                            source_event_key,
                        ),
                    )
                    source_ids.append(source_id)
                rollback_receipt: dict[str, Any] = {
                    "schema_version": ROLLBACK_RECEIPT_SCHEMA,
                    "policy_id": POLICY_ID,
                    "plan_sha256": validated["plan_sha256"],
                    "classification_receipt_sha256": validated["receipt_sha256"],
                    "rolled_back_at": rolled_back_at,
                    "idempotency_key": key,
                    "rolled_back_count": len(source_ids),
                    "source_ids": source_ids,
                    "mutation_performed": bool(source_ids),
                }
                rollback_receipt["receipt_sha256"] = _sha256_json(rollback_receipt)
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                        actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        _event_id(receipt_event_key),
                        "source.sharing_classification_rollback_receipt",
                        "source_sharing_classification",
                        rollback_receipt["receipt_sha256"],
                        rolled_back_at,
                        "source_sharing_policy",
                        _canonical_json(rollback_receipt),
                        _canonical_json(
                            {
                                "classification_receipt_sha256": validated[
                                    "receipt_sha256"
                                ]
                            }
                        ),
                        "[]",
                        receipt_event_key,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return rollback_receipt
