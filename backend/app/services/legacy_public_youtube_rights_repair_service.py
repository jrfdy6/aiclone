from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import re
import sqlite3
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlsplit
import uuid

from app.services.integrated_system_store import (
    IntegratedSystemStore,
    _canonical_json,
    _utcnow,
)
from app.services.source_sharing_policy_service import (
    is_credential_free_public_url,
)


PLAN_SCHEMA = "legacy_public_youtube_rights_repair_plan/v1"
RECEIPT_SCHEMA = "legacy_public_youtube_rights_repair_receipt/v1"
ROLLBACK_BINDING_SCHEMA = "legacy_public_youtube_rights_repair_rollback_binding/v1"
ROLLBACK_RECEIPT_SCHEMA = "legacy_public_youtube_rights_repair_rollback_receipt/v1"
POLICY_ID = "owner_authorized_legacy_public_youtube_attribution/v1"
MAX_REPAIR_CANDIDATES = 100
TARGET_RIGHTS_STATE = "permitted"
REPAIR_METADATA_PATCH: dict[str, Any] = {
    "rights_basis": "legacy_qualified_public_youtube_capture",
    "owner_authorship_attested": False,
    "authorship_classification": "attributed_external",
    "rights_repair_version": PLAN_SCHEMA,
}
_REPAIR_METADATA_KEYS = frozenset(REPAIR_METADATA_PATCH)
_YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
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
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LegacyPublicYoutubeRightsRepairConflict(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_text(_canonical_json(value))


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
        if isinstance(value, Mapping) and _has_explicit_local_or_private_block(value):
            return True
    return False


def _is_exact_public_youtube_watch_url(value: Any) -> bool:
    if not is_credential_free_public_url(value):
        return False
    try:
        parsed = urlsplit(str(value).strip())
        query = parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return False
    video_ids = [item for key, item in query if key == "v" and item.strip()]
    return (
        parsed.scheme.casefold() in {"http", "https"}
        and (parsed.hostname or "").casefold().rstrip(".") in _YOUTUBE_HOSTS
        and parsed.path.rstrip("/") == "/watch"
        and len(video_ids) == 1
    )


def _validate_idempotency_key(value: str) -> str:
    key = str(value or "").strip()
    if not _IDEMPOTENCY_RE.fullmatch(key):
        raise ValueError("rights repair idempotency key is invalid")
    return key


def _event_id(idempotency_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))


class LegacyPublicYoutubeRightsRepairService:
    """Reversibly repair one narrowly defined legacy public-YouTube rights gap."""

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    @contextmanager
    def _read_only_connection(self) -> Any:
        database_input = self.store.database_path.expanduser()
        if database_input.is_symlink():
            raise ValueError("rights repair planning refuses a symlink database")
        database = database_input.resolve()
        if not database.is_file():
            raise ValueError("rights repair planning requires an existing canonical SQL file")
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
    def _qualified_discoveries(connection: Any, source_id: str) -> list[dict[str, Any]]:
        return [
            {
                "discovery_id": str(row["discovery_id"]),
                "origin": str(row["origin"]),
                "discovery_route": str(row["discovery_route"]),
                "external_ref": row["external_ref"],
                "relevance_state": str(row["relevance_state"]),
            }
            for row in connection.execute(
                """SELECT discovery_id,origin,discovery_route,external_ref,relevance_state
                FROM discovery_events
                WHERE source_id=? AND origin='youtube_watchlist'
                  AND discovery_route='legacy_source_intelligence_import'
                  AND relevance_state='qualified'
                ORDER BY discovery_id""",
                (source_id,),
            )
        ]

    @staticmethod
    def _transcript_artifact(connection: Any, artifact_id: Any) -> dict[str, Any] | None:
        if not artifact_id:
            return None
        row = connection.execute(
            """SELECT artifact_id,content_sha256,artifact_kind
            FROM artifacts WHERE artifact_id=?""",
            (artifact_id,),
        ).fetchone()
        return dict(row) if row else None

    def _candidate_or_reason(
        self, connection: Any, source: Mapping[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        if source.get("merged_into_source_id"):
            return None, "merged_alias"
        if source.get("source_kind") != "youtube_video":
            return None, "not_legacy_youtube_video"
        if source.get("rights_state") != "unknown":
            return None, "rights_not_unknown"
        if source.get("admissibility_state") != "admissible":
            return None, "not_admissible"
        if not _is_exact_public_youtube_watch_url(source.get("canonical_url")):
            return None, "url_not_exact_public_youtube_watch"
        try:
            metadata = _strict_metadata(source.get("metadata_json"))
        except ValueError:
            return None, "metadata_invalid"
        if metadata.get("legacy_status") not in {"digested", "routed", "reviewed"}:
            return None, "legacy_status_not_qualified"
        if metadata.get("source_type") not in {"transcript", "youtube_transcript"}:
            return None, "legacy_type_not_transcript"
        if "sharing" in metadata:
            return None, "sharing_already_declared"
        if _REPAIR_METADATA_KEYS.intersection(metadata):
            return None, "rights_repair_metadata_already_present"
        if _has_explicit_local_or_private_block(metadata):
            return None, "explicit_local_or_private_block"
        artifact = self._transcript_artifact(
            connection, source.get("transcript_artifact_id")
        )
        if not artifact or artifact.get("artifact_kind") != "source_transcript":
            return None, "qualified_transcript_artifact_missing"
        discoveries = self._qualified_discoveries(connection, str(source["source_id"]))
        if not discoveries:
            return None, "qualified_legacy_watchlist_route_missing"
        metadata_sha256 = _sha256_json(metadata)
        discovery_fingerprint = _sha256_json(discoveries)
        identity = {
            "source_id": source["source_id"],
            "canonical_identity_sha256": _sha256_text(
                str(source.get("canonical_identity") or "")
            ),
            "canonical_url_sha256": _sha256_text(str(source.get("canonical_url") or "")),
            "source_kind": source.get("source_kind"),
            "rights_state": source.get("rights_state"),
            "admissibility_state": source.get("admissibility_state"),
            "merged_into_source_id": source.get("merged_into_source_id"),
            "metadata_sha256": metadata_sha256,
            "transcript_artifact_id": artifact["artifact_id"],
            "transcript_content_sha256": artifact["content_sha256"],
            "qualified_discovery_fingerprint": discovery_fingerprint,
        }
        return (
            {
                "source_id": source["source_id"],
                "row_identity_sha256": _sha256_json(identity),
                "before_metadata_sha256": metadata_sha256,
                "before_rights_state": "unknown",
                "transcript_artifact_id": artifact["artifact_id"],
                "qualified_discovery_fingerprint": discovery_fingerprint,
                "target_rights_state": TARGET_RIGHTS_STATE,
                "metadata_patch": dict(REPAIR_METADATA_PATCH),
            },
            None,
        )

    def _scan(
        self, connection: Any, *, source_ids: Iterable[str] | None = None
    ) -> tuple[list[dict[str, Any]], Counter[str], bool]:
        requested = sorted(
            {str(item).strip() for item in source_ids or [] if str(item).strip()}
        )
        if requested:
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"SELECT * FROM sources WHERE source_id IN ({placeholders}) ORDER BY source_id",
                requested,
            ).fetchall()
            found = {str(row["source_id"]) for row in rows}
            missing = sorted(set(requested) - found)
            if missing:
                raise ValueError(f"unknown requested source ids: {','.join(missing[:5])}")
        else:
            rows = connection.execute(
                "SELECT * FROM sources WHERE rights_state='unknown' ORDER BY source_id"
            ).fetchall()
        candidates: list[dict[str, Any]] = []
        exclusions: Counter[str] = Counter()
        for row in rows:
            candidate, reason = self._candidate_or_reason(connection, dict(row))
            if candidate is None:
                exclusions[str(reason)] += 1
            else:
                candidates.append(candidate)
        return candidates, exclusions, bool(requested)

    @staticmethod
    def _build_plan(
        *,
        candidates: list[dict[str, Any]],
        exclusions: Mapping[str, int],
        requested: bool,
        generated_at: str,
        max_candidates: int,
        batch_index: int,
        batch_count: int,
        total_candidate_count: int,
        eligible_set_sha256: str,
    ) -> dict[str, Any]:
        plan: dict[str, Any] = {
            "schema_version": PLAN_SCHEMA,
            "generated_at": generated_at,
            "policy_id": POLICY_ID,
            "scope": "explicit_source_ids" if requested else "all_exact_eligible_sources",
            "max_candidates": max_candidates,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "excluded_counts": dict(sorted(exclusions.items())),
            "batch": {
                "index": batch_index,
                "count": batch_count,
                "total_candidate_count": total_candidate_count,
                "eligible_set_sha256": eligible_set_sha256,
            },
            "mutation_performed": False,
        }
        plan["plan_sha256"] = _sha256_json(plan)
        return plan

    def plan(
        self,
        *,
        source_ids: Iterable[str] | None = None,
        max_candidates: int = MAX_REPAIR_CANDIDATES,
    ) -> dict[str, Any]:
        if not 1 <= int(max_candidates) <= MAX_REPAIR_CANDIDATES:
            raise ValueError(
                f"max_candidates must be between 1 and {MAX_REPAIR_CANDIDATES}"
            )
        with self._read_only_connection() as connection:
            candidates, exclusions, requested = self._scan(
                connection, source_ids=source_ids
            )
        if len(candidates) > max_candidates:
            raise ValueError(
                "eligible source set exceeds max_candidates; use bounded batch planning"
            )
        eligible_set_sha256 = _sha256_json(
            [
                [candidate["source_id"], candidate["row_identity_sha256"]]
                for candidate in candidates
            ]
        )
        return self._build_plan(
            candidates=candidates,
            exclusions=exclusions,
            requested=requested,
            generated_at=_utcnow(),
            max_candidates=int(max_candidates),
            batch_index=1,
            batch_count=1,
            total_candidate_count=len(candidates),
            eligible_set_sha256=eligible_set_sha256,
        )

    def plan_batches(
        self,
        *,
        source_ids: Iterable[str] | None = None,
        max_candidates: int = MAX_REPAIR_CANDIDATES,
    ) -> list[dict[str, Any]]:
        if not 1 <= int(max_candidates) <= MAX_REPAIR_CANDIDATES:
            raise ValueError(
                f"max_candidates must be between 1 and {MAX_REPAIR_CANDIDATES}"
            )
        with self._read_only_connection() as connection:
            candidates, exclusions, requested = self._scan(
                connection, source_ids=source_ids
            )
        generated_at = _utcnow()
        eligible_set_sha256 = _sha256_json(
            [
                [candidate["source_id"], candidate["row_identity_sha256"]]
                for candidate in candidates
            ]
        )
        chunks = [
            candidates[index : index + int(max_candidates)]
            for index in range(0, len(candidates), int(max_candidates))
        ] or [[]]
        return [
            self._build_plan(
                candidates=chunk,
                exclusions=exclusions,
                requested=requested,
                generated_at=generated_at,
                max_candidates=int(max_candidates),
                batch_index=index,
                batch_count=len(chunks),
                total_candidate_count=len(candidates),
                eligible_set_sha256=eligible_set_sha256,
            )
            for index, chunk in enumerate(chunks, start=1)
        ]

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
            "batch",
            "mutation_performed",
            "plan_sha256",
        }
        if not isinstance(plan, Mapping) or set(plan) != expected:
            raise ValueError("legacy YouTube rights repair plan is not closed")
        normalized = dict(plan)
        supplied_sha256 = normalized.pop("plan_sha256", None)
        if (
            plan.get("schema_version") != PLAN_SCHEMA
            or plan.get("policy_id") != POLICY_ID
            or plan.get("mutation_performed") is not False
            or supplied_sha256 != _sha256_json(normalized)
        ):
            raise ValueError("legacy YouTube rights repair plan binding is invalid")
        candidates = plan.get("candidates")
        max_candidates = plan.get("max_candidates")
        batch = plan.get("batch")
        if (
            not isinstance(max_candidates, int)
            or not 1 <= max_candidates <= MAX_REPAIR_CANDIDATES
            or not isinstance(candidates, list)
            or len(candidates) != plan.get("candidate_count")
            or len(candidates) > max_candidates
            or not isinstance(batch, Mapping)
            or set(batch)
            != {"index", "count", "total_candidate_count", "eligible_set_sha256"}
            or not isinstance(batch.get("index"), int)
            or not isinstance(batch.get("count"), int)
            or not 1 <= batch["index"] <= batch["count"]
            or not isinstance(batch.get("total_candidate_count"), int)
            or batch["total_candidate_count"] < len(candidates)
            or not _SHA256_RE.fullmatch(str(batch.get("eligible_set_sha256") or ""))
        ):
            raise ValueError("legacy YouTube rights repair plan exceeds its bounds")
        fields = {
            "source_id",
            "row_identity_sha256",
            "before_metadata_sha256",
            "before_rights_state",
            "transcript_artifact_id",
            "qualified_discovery_fingerprint",
            "target_rights_state",
            "metadata_patch",
        }
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, Mapping) or set(candidate) != fields:
                raise ValueError("legacy YouTube rights repair candidate is not closed")
            source_id = str(candidate.get("source_id") or "")
            if not source_id or source_id in seen:
                raise ValueError("legacy YouTube rights repair candidate identity is invalid")
            seen.add(source_id)
            if (
                not _SHA256_RE.fullmatch(str(candidate.get("row_identity_sha256") or ""))
                or not _SHA256_RE.fullmatch(
                    str(candidate.get("before_metadata_sha256") or "")
                )
                or not _SHA256_RE.fullmatch(
                    str(candidate.get("qualified_discovery_fingerprint") or "")
                )
                or candidate.get("before_rights_state") != "unknown"
                or candidate.get("target_rights_state") != TARGET_RIGHTS_STATE
                or candidate.get("metadata_patch") != REPAIR_METADATA_PATCH
                or not str(candidate.get("transcript_artifact_id") or "")
            ):
                raise ValueError("legacy YouTube rights repair candidate binding is invalid")
        return dict(plan)

    @staticmethod
    def _existing_receipt(
        connection: Any,
        *,
        event_key: str,
        expected_plan_sha256: str,
        expected_receipt_sha256: str | None = None,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT payload_json FROM system_events WHERE idempotency_key=?",
            (event_key,),
        ).fetchone()
        if not row:
            return None
        payload = _strict_metadata(row["payload_json"])
        if payload.get("plan_sha256") != expected_plan_sha256:
            raise LegacyPublicYoutubeRightsRepairConflict(
                "rights repair idempotency key is bound to a different plan"
            )
        if (
            expected_receipt_sha256 is not None
            and payload.get("classification_receipt_sha256")
            != expected_receipt_sha256
        ):
            raise LegacyPublicYoutubeRightsRepairConflict(
                "rights rollback idempotency key is bound to a different receipt"
            )
        return payload

    def apply(
        self, *, plan: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        validated = self.validate_plan(plan)
        key = _validate_idempotency_key(idempotency_key)
        receipt_event_key = f"legacy-public-youtube-rights-repair-receipt:{key}"
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
                rollback_entries: list[dict[str, Any]] = []
                for candidate in validated["candidates"]:
                    source_id = candidate["source_id"]
                    row = connection.execute(
                        "SELECT * FROM sources WHERE source_id=?", (source_id,)
                    ).fetchone()
                    if not row:
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights repair source disappeared: {source_id}"
                        )
                    current_candidate, reason = self._candidate_or_reason(
                        connection, dict(row)
                    )
                    if current_candidate != dict(candidate):
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights repair source changed after planning: {source_id} ({reason or 'identity_drift'})"
                        )
                    before_metadata = _strict_metadata(row["metadata_json"])
                    repaired_metadata = {**before_metadata, **REPAIR_METADATA_PATCH}
                    before_sha256 = _sha256_json(before_metadata)
                    repaired_sha256 = _sha256_json(repaired_metadata)
                    connection.execute(
                        """UPDATE sources
                        SET rights_state=?,metadata_json=?,updated_at=?
                        WHERE source_id=? AND rights_state='unknown'""",
                        (
                            TARGET_RIGHTS_STATE,
                            _canonical_json(repaired_metadata),
                            applied_at,
                            source_id,
                        ),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0] != 1:
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights repair source was not updated: {source_id}"
                        )
                    source_event_key = f"legacy-public-youtube-rights-repaired:{key}:{source_id}"
                    connection.execute(
                        """INSERT INTO system_events(
                            event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                            actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            _event_id(source_event_key),
                            "source.legacy_public_youtube_rights_repaired",
                            "source",
                            source_id,
                            applied_at,
                            "governed_rights_repair",
                            _canonical_json(
                                {
                                    "schema_version": RECEIPT_SCHEMA,
                                    "policy_id": POLICY_ID,
                                    "plan_sha256": validated["plan_sha256"],
                                    "before_rights_state": "unknown",
                                    "repaired_rights_state": TARGET_RIGHTS_STATE,
                                    "before_metadata_sha256": before_sha256,
                                    "repaired_metadata_sha256": repaired_sha256,
                                    "owner_authorship_attested": False,
                                }
                            ),
                            _canonical_json(
                                {
                                    "qualified_discovery_fingerprint": candidate[
                                        "qualified_discovery_fingerprint"
                                    ],
                                    "eligibility_revalidated": True,
                                }
                            ),
                            _canonical_json([candidate["transcript_artifact_id"]]),
                            source_event_key,
                        ),
                    )
                    rollback_entries.append(
                        {
                            "source_id": source_id,
                            "before_rights_state": "unknown",
                            "repaired_rights_state": TARGET_RIGHTS_STATE,
                            "before_metadata_sha256": before_sha256,
                            "repaired_metadata_sha256": repaired_sha256,
                        }
                    )
                rollback = {
                    "schema_version": ROLLBACK_BINDING_SCHEMA,
                    "operation": "restore_unknown_rights_and_remove_exact_patch_if_unchanged",
                    "metadata_patch": dict(REPAIR_METADATA_PATCH),
                    "entries": rollback_entries,
                }
                receipt: dict[str, Any] = {
                    "schema_version": RECEIPT_SCHEMA,
                    "policy_id": POLICY_ID,
                    "plan_sha256": validated["plan_sha256"],
                    "eligible_set_sha256": validated["batch"]["eligible_set_sha256"],
                    "batch_index": validated["batch"]["index"],
                    "batch_count": validated["batch"]["count"],
                    "applied_at": applied_at,
                    "idempotency_key": key,
                    "repaired_count": len(rollback_entries),
                    "source_ids": [entry["source_id"] for entry in rollback_entries],
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
                        "source.legacy_public_youtube_rights_repair_receipt",
                        "source_rights_repair",
                        receipt["receipt_sha256"],
                        applied_at,
                        "governed_rights_repair",
                        _canonical_json(receipt),
                        _canonical_json(
                            {
                                "policy_id": POLICY_ID,
                                "plan_sha256": validated["plan_sha256"],
                                "eligible_set_sha256": validated["batch"][
                                    "eligible_set_sha256"
                                ],
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
            "eligible_set_sha256",
            "batch_index",
            "batch_count",
            "applied_at",
            "idempotency_key",
            "repaired_count",
            "source_ids",
            "rollback",
            "mutation_performed",
            "receipt_sha256",
        }
        if not isinstance(receipt, Mapping) or set(receipt) != expected:
            raise ValueError("legacy YouTube rights repair receipt is not closed")
        normalized = dict(receipt)
        supplied_sha256 = normalized.pop("receipt_sha256", None)
        rollback = receipt.get("rollback")
        if (
            receipt.get("schema_version") != RECEIPT_SCHEMA
            or receipt.get("policy_id") != POLICY_ID
            or supplied_sha256 != _sha256_json(normalized)
            or not _SHA256_RE.fullmatch(str(receipt.get("plan_sha256") or ""))
            or not _SHA256_RE.fullmatch(
                str(receipt.get("eligible_set_sha256") or "")
            )
            or not isinstance(rollback, Mapping)
            or set(rollback)
            != {"schema_version", "operation", "metadata_patch", "entries"}
            or rollback.get("schema_version") != ROLLBACK_BINDING_SCHEMA
            or rollback.get("operation")
            != "restore_unknown_rights_and_remove_exact_patch_if_unchanged"
            or rollback.get("metadata_patch") != REPAIR_METADATA_PATCH
            or not isinstance(receipt.get("batch_index"), int)
            or not isinstance(receipt.get("batch_count"), int)
            or not 1 <= receipt["batch_index"] <= receipt["batch_count"]
            or not isinstance(receipt.get("repaired_count"), int)
            or not 0 <= receipt["repaired_count"] <= MAX_REPAIR_CANDIDATES
            or not _IDEMPOTENCY_RE.fullmatch(
                str(receipt.get("idempotency_key") or "")
            )
        ):
            raise ValueError("legacy YouTube rights repair receipt binding is invalid")
        entries = rollback.get("entries")
        source_ids = receipt.get("source_ids")
        if (
            not isinstance(entries, list)
            or not isinstance(source_ids, list)
            or len(entries) != receipt.get("repaired_count")
            or [entry.get("source_id") for entry in entries] != source_ids
            or len(set(source_ids)) != len(source_ids)
            or receipt.get("mutation_performed") is not bool(entries)
        ):
            raise ValueError("legacy YouTube rights rollback binding is invalid")
        fields = {
            "source_id",
            "before_rights_state",
            "repaired_rights_state",
            "before_metadata_sha256",
            "repaired_metadata_sha256",
        }
        for entry in entries:
            if not isinstance(entry, Mapping) or set(entry) != fields:
                raise ValueError("legacy YouTube rights rollback entry is not closed")
            if (
                not str(entry.get("source_id") or "")
                or entry.get("before_rights_state") != "unknown"
                or entry.get("repaired_rights_state") != TARGET_RIGHTS_STATE
                or not _SHA256_RE.fullmatch(
                    str(entry.get("before_metadata_sha256") or "")
                )
                or not _SHA256_RE.fullmatch(
                    str(entry.get("repaired_metadata_sha256") or "")
                )
            ):
                raise ValueError("legacy YouTube rights rollback entry is invalid")
        return dict(receipt)

    def rollback(
        self, *, receipt: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        validated = self.validate_receipt(receipt)
        key = _validate_idempotency_key(idempotency_key)
        receipt_event_key = f"legacy-public-youtube-rights-rollback-receipt:{key}"
        self.store.migrate()
        with self.store.connection() as connection:
            existing = self._existing_receipt(
                connection,
                event_key=receipt_event_key,
                expected_plan_sha256=validated["plan_sha256"],
                expected_receipt_sha256=validated["receipt_sha256"],
            )
            if existing is not None:
                return existing
            connection.execute("BEGIN IMMEDIATE")
            try:
                rolled_back_at = _utcnow()
                source_ids: list[str] = []
                for entry in validated["rollback"]["entries"]:
                    source_id = entry["source_id"]
                    row = connection.execute(
                        "SELECT rights_state,metadata_json FROM sources WHERE source_id=?",
                        (source_id,),
                    ).fetchone()
                    if not row:
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights rollback source disappeared: {source_id}"
                        )
                    current_metadata = _strict_metadata(row["metadata_json"])
                    if (
                        row["rights_state"] != entry["repaired_rights_state"]
                        or _sha256_json(current_metadata)
                        != entry["repaired_metadata_sha256"]
                        or any(
                            current_metadata.get(patch_key) != patch_value
                            for patch_key, patch_value in REPAIR_METADATA_PATCH.items()
                        )
                    ):
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights rollback source changed after repair: {source_id}"
                        )
                    restored_metadata = dict(current_metadata)
                    for patch_key in REPAIR_METADATA_PATCH:
                        restored_metadata.pop(patch_key, None)
                    if _sha256_json(restored_metadata) != entry["before_metadata_sha256"]:
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights rollback cannot reconstruct prior metadata: {source_id}"
                        )
                    connection.execute(
                        """UPDATE sources
                        SET rights_state=?,metadata_json=?,updated_at=?
                        WHERE source_id=? AND rights_state=?""",
                        (
                            entry["before_rights_state"],
                            _canonical_json(restored_metadata),
                            rolled_back_at,
                            source_id,
                            entry["repaired_rights_state"],
                        ),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0] != 1:
                        raise LegacyPublicYoutubeRightsRepairConflict(
                            f"rights rollback source was not restored: {source_id}"
                        )
                    source_event_key = f"legacy-public-youtube-rights-rolled-back:{key}:{source_id}"
                    connection.execute(
                        """INSERT INTO system_events(
                            event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                            actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            _event_id(source_event_key),
                            "source.legacy_public_youtube_rights_rolled_back",
                            "source",
                            source_id,
                            rolled_back_at,
                            "governed_rights_repair",
                            _canonical_json(
                                {
                                    "classification_receipt_sha256": validated[
                                        "receipt_sha256"
                                    ],
                                    "restored_rights_state": entry[
                                        "before_rights_state"
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
                        "source.legacy_public_youtube_rights_rollback_receipt",
                        "source_rights_repair",
                        rollback_receipt["receipt_sha256"],
                        rolled_back_at,
                        "governed_rights_repair",
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
