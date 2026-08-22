from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json
from app.services.linkedin_performance_ledger_service import (
    CANONICAL_WORKSPACE_KEY,
    EVENT_SCHEMA,
    EVENT_TYPES,
)


MIGRATION_SCHEMA = "legacy_linkedin_performance_migration/v1"
MAX_INPUT_FILE_BYTES = 64 * 1024 * 1024
MAX_EVENT_BYTES = 256 * 1024
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class LegacyPerformanceMigrationError(ValueError):
    """Raised when historical performance evidence cannot be imported safely."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware_iso(value: Any, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise LegacyPerformanceMigrationError(f"{field} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LegacyPerformanceMigrationError(f"{field} is not timezone-aware")
    return parsed.isoformat()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LegacyPerformanceMigrationError("legacy event contains a duplicate JSON key")
        result[key] = value
    return result


def load_legacy_performance_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read one explicit legacy ledger without following links or tolerating corruption."""

    candidate = path.expanduser()
    try:
        details = candidate.lstat()
    except FileNotFoundError as exc:
        raise LegacyPerformanceMigrationError("legacy ledger does not exist") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise LegacyPerformanceMigrationError("legacy ledger must be a regular, non-symlink file")
    if details.st_size > MAX_INPUT_FILE_BYTES:
        raise LegacyPerformanceMigrationError("legacy ledger exceeds the bounded migration size")
    events: list[dict[str, Any]] = []
    with candidate.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                value = json.loads(line, object_pairs_hook=_no_duplicate_keys)
            except json.JSONDecodeError as exc:
                raise LegacyPerformanceMigrationError(
                    f"legacy ledger contains invalid JSON at line {line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise LegacyPerformanceMigrationError(
                    f"legacy ledger row {line_number} is not an object"
                )
            events.append(value)
    return events


def _legacy_semantic_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {"event_id", "idempotency_key", "payload_sha256", "recorded_at"}
    return {str(key): value for key, value in event.items() if key not in excluded}


def _validate_event(event: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    normalized = dict(event)
    rendered = _canonical_json(normalized)
    if len(rendered.encode("utf-8")) > MAX_EVENT_BYTES:
        raise LegacyPerformanceMigrationError("legacy event exceeds the bounded row size")
    required = {
        "schema_version",
        "event_id",
        "idempotency_key",
        "payload_sha256",
        "event_type",
        "workspace_key",
        "content_id",
        "content_version_sha256",
        "occurred_at",
        "recorded_at",
        "strategy_contract",
        "data",
    }
    if not required.issubset(normalized):
        raise LegacyPerformanceMigrationError("legacy event is incomplete")
    if normalized.get("schema_version") != EVENT_SCHEMA:
        raise LegacyPerformanceMigrationError("legacy event schema is unsupported")
    if normalized.get("workspace_key") != CANONICAL_WORKSPACE_KEY:
        raise LegacyPerformanceMigrationError("legacy event workspace is unsupported")
    if normalized.get("event_type") not in EVENT_TYPES:
        raise LegacyPerformanceMigrationError("legacy event type is unsupported")
    event_id = str(normalized.get("event_id") or "").strip()
    content_id = str(normalized.get("content_id") or "").strip()
    digest = str(normalized.get("content_version_sha256") or "").strip().lower()
    payload_sha256 = str(normalized.get("payload_sha256") or "").strip().lower()
    if not event_id or len(event_id) > 200:
        raise LegacyPerformanceMigrationError("legacy event_id is invalid")
    if not content_id or len(content_id) > 160:
        raise LegacyPerformanceMigrationError("legacy content_id is invalid")
    if SHA256_RE.fullmatch(digest) is None or SHA256_RE.fullmatch(payload_sha256) is None:
        raise LegacyPerformanceMigrationError("legacy event digest is invalid")
    if not isinstance(normalized.get("strategy_contract"), dict) or not isinstance(normalized.get("data"), dict):
        raise LegacyPerformanceMigrationError("legacy event structured payload is invalid")
    _aware_iso(normalized.get("occurred_at"), field="occurred_at")
    _aware_iso(normalized.get("recorded_at"), field="recorded_at")
    computed = _sha256(_canonical_json(_legacy_semantic_payload(normalized)))
    if computed != payload_sha256:
        raise LegacyPerformanceMigrationError("legacy payload hash does not match the event")
    normalized["content_id"] = content_id
    normalized["content_version_sha256"] = digest
    normalized["payload_sha256"] = payload_sha256
    return normalized, _sha256(rendered)


def _metadata_identity_refs(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    refs: set[str] = set()
    direct = value.get("legacy_content_id")
    if isinstance(direct, str) and direct.strip():
        refs.add(direct.strip())
    multiple = value.get("legacy_content_ids")
    if isinstance(multiple, list):
        refs.update(item.strip() for item in multiple if isinstance(item, str) and item.strip())
    return refs


class LegacyPerformanceMigrationService:
    """Preserve legacy JSONL rows as non-authoritative SQL audit evidence.

    This service intentionally never calls ``ContentLearningService`` and never
    writes lifecycle, publication, persona, or owner-approval tables.  An exact
    content-ID plus immutable body-hash match may add a separate audit link to a
    revision; it does not convert the historical assertion into canonical truth.
    """

    def __init__(self, store: IntegratedSystemStore) -> None:
        self.store = store

    def _revision_candidates(self, digest: str) -> list[dict[str, Any]]:
        database = self.store.database_path
        if not database.is_file():
            return []
        uri = f"{database.as_uri()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=10)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """SELECT r.revision_id,r.post_id,r.control_json,r.body_artifact_id,
                p.current_revision_id,p.metadata_json,a.content_sha256
                FROM content_revisions r
                JOIN canonical_posts p ON p.post_id=r.post_id
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE lower(a.content_sha256)=?""",
                (digest,),
            ).fetchall()
        except sqlite3.Error:
            return []
        finally:
            if "connection" in locals():
                connection.close()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for key in ("metadata_json", "control_json"):
                try:
                    item[key.removesuffix("_json")] = json.loads(item.get(key) or "{}")
                except json.JSONDecodeError:
                    item[key.removesuffix("_json")] = {}
            result.append(item)
        return result

    def _resolve_mapping(self, *, content_id: str, digest: str) -> dict[str, Any]:
        matches: list[tuple[dict[str, Any], str]] = []
        for candidate in self._revision_candidates(digest):
            method = ""
            if content_id == candidate["revision_id"]:
                method = "revision_id_and_body_hash"
            elif content_id == candidate["post_id"]:
                method = "post_id_and_body_hash"
            else:
                refs = _metadata_identity_refs(candidate.get("metadata")) | _metadata_identity_refs(
                    candidate.get("control")
                )
                if content_id in refs:
                    method = "explicit_legacy_id_and_body_hash"
            if method:
                matches.append((candidate, method))
        if len(matches) > 1:
            current = [pair for pair in matches if pair[0]["revision_id"] == pair[0]["current_revision_id"]]
            if len(current) == 1:
                matches = current
        if len(matches) != 1:
            return {
                "status": "unmapped",
                "reason": "no_exact_identity_and_hash_match" if not matches else "ambiguous_exact_identity_and_hash_match",
            }
        candidate, method = matches[0]
        return {
            "status": "mapped_audit_only",
            "method": method,
            "post_id": candidate["post_id"],
            "revision_id": candidate["revision_id"],
            "body_artifact_id": candidate["body_artifact_id"],
        }

    def plan(self, events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        validated: list[dict[str, Any]] = []
        input_tokens: list[str] = []
        seen: dict[str, str] = {}
        duplicates = 0
        invalid = 0
        for index, raw in enumerate(events):
            try:
                event, record_sha256 = _validate_event(raw)
                event_id = str(event["event_id"])
                previous = seen.get(event_id)
                if previous is not None:
                    if previous != record_sha256:
                        raise LegacyPerformanceMigrationError(
                            "legacy event_id is repeated with different content"
                        )
                    duplicates += 1
                    continue
                seen[event_id] = record_sha256
                mapping = self._resolve_mapping(
                    content_id=str(event["content_id"]),
                    digest=str(event["content_version_sha256"]),
                )
                input_tokens.append(f"{event_id}:{record_sha256}")
                validated.append({"event": event, "record_sha256": record_sha256, "mapping": mapping})
                items.append(
                    {
                        "event_id": event_id,
                        "legacy_event_type": event["event_type"],
                        "record_sha256": record_sha256,
                        "content_identity_sha256": _sha256(
                            f"{event['content_id']}\x00{event['content_version_sha256']}"
                        ),
                        "mapping": mapping,
                    }
                )
            except (LegacyPerformanceMigrationError, TypeError) as exc:
                invalid += 1
                items.append(
                    {
                        "event_id": str(raw.get("event_id") or f"row-{index + 1}"),
                        "status": "invalid",
                        "reason": str(exc),
                    }
                )
        mapped = sum(item["mapping"]["status"] == "mapped_audit_only" for item in validated)
        manifest_sha256 = _sha256("\n".join(sorted(input_tokens)))
        public_plan = {
            "schema_version": MIGRATION_SCHEMA,
            "mode": "dry_run",
            "input_manifest_sha256": manifest_sha256,
            "counts": {
                "input": len(items) + duplicates,
                "valid": len(validated),
                "invalid": invalid,
                "duplicates": duplicates,
                "mapped_audit_only": mapped,
                "unmapped_audit_only": len(validated) - mapped,
            },
            "items": items,
            "authority": {
                "legacy_rows": "historical_audit_only",
                "canonical_learning_mutated": False,
                "approval_or_publication_synthesized": False,
                "persona_mutated": False,
            },
            "rollback": {
                "data_mutation": "append_only_audit_events_only",
                "action": "exclude legacy.performance_* audit event types from readers",
            },
        }
        public_plan["plan_sha256"] = _sha256(_canonical_json(public_plan))
        public_plan["_validated"] = validated
        return public_plan

    def migrate(self, events: Iterable[Mapping[str, Any]], *, apply: bool = False) -> dict[str, Any]:
        materialized = [dict(event) for event in events]
        plan = self.plan(materialized)
        validated = list(plan.pop("_validated"))
        if not apply:
            return plan
        if plan["counts"]["invalid"]:
            raise LegacyPerformanceMigrationError("migration apply refused because the input contains invalid rows")

        self.store.migrate()
        # Re-read exact revision identities immediately before mutation so a
        # stale plan cannot create a link after the canonical state changes.
        plan = self.plan(materialized)
        validated = list(plan.pop("_validated"))
        if plan["counts"]["invalid"]:
            raise LegacyPerformanceMigrationError("migration apply refused after canonical-state revalidation")

        created = 0
        reused = 0
        links = 0
        for item in validated:
            event = item["event"]
            record_sha256 = item["record_sha256"]
            mapping = item["mapping"]
            audit_key = f"legacy-performance:audit:v1:{event['event_id']}"
            existed = self._event_exists(audit_key)
            audit = self.store.append_event(
                event_type="legacy.performance_audit_imported",
                aggregate_type="legacy_performance_identity",
                aggregate_id="legacy-linkedin-" + _sha256(
                    f"{event['content_id']}\x00{event['content_version_sha256']}"
                )[:32],
                actor_type="legacy_migration",
                payload={
                    "schema_version": MIGRATION_SCHEMA,
                    "authority": "historical_audit_only",
                    "canonical_learning_mutation": False,
                    "legacy_record_sha256": record_sha256,
                    "legacy_record": event,
                },
                provenance={
                    "source": "linkedin_publication_events.jsonl",
                    "legacy_schema_version": EVENT_SCHEMA,
                    "migration_version": "1.0.0",
                    "mapping_status": mapping["status"],
                },
                idempotency_key=audit_key,
                occurred_at=str(event["occurred_at"]),
            )
            created += int(not existed)
            reused += int(existed)
            if mapping["status"] == "mapped_audit_only":
                link_key = f"legacy-performance:link:v1:{event['event_id']}:{mapping['revision_id']}"
                link_existed = self._event_exists(link_key)
                self.store.append_event(
                    event_type="legacy.performance_revision_linked",
                    aggregate_type="content_revision",
                    aggregate_id=str(mapping["revision_id"]),
                    actor_type="legacy_migration",
                    payload={
                        "schema_version": MIGRATION_SCHEMA,
                        "authority": "historical_audit_link_only",
                        "canonical_learning_mutation": False,
                        "legacy_audit_event_id": audit["event_id"],
                        "legacy_event_type": event["event_type"],
                        "legacy_record_sha256": record_sha256,
                        "post_id": mapping["post_id"],
                        "revision_id": mapping["revision_id"],
                        "content_sha256": event["content_version_sha256"],
                        "match_method": mapping["method"],
                    },
                    provenance={
                        "source": "legacy.performance_audit_imported",
                        "migration_version": "1.0.0",
                        "truth_effect": "none",
                    },
                    artifact_refs=[str(mapping["body_artifact_id"])],
                    idempotency_key=link_key,
                    occurred_at=str(event["occurred_at"]),
                )
                created += int(not link_existed)
                reused += int(link_existed)
                links += 1

        receipt_key = f"legacy-performance:receipt:v1:{plan['input_manifest_sha256']}:{plan['plan_sha256']}"
        receipt_existed = self._event_exists(receipt_key)
        self.store.append_event(
            event_type="legacy.performance_migration_receipt",
            aggregate_type="migration_receipt",
            aggregate_id="legacy-performance-" + plan["input_manifest_sha256"][:32],
            actor_type="legacy_migration",
            payload={
                "schema_version": MIGRATION_SCHEMA,
                "input_manifest_sha256": plan["input_manifest_sha256"],
                "plan_sha256": plan["plan_sha256"],
                "counts": plan["counts"],
                "canonical_learning_mutated": False,
                "persona_mutated": False,
            },
            provenance={"source": "legacy_performance_migration", "migration_version": "1.0.0"},
            idempotency_key=receipt_key,
        )
        created += int(not receipt_existed)
        reused += int(receipt_existed)
        return {
            **plan,
            "mode": "applied",
            "apply_result": {
                "created_events": created,
                "reused_events": reused,
                "audit_rows": len(validated),
                "revision_links": links,
                "canonical_learning_mutated": False,
                "persona_mutated": False,
            },
        }

    def _event_exists(self, idempotency_key: str) -> bool:
        with self.store.connection() as connection:
            return bool(
                connection.execute(
                    "SELECT 1 FROM system_events WHERE idempotency_key=? LIMIT 1",
                    (idempotency_key,),
                ).fetchone()
            )
