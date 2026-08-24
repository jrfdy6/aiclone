from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Mapping

from app.services.content_lifecycle_service import PrivateContentArtifactStore
from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow
from app.services.source_authorship_policy_service import conservative_combined_rights


SOURCE_GATE_RECEIPT_SCHEMA = "source_gate_receipt/v2"


class SourceProcessingService:
    def __init__(self, store: IntegratedSystemStore, artifacts: PrivateContentArtifactStore) -> None:
        self.store = store
        self.artifacts = artifacts
        self.store.migrate()

    def qualify(
        self,
        *,
        discovery_id: str,
        relevance_state: str,
        admissibility_state: str,
        reason: str = "policy_evaluation",
        policy_name: str = "canonical_source_gate",
        policy_version: str = "1.0.0",
    ) -> dict[str, Any]:
        if relevance_state not in {"qualified", "backlog", "rejected"} or admissibility_state not in {"admissible", "restricted", "blocked"}:
            raise ValueError("invalid source gate state")
        with self.store.connection() as connection:
            discovery = connection.execute("SELECT * FROM discovery_events WHERE discovery_id=?", (discovery_id,)).fetchone()
            if not discovery:
                raise ValueError("unknown discovery")
            source = connection.execute("SELECT * FROM sources WHERE source_id=?", (discovery["source_id"],)).fetchone()
            admissibility_rank = {"pending": 0, "admissible": 1, "restricted": 2, "blocked": 3}
            effective_admissibility_state = admissibility_state
            if admissibility_rank[source["admissibility_state"]] > admissibility_rank[admissibility_state]:
                effective_admissibility_state = source["admissibility_state"]
            authorized = (
                relevance_state == "qualified"
                and effective_admissibility_state == "admissible"
                and source["rights_state"] in {"permitted", "owner_controlled"}
            )
            evaluation_fingerprint = hashlib.sha256(
                f"{policy_name}\n{policy_version}\n{reason}".encode("utf-8")
            ).hexdigest()[:16]
            idempotency_key = (
                f"source-gate:v2:{discovery_id}:{relevance_state}:{admissibility_state}:"
                f"{policy_version}:{evaluation_fingerprint}"
            )
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))
            payload_json = _canonical_json(
                {
                    "admissibility_state": effective_admissibility_state,
                    "requested_admissibility_state": admissibility_state,
                    "discovery_id": discovery_id,
                    "expensive_processing_authorized": authorized,
                    "receipt_schema": SOURCE_GATE_RECEIPT_SCHEMA,
                    "relevance_state": relevance_state,
                    "rights_state": source["rights_state"],
                }
            )
            provenance_json = _canonical_json(
                {
                    "policy_name": policy_name,
                    "policy_version": policy_version,
                    "reason": reason,
                    "receipt_schema": SOURCE_GATE_RECEIPT_SCHEMA,
                }
            )
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("UPDATE discovery_events SET relevance_state=? WHERE discovery_id=?", (relevance_state, discovery_id))
                connection.execute(
                    "UPDATE sources SET admissibility_state=?,updated_at=? WHERE source_id=?",
                    (effective_admissibility_state, _utcnow(), discovery["source_id"]),
                )
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                        payload_json,provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        event_id,
                        "source.gate_evaluated",
                        "source",
                        discovery["source_id"],
                        _utcnow(),
                        "source_gate_policy",
                        payload_json,
                        provenance_json,
                        "[]",
                        idempotency_key,
                    ),
                )
                event = connection.execute(
                    "SELECT * FROM system_events WHERE idempotency_key=?", (idempotency_key,)
                ).fetchone()
                if not event or event["payload_json"] != payload_json or event["provenance_json"] != provenance_json:
                    raise ValueError("source gate idempotency conflict")
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return {
            "source_id": discovery["source_id"],
            "discovery_id": discovery_id,
            "relevance_state": relevance_state,
            "admissibility_state": effective_admissibility_state,
            "expensive_processing_authorized": authorized,
            "gate_event_id": event["event_id"],
        }

    def processing_decision(
        self, *, source_id: str, discovery_id: str, capture_kind: str = "transcript"
    ) -> dict[str, Any]:
        if capture_kind not in {"raw", "transcript"}:
            raise ValueError("capture kind must be raw or transcript")
        column = "transcript_artifact_id" if capture_kind == "transcript" else "raw_artifact_id"
        with self.store.connection() as connection:
            row = connection.execute(
                """SELECT s.*,d.relevance_state,d.source_id AS discovery_source_id
                   FROM sources s JOIN discovery_events d ON d.discovery_id=?
                   WHERE s.source_id=?""",
                (discovery_id, source_id),
            ).fetchone()
            if not row or row["discovery_source_id"] != source_id:
                raise ValueError("unknown source discovery relationship")
            authorized = (
                row["relevance_state"] == "qualified"
                and row["admissibility_state"] == "admissible"
                and row["rights_state"] in {"permitted", "owner_controlled"}
            )
            existing_artifact_id = row[column]
        return {
            "source_id": source_id,
            "discovery_id": discovery_id,
            "capture_kind": capture_kind,
            "expensive_processing_authorized": authorized,
            "capture_required": bool(authorized and not existing_artifact_id),
            "existing_artifact_id": existing_artifact_id,
            "state": (
                "reuse_existing_capture"
                if existing_artifact_id
                else "ready_for_capture"
                if authorized
                else "not_authorized"
            ),
        }

    def attach_captured_text(self, *, source_id: str, text: str, capture_kind: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if capture_kind not in {"raw", "transcript"}:
            raise ValueError("capture kind must be raw or transcript")
        if not text.strip():
            raise ValueError("captured text is empty")
        column = "transcript_artifact_id" if capture_kind == "transcript" else "raw_artifact_id"
        with self.store.connection() as connection:
            source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
            if not source:
                raise ValueError("unknown source")
            source = self._resolve_active_source(connection, source)
            source_id = source["source_id"]
            qualified = connection.execute("SELECT EXISTS(SELECT 1 FROM discovery_events WHERE source_id=? AND relevance_state='qualified')", (source_id,)).fetchone()[0]
            if (
                not qualified
                or source["admissibility_state"] != "admissible"
                or source["rights_state"] not in {"permitted", "owner_controlled"}
            ):
                raise ValueError("source has not passed relevance, admissibility, and rights gates")
            existing_id = source[column]
            if existing_id:
                existing = connection.execute("SELECT * FROM artifacts WHERE artifact_id=?", (existing_id,)).fetchone()
                connection.execute("BEGIN IMMEDIATE")
                try:
                    canonical_source_id, merged_source_ids = self._merge_exact_duplicates(
                        connection,
                        source_id=source_id,
                        content_sha256=existing["content_sha256"],
                    )
                    self._record_capture_event(
                        connection,
                        source_id=canonical_source_id,
                        capture_kind=capture_kind,
                        artifact=dict(existing),
                    )
                    connection.execute("COMMIT")
                except Exception:
                    connection.execute("ROLLBACK")
                    raise
                return {
                    "source_id": canonical_source_id,
                    "artifact": dict(existing),
                    "reused": True,
                    "merged_source_ids": merged_source_ids,
                }
        artifact_kind = f"source_{capture_kind}"
        content_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self.store.connection() as connection:
            artifact_preexisted = bool(
                connection.execute(
                    "SELECT 1 FROM artifacts WHERE content_sha256=? AND artifact_kind=?",
                    (content_sha256, artifact_kind),
                ).fetchone()
            )
        artifact = self.artifacts.write_text(text, artifact_kind=artifact_kind)
        artifact_row = self.store.put_artifact(artifact_kind=artifact_kind, metadata={"private": True, **dict(metadata or {})}, **artifact)
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = connection.execute(f"SELECT {column} FROM sources WHERE source_id=?", (source_id,)).fetchone()[0]
                if current and current != artifact_row["artifact_id"]:
                    raise ValueError("canonical source already has a different captured artifact")
                connection.execute(f"UPDATE sources SET {column}=?,content_sha256=?,captured_at=?,updated_at=? WHERE source_id=?", (artifact_row["artifact_id"], artifact_row["content_sha256"], _utcnow(), _utcnow(), source_id))
                canonical_source_id, merged_source_ids = self._merge_exact_duplicates(
                    connection,
                    source_id=source_id,
                    content_sha256=artifact_row["content_sha256"],
                )
                self._record_capture_event(
                    connection,
                    source_id=canonical_source_id,
                    capture_kind=capture_kind,
                    artifact=artifact_row,
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return {
            "source_id": canonical_source_id,
            "artifact": artifact_row,
            "reused": artifact_preexisted or bool(merged_source_ids),
            "merged_source_ids": merged_source_ids,
        }

    @staticmethod
    def _resolve_active_source(connection: Any, source: Any) -> Any:
        visited: set[str] = set()
        while source["merged_into_source_id"]:
            if source["source_id"] in visited:
                raise ValueError("canonical source alias cycle detected")
            visited.add(source["source_id"])
            source = connection.execute(
                "SELECT * FROM sources WHERE source_id=?", (source["merged_into_source_id"],)
            ).fetchone()
            if not source:
                raise ValueError("canonical source alias target is missing")
        return source

    @classmethod
    def _merge_exact_duplicates(
        cls,
        connection: Any,
        *,
        source_id: str,
        content_sha256: str,
    ) -> tuple[str, list[str]]:
        """Collapse exact-body aliases only when a shared provider identity agrees.

        Content equality is necessary but not sufficient: separate syndicated
        items and short boilerplate can have identical bytes.  A merge also
        requires an explicitly namespaced cross-adapter external identity.  A
        pair of different canonical URLs always remains separate.
        """

        current = connection.execute(
            "SELECT * FROM sources WHERE source_id=?", (source_id,)
        ).fetchone()
        if not current:
            raise ValueError("captured source disappeared before deduplication")
        current = cls._resolve_active_source(connection, current)
        current_shared_ids = cls._shared_external_source_ids(
            connection, current["source_id"]
        )
        candidates: list[tuple[Any, str]] = []
        for row in connection.execute(
                """SELECT * FROM sources
                WHERE content_sha256=? AND merged_into_source_id IS NULL AND source_id<>?
                ORDER BY created_at,source_id""",
                (content_sha256, current["source_id"]),
            ):
            if (
                current["canonical_url"]
                and row["canonical_url"]
                and current["canonical_url"] != row["canonical_url"]
            ):
                continue
            shared_ids = current_shared_ids & cls._shared_external_source_ids(
                connection, row["source_id"]
            )
            if shared_ids:
                candidates.append((row, min(shared_ids)))
        if not candidates:
            return current["source_id"], []
        pool = [current, *(row for row, _shared_id in candidates)]
        target = min(
            pool,
            key=lambda row: (
                0 if row["canonical_url"] else 1,
                row["created_at"],
                row["source_id"],
            ),
        )
        merged_source_ids: list[str] = []
        matching_ids = {
            row["source_id"]: shared_id for row, shared_id in candidates
        }
        for loser in pool:
            if loser["source_id"] == target["source_id"]:
                continue
            if (
                target["canonical_url"]
                and loser["canonical_url"]
                and target["canonical_url"] != loser["canonical_url"]
            ):
                continue
            cls._merge_source_alias(
                connection,
                target_source_id=target["source_id"],
                loser_source_id=loser["source_id"],
                content_sha256=content_sha256,
                matching_shared_external_source_id=(
                    matching_ids.get(loser["source_id"])
                    or min(
                        cls._shared_external_source_ids(connection, target["source_id"])
                        & cls._shared_external_source_ids(connection, loser["source_id"])
                    )
                ),
            )
            merged_source_ids.append(loser["source_id"])
        return target["source_id"], merged_source_ids

    @staticmethod
    def _shared_external_source_ids(connection: Any, source_id: str) -> set[str]:
        shared_ids: set[str] = set()
        for row in connection.execute(
            "SELECT metadata_json FROM discovery_events WHERE source_id=?",
            (source_id,),
        ):
            try:
                metadata = json.loads(row["metadata_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            value = metadata.get("shared_external_source_id")
            if isinstance(value, str) and value.strip():
                shared_ids.add(value.strip())
        return shared_ids

    @staticmethod
    def _merge_source_alias(
        connection: Any,
        *,
        target_source_id: str,
        loser_source_id: str,
        content_sha256: str,
        matching_shared_external_source_id: str,
    ) -> None:
        target = connection.execute(
            "SELECT * FROM sources WHERE source_id=?", (target_source_id,)
        ).fetchone()
        loser = connection.execute(
            "SELECT * FROM sources WHERE source_id=?", (loser_source_id,)
        ).fetchone()
        if not target or not loser or loser["merged_into_source_id"]:
            return
        admissibility_rank = {"pending": 0, "admissible": 1, "restricted": 2, "blocked": 3}
        rights_state = conservative_combined_rights(
            left_state=str(target["rights_state"]),
            left_metadata=target["metadata_json"],
            right_state=str(loser["rights_state"]),
            right_metadata=loser["metadata_json"],
        )
        admissibility_state = max(
            (target["admissibility_state"], loser["admissibility_state"]),
            key=admissibility_rank.__getitem__,
        )
        target_metadata = json.loads(target["metadata_json"])
        aliases = target_metadata.get("merged_source_aliases")
        aliases = [dict(item) for item in aliases if isinstance(item, dict)] if isinstance(aliases, list) else []
        alias = {
            "source_id": loser["source_id"],
            "canonical_identity": loser["canonical_identity"],
            "source_kind": loser["source_kind"],
            "canonical_url": loser["canonical_url"],
            "shared_external_source_id": matching_shared_external_source_id,
        }
        if not any(item.get("source_id") == loser["source_id"] for item in aliases):
            aliases.append(alias)
        target_metadata["merged_source_aliases"] = sorted(
            aliases, key=lambda item: str(item.get("source_id") or "")
        )
        now = _utcnow()
        connection.execute(
            """UPDATE sources SET
                author_or_publisher=COALESCE(author_or_publisher,?),
                title=COALESCE(title,?),rights_state=?,admissibility_state=?,
                content_sha256=?,raw_artifact_id=COALESCE(raw_artifact_id,?),
                transcript_artifact_id=COALESCE(transcript_artifact_id,?),
                captured_at=COALESCE(captured_at,?),updated_at=?,metadata_json=?
            WHERE source_id=?""",
            (
                loser["author_or_publisher"],
                loser["title"],
                rights_state,
                admissibility_state,
                content_sha256,
                loser["raw_artifact_id"],
                loser["transcript_artifact_id"],
                loser["captured_at"],
                now,
                _canonical_json(target_metadata),
                target_source_id,
            ),
        )
        connection.execute(
            "UPDATE discovery_events SET source_id=? WHERE source_id=?",
            (target_source_id, loser_source_id),
        )
        connection.execute(
            "UPDATE evidence_records SET source_id=? WHERE source_id=?",
            (target_source_id, loser_source_id),
        )
        connection.execute(
            """INSERT OR IGNORE INTO opportunity_sources(
                opportunity_id,source_id,relationship_kind
            ) SELECT opportunity_id,?,relationship_kind FROM opportunity_sources WHERE source_id=?""",
            (target_source_id, loser_source_id),
        )
        connection.execute("DELETE FROM opportunity_sources WHERE source_id=?", (loser_source_id,))
        connection.execute(
            "UPDATE persona_candidate_evidence SET source_id=? WHERE source_id=?",
            (target_source_id, loser_source_id),
        )
        loser_metadata = json.loads(loser["metadata_json"])
        loser_metadata["merged_into_source_id"] = target_source_id
        loser_metadata["merge_content_sha256"] = content_sha256
        connection.execute(
            """UPDATE sources SET merged_into_source_id=?,updated_at=?,metadata_json=?
            WHERE source_id=?""",
            (target_source_id, now, _canonical_json(loser_metadata), loser_source_id),
        )
        event_key = f"source-merge:{loser_source_id}:{target_source_id}:{content_sha256}"
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                payload_json,provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,'source_deduplication',?,?,?,?)
            ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}")),
                "source.alias_merged",
                "source",
                target_source_id,
                now,
                _canonical_json(
                    {
                        "canonical_source_id": target_source_id,
                        "merged_source_id": loser_source_id,
                        "content_sha256": content_sha256,
                        "shared_external_source_id": matching_shared_external_source_id,
                    }
                ),
                _canonical_json(
                    {
                        "merge_rule": "exact_content_and_shared_external_id/v2",
                        "merged_canonical_identity": loser["canonical_identity"],
                    }
                ),
                "[]",
                event_key,
            ),
        )

    @staticmethod
    def _record_capture_event(
        connection: Any,
        *,
        source_id: str,
        capture_kind: str,
        artifact: Mapping[str, Any],
    ) -> None:
        event_key = f"source-capture:{source_id}:{capture_kind}:{artifact['content_sha256']}"
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                payload_json,provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,'source_capture',?,?,?,?)
            ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                "source.capture_verified",
                "source",
                source_id,
                _utcnow(),
                _canonical_json(
                    {
                        "artifact_id": artifact["artifact_id"],
                        "byte_size": artifact["byte_size"],
                        "capture_kind": capture_kind,
                        "content_sha256": artifact["content_sha256"],
                    }
                ),
                _canonical_json({"storage_authority": "local_private_artifact_store"}),
                _canonical_json([artifact["artifact_id"]]),
                event_key,
            ),
        )
