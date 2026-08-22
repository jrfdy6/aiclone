from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any, Callable, Mapping

from app.services.integrated_system_store import IntegratedSystemStore
from app.services.railway_retention_service import (
    _canonical_json,
    _migration_source_sha256,
    _sha256,
    _table_schema_sha256,
    retention_rules,
)


ARCHIVE_SCHEMA_VERSION = "railway_retention_local_archive/v2"
MANIFEST_SCHEMA_VERSION = "railway_retention_local_archive_manifest/v2"
RECEIPT_SCHEMA_VERSION = "railway_retention_local_archive_receipt/v2"
RUN_MANIFEST_SCHEMA_VERSION = "railway_retention_local_archive_run_manifest/v2"
ARCHIVE_EVENT_TYPE = "retention.local_archive_verified"
ARCHIVE_DISCOVERY_EVENT_TYPE = "retention.local_archive_discovery_verified"
ARCHIVE_DISCOVERY_BINDING_SCHEMA_VERSION = "railway_retention_archive_discovery_binding/v1"
CANDIDATE_SNAPSHOT_SCHEMA_VERSION = "railway_retention_archive_candidate_snapshot/v2"

ArchiveBinding = tuple[str, str, str, str]
ArchiveDiscoveryBinding = tuple[str, str, str, str]

_DISCOVERY_BINDING_FIELDS = frozenset(
    {
        "schema_version",
        "archive_receipt_sha256",
        "source_table",
        "rule_name",
        "row_identity",
        "source_row_sha256",
        "source_discovery_sha256",
    }
)

ARCHIVE_TARGETS: dict[tuple[str, str], dict[str, Any]] = {
    ("local_codex_jobs", "completed_large_job_payloads"): {
        "mutation_kind": "compact_job_payload_and_delete_artifacts",
        "target_contract_version": "railway_retained_job_receipt/v1",
        "target_row_count": 1,
    },
    ("standups", "standup_payload_compaction"): {
        "mutation_kind": "compact_standup_payload",
        "target_contract_version": "railway_retained_standup_receipt/v1",
        "target_row_count": 1,
    },
    ("standups", "standup_rows_after_audit_window"): {
        "mutation_kind": "delete",
        "target_contract_version": "railway_retained_standup_receipt/v1",
        "target_row_count": 0,
    },
}

_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "verified",
        "canonical_local_copy",
        "source_table",
        "rule_name",
        "row_identity",
        "source_row_sha256",
        "source_snapshot_sha256",
        "source_schema_sha256",
        "source_row_count",
        "target_contract_version",
        "target_contract_sha256",
        "target_row_count",
        "mutation_kind",
        "artifact_relative_path",
        "artifact_sha256",
        "artifact_bytes",
        "manifest_relative_path",
        "manifest_sha256",
        "manifest_member_count",
    }
)
_ARCHIVE_FIELDS = frozenset({"schema_version", "source", "target", "source_record"})
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "source",
        "target",
        "artifacts",
        "counts",
        "source_manifest_sha256",
        "target_manifest_sha256",
        "schema_manifest_sha256",
    }
)


def _state_root(path: Path | None = None, *, create: bool = True) -> Path:
    configured = path or Path(
        os.getenv("AI_CLONE_STATE_ROOT", Path.home() / ".codex" / "ai-clone" / "state")
    )
    raw = configured.expanduser()
    if raw.exists() and raw.is_symlink():
        raise ValueError("retention archive state root must not be a symlink")
    if not raw.exists() and not create:
        raise ValueError("retention archive state root does not exist")
    # A symlinked parent is intentionally supported (for example macOS private
    # state mounts). Resolve it once and anchor every descendant check/write to
    # that canonical directory; the configured root itself may never be a link.
    resolved = raw.resolve()
    if create:
        resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    elif not resolved.is_dir():
        raise ValueError("retention archive state root is not a directory")
    return resolved


def _secure_directory(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("retention archive directory must stay inside the private state root")
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("retention archive directory must not traverse a symlink")
        current.mkdir(exist_ok=True, mode=0o700)
    if root != current and root not in current.resolve().parents:
        raise ValueError("retention archive directory escaped the private state root")
    return current


def _content_bytes(payload: Mapping[str, Any]) -> bytes:
    return _canonical_json(dict(payload)).encode("utf-8")


def _write_content_addressed(
    *,
    root: Path,
    kind: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    body = _content_bytes(payload)
    digest = hashlib.sha256(body).hexdigest()
    directory = _secure_directory(root, Path("retention") / kind / "v2" / digest[:2])
    destination = directory / f"{digest}.json"
    relative = destination.relative_to(root)

    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError("retention content-addressed target is not a regular file")
        if destination.read_bytes() != body:
            raise ValueError("retention content-addressed artifact hash collision or tamper detected")
        return {"path": destination, "relative_path": relative.as_posix(), "sha256": digest, "bytes": len(body)}

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{digest}.", dir=directory)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != body:
                raise ValueError("retention content-addressed artifact changed during write")
        os.chmod(destination, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return {"path": destination, "relative_path": relative.as_posix(), "sha256": digest, "bytes": len(body)}


def _target_descriptor(*, source_table: str, rule_name: str) -> dict[str, Any]:
    target = ARCHIVE_TARGETS.get((source_table, rule_name))
    if target is None:
        raise ValueError("retention archive rule is not an approved local archive lane")
    core = {
        "source_table": source_table,
        "rule_name": rule_name,
        "mutation_kind": target["mutation_kind"],
        "target_contract_version": target["target_contract_version"],
        "target_row_count": target["target_row_count"],
    }
    return {**core, "target_contract_sha256": _sha256(core)}


def _archive_payload(
    *,
    candidate: Mapping[str, Any],
    source_table: str,
    rule_name: str,
    source_schema_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = str(candidate.get("identity") or "").strip()
    source = candidate.get("source")
    if not identity or not isinstance(source, dict):
        raise ValueError("retention archive candidate must contain an identity and exact source object")
    if re.fullmatch(r"[0-9a-f]{64}", source_schema_sha256) is None:
        raise ValueError("retention archive source schema hash is invalid")
    source_snapshot_sha256 = _sha256(source)
    source_row_sha256 = _migration_source_sha256(source_table, source)
    supplied_snapshot = str(candidate.get("source_sha256") or "")
    supplied_migration = str(candidate.get("migration_source_sha256") or "")
    if supplied_snapshot and supplied_snapshot != source_snapshot_sha256:
        raise ValueError("retention archive candidate source snapshot hash drifted")
    if supplied_migration and supplied_migration != source_row_sha256:
        raise ValueError("retention archive candidate migration hash drifted")

    source_descriptor = {
        "source_table": source_table,
        "row_identity": identity,
        "row_count": 1,
        "source_snapshot_sha256": source_snapshot_sha256,
        "source_row_sha256": source_row_sha256,
        "source_schema_sha256": source_schema_sha256,
    }
    target_descriptor = _target_descriptor(source_table=source_table, rule_name=rule_name)
    archive = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "source": source_descriptor,
        "target": target_descriptor,
        "source_record": source,
    }
    return archive, source_descriptor, target_descriptor


def produce_candidate_archive(
    *,
    candidate: Mapping[str, Any],
    source_table: str,
    rule_name: str,
    source_schema_sha256: str,
    state_root: Path | None = None,
    store: IntegratedSystemStore | None = None,
) -> dict[str, Any]:
    """Persist one immutable local archive and exact proof without writing Railway."""

    source_discovery_sha256 = str(candidate.get("source_discovery_sha256") or "").strip()
    if source_discovery_sha256 and re.fullmatch(r"[0-9a-f]{64}", source_discovery_sha256) is None:
        raise ValueError("retention archive candidate discovery hash is invalid")
    root = _state_root(state_root)
    archive, source, target = _archive_payload(
        candidate=candidate,
        source_table=source_table,
        rule_name=rule_name,
        source_schema_sha256=source_schema_sha256,
    )
    archive_file = _write_content_addressed(root=root, kind="archives", payload=archive)
    artifact_member = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "relative_path": archive_file["relative_path"],
        "sha256": archive_file["sha256"],
        "bytes": archive_file["bytes"],
    }
    counts = {
        "source_rows": 1,
        "target_rows": int(target["target_row_count"]),
        "artifacts": 1,
        "manifest_members": 1,
    }
    schema_subject = {
        "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
        "source_schema_sha256": source_schema_sha256,
        "target_contract_version": target["target_contract_version"],
        "target_contract_sha256": target["target_contract_sha256"],
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source": source,
        "target": target,
        "artifacts": [artifact_member],
        "counts": counts,
        "source_manifest_sha256": _sha256([source]),
        "target_manifest_sha256": _sha256([target]),
        "schema_manifest_sha256": _sha256(schema_subject),
    }
    manifest_file = _write_content_addressed(root=root, kind="manifests", payload=manifest)
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "verified": True,
        "canonical_local_copy": True,
        "source_table": source_table,
        "rule_name": rule_name,
        "row_identity": source["row_identity"],
        "source_row_sha256": source["source_row_sha256"],
        "source_snapshot_sha256": source["source_snapshot_sha256"],
        "source_schema_sha256": source_schema_sha256,
        "source_row_count": 1,
        "target_contract_version": target["target_contract_version"],
        "target_contract_sha256": target["target_contract_sha256"],
        "target_row_count": target["target_row_count"],
        "mutation_kind": target["mutation_kind"],
        "artifact_relative_path": archive_file["relative_path"],
        "artifact_sha256": archive_file["sha256"],
        "artifact_bytes": archive_file["bytes"],
        "manifest_relative_path": manifest_file["relative_path"],
        "manifest_sha256": manifest_file["sha256"],
        "manifest_member_count": 1,
    }
    receipt_sha256 = _sha256(receipt)
    canonical_store = store or IntegratedSystemStore()
    canonical_store.put_artifact(
        content_sha256=archive_file["sha256"],
        artifact_kind="railway_retention_archive_v2",
        logical_ref=f"state://{archive_file['relative_path']}",
        byte_size=archive_file["bytes"],
        media_type="application/json",
        metadata={"source_table": source_table, "rule_name": rule_name, "row_count": 1},
    )
    canonical_store.put_artifact(
        content_sha256=manifest_file["sha256"],
        artifact_kind="railway_retention_archive_manifest_v2",
        logical_ref=f"state://{manifest_file['relative_path']}",
        byte_size=manifest_file["bytes"],
        media_type="application/json",
        metadata={"source_rows": 1, "target_rows": target["target_row_count"]},
    )
    event = canonical_store.append_event(
        event_type=ARCHIVE_EVENT_TYPE,
        aggregate_type="railway_retention",
        aggregate_id=source["row_identity"],
        actor_type="retention_archive_producer",
        payload=receipt,
        provenance={
            "schema_version": "railway_retention_archive_provenance/v2",
            "assessment_kind": "deterministic_local_archive_verification",
            "railway_write_performed": False,
        },
        artifact_refs=[
            f"state://{archive_file['relative_path']}",
            f"state://{manifest_file['relative_path']}",
        ],
        idempotency_key=f"railway-retention-local-archive-v2:{receipt_sha256}",
    )
    discovery_event_id: str | None = None
    if source_discovery_sha256:
        discovery_binding = {
            "schema_version": ARCHIVE_DISCOVERY_BINDING_SCHEMA_VERSION,
            "archive_receipt_sha256": receipt_sha256,
            "source_table": source_table,
            "rule_name": rule_name,
            "row_identity": source["row_identity"],
            "source_row_sha256": source["source_row_sha256"],
            "source_discovery_sha256": source_discovery_sha256,
        }
        discovery_event = canonical_store.append_event(
            event_type=ARCHIVE_DISCOVERY_EVENT_TYPE,
            aggregate_type="railway_retention",
            aggregate_id=source["row_identity"],
            actor_type="retention_archive_producer",
            payload=discovery_binding,
            provenance={
                "schema_version": "railway_retention_archive_discovery_provenance/v1",
                "assessment_kind": "repeatable_read_remote_digest_binding",
                "railway_write_performed": False,
            },
            artifact_refs=[
                f"state://{archive_file['relative_path']}",
                f"state://{manifest_file['relative_path']}",
            ],
            idempotency_key=(
                "railway-retention-local-archive-discovery-v1:"
                f"{receipt_sha256}:{source_discovery_sha256}"
            ),
        )
        discovery_event_id = str(discovery_event["event_id"])
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_sha256": receipt_sha256,
        "receipt": receipt,
        "event_id": event["event_id"],
        "discovery_event_id": discovery_event_id,
        "archive_artifact": artifact_member,
        "manifest": {
            "relative_path": manifest_file["relative_path"],
            "sha256": manifest_file["sha256"],
            "bytes": manifest_file["bytes"],
        },
    }


def verify_candidate_archive_receipt(
    payload: Mapping[str, Any],
    *,
    state_root: Path | None = None,
) -> dict[str, str] | None:
    """Re-read and re-hash every v2 archive binding used by the retention gate."""

    try:
        if not isinstance(payload, Mapping) or set(payload) != _RECEIPT_FIELDS:
            return None
        if (
            payload.get("schema_version") != RECEIPT_SCHEMA_VERSION
            or payload.get("verified") is not True
            or payload.get("canonical_local_copy") is not True
            or int(payload.get("source_row_count") or 0) != 1
            or int(payload.get("manifest_member_count") or 0) != 1
        ):
            return None
        source_table = str(payload.get("source_table") or "")
        rule_name = str(payload.get("rule_name") or "")
        identity = str(payload.get("row_identity") or "")
        expected_target = _target_descriptor(source_table=source_table, rule_name=rule_name)
        if (
            not identity
            or payload.get("mutation_kind") != expected_target["mutation_kind"]
            or payload.get("target_contract_version") != expected_target["target_contract_version"]
            or payload.get("target_contract_sha256") != expected_target["target_contract_sha256"]
            or int(payload.get("target_row_count")) != int(expected_target["target_row_count"])
        ):
            return None
        for field in (
            "source_row_sha256",
            "source_snapshot_sha256",
            "source_schema_sha256",
            "target_contract_sha256",
            "artifact_sha256",
            "manifest_sha256",
        ):
            if re.fullmatch(r"[0-9a-f]{64}", str(payload.get(field) or "")) is None:
                return None
        root = _state_root(state_root, create=False)

        def load(relative_value: Any, expected_sha256: str) -> tuple[dict[str, Any], bytes]:
            relative = Path(str(relative_value or ""))
            if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
                raise ValueError("invalid archive-relative path")
            target = root / relative
            if target.is_symlink() or not target.is_file() or root not in target.resolve().parents:
                raise ValueError("archive path is not a contained regular file")
            body = target.read_bytes()
            if hashlib.sha256(body).hexdigest() != expected_sha256:
                raise ValueError("archive hash mismatch")
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise ValueError("archive document is not an object")
            return parsed, body

        archive, archive_bytes = load(payload["artifact_relative_path"], str(payload["artifact_sha256"]))
        manifest, _manifest_bytes = load(payload["manifest_relative_path"], str(payload["manifest_sha256"]))
        if set(archive) != _ARCHIVE_FIELDS or archive.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
            return None
        if set(manifest) != _MANIFEST_FIELDS or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            return None
        source = archive.get("source")
        target = archive.get("target")
        source_record = archive.get("source_record")
        if not isinstance(source, dict) or not isinstance(target, dict) or not isinstance(source_record, dict):
            return None
        if (
            source.get("source_table") != source_table
            or source.get("row_identity") != identity
            or source.get("row_count") != 1
            or source.get("source_row_sha256") != payload["source_row_sha256"]
            or source.get("source_snapshot_sha256") != payload["source_snapshot_sha256"]
            or source.get("source_schema_sha256") != payload["source_schema_sha256"]
            or _sha256(source_record) != payload["source_snapshot_sha256"]
            or _migration_source_sha256(source_table, source_record) != payload["source_row_sha256"]
            or target != expected_target
            or len(archive_bytes) != int(payload.get("artifact_bytes") or -1)
        ):
            return None
        artifact_member = {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "relative_path": payload["artifact_relative_path"],
            "sha256": payload["artifact_sha256"],
            "bytes": payload["artifact_bytes"],
        }
        counts = {
            "source_rows": 1,
            "target_rows": expected_target["target_row_count"],
            "artifacts": 1,
            "manifest_members": 1,
        }
        schema_subject = {
            "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
            "source_schema_sha256": payload["source_schema_sha256"],
            "target_contract_version": expected_target["target_contract_version"],
            "target_contract_sha256": expected_target["target_contract_sha256"],
        }
        if (
            manifest.get("source") != source
            or manifest.get("target") != expected_target
            or manifest.get("artifacts") != [artifact_member]
            or manifest.get("counts") != counts
            or manifest.get("source_manifest_sha256") != _sha256([source])
            or manifest.get("target_manifest_sha256") != _sha256([expected_target])
            or manifest.get("schema_manifest_sha256") != _sha256(schema_subject)
        ):
            return None
        return {
            "source_table": source_table,
            "rule_name": rule_name,
            "row_identity": identity,
            "source_row_sha256": str(payload["source_row_sha256"]),
        }
    except (AttributeError, json.JSONDecodeError, OSError, TypeError, UnicodeDecodeError, ValueError):
        return None


def _verified_local_archive_proofs(
    *,
    state_root: Path | None = None,
    store: IntegratedSystemStore | None = None,
) -> tuple[set[ArchiveBinding], set[ArchiveDiscoveryBinding]]:
    """Reverify immutable v2 proofs and their optional remote-digest bindings."""

    canonical_store = store or IntegratedSystemStore()
    database_path = canonical_store.database_path
    if not database_path.is_file():
        return set(), set()
    try:
        root = _state_root(state_root, create=False)
        connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                """SELECT aggregate_id,event_type,payload_json FROM system_events
                WHERE event_type IN (?,?) ORDER BY occurred_at,event_id""",
                (ARCHIVE_EVENT_TYPE, ARCHIVE_DISCOVERY_EVENT_TYPE),
            ).fetchall()
        finally:
            connection.close()
    except (OSError, sqlite3.Error, ValueError):
        return set(), set()

    bindings: set[ArchiveBinding] = set()
    archive_by_receipt: dict[str, ArchiveBinding] = {}
    discovery_events: list[tuple[str, Mapping[str, Any]]] = []
    for aggregate_id, event_type, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        if event_type == ARCHIVE_EVENT_TYPE:
            binding = verify_candidate_archive_receipt(payload, state_root=root)
            if binding is None or str(aggregate_id or "") != binding["row_identity"]:
                continue
            normalized = (
                binding["source_table"],
                binding["rule_name"],
                binding["row_identity"],
                binding["source_row_sha256"],
            )
            bindings.add(normalized)
            archive_by_receipt[_sha256(payload)] = normalized
        elif event_type == ARCHIVE_DISCOVERY_EVENT_TYPE:
            discovery_events.append((str(aggregate_id or ""), payload))

    discovery_bindings: set[ArchiveDiscoveryBinding] = set()
    for aggregate_id, payload in discovery_events:
        if (
            set(payload) != _DISCOVERY_BINDING_FIELDS
            or payload.get("schema_version") != ARCHIVE_DISCOVERY_BINDING_SCHEMA_VERSION
        ):
            continue
        archive_receipt_sha256 = str(payload.get("archive_receipt_sha256") or "")
        source_discovery_sha256 = str(payload.get("source_discovery_sha256") or "")
        source_binding: ArchiveBinding = (
            str(payload.get("source_table") or ""),
            str(payload.get("rule_name") or ""),
            str(payload.get("row_identity") or ""),
            str(payload.get("source_row_sha256") or ""),
        )
        if (
            re.fullmatch(r"[0-9a-f]{64}", archive_receipt_sha256) is None
            or re.fullmatch(r"[0-9a-f]{64}", source_discovery_sha256) is None
            or aggregate_id != source_binding[2]
            or archive_by_receipt.get(archive_receipt_sha256) != source_binding
        ):
            continue
        discovery_bindings.add(
            (source_binding[0], source_binding[1], source_binding[2], source_discovery_sha256)
        )
    return bindings, discovery_bindings


def verified_local_archive_bindings(
    *,
    state_root: Path | None = None,
    store: IntegratedSystemStore | None = None,
) -> set[ArchiveBinding]:
    """Read and reverify only immutable v2 archive bindings."""

    bindings, _discovery_bindings = _verified_local_archive_proofs(
        state_root=state_root,
        store=store,
    )
    return bindings


def _candidate_query(rule: Any, *, blocked: bool) -> tuple[str, tuple[Any, ...]]:
    query = rule.blocked_sql if blocked else rule.candidate_sql
    params = rule.blocked_params if blocked else rule.params
    if not query:
        raise ValueError("retention archive rule has no candidate query")
    return str(query), tuple(params)


def _discovery_source_expression(*, table_name: str) -> str:
    if table_name == "local_codex_jobs":
        return """jsonb_set(
            retention_archive_candidates.source_record::jsonb,
            '{row}',
            COALESCE(retention_archive_candidates.source_record::jsonb->'row','{}'::jsonb)
                - 'retention_local_receipt_sha256',
            false
        )"""
    if table_name == "standups":
        return (
            "retention_archive_candidates.source_record::jsonb "
            "- 'retention_local_receipt_sha256'"
        )
    raise ValueError("retention archive discovery does not support this table")


def _discovery_projection_sql(*, rule: Any, blocked: bool) -> tuple[str, tuple[Any, ...]]:
    query, params = _candidate_query(rule, blocked=blocked)
    normalized_source = _discovery_source_expression(table_name=str(rule.table_name))
    projection = f"""SELECT
        retention_archive_candidates.row_identity::text,
        retention_archive_candidates.source_bytes,
        encode(
            sha256(convert_to(({normalized_source})::text,'UTF8')),
            'hex'
        ) AS source_discovery_sha256
    FROM ({query}) AS retention_archive_candidates(
        row_identity,source_bytes,source_record
    )"""
    return projection, params


def _discover_candidate_page(
    cursor: Any,
    *,
    rule: Any,
    blocked: bool,
    after_identity: str,
    limit: int,
) -> list[dict[str, Any]]:
    projection, params = _discovery_projection_sql(rule=rule, blocked=blocked)
    cursor.execute(
        f"""SELECT row_identity,source_bytes,source_discovery_sha256
        FROM ({projection}) AS retention_archive_discovery
        WHERE row_identity>%s
        ORDER BY row_identity
        LIMIT %s""",
        (*params, after_identity, limit),
    )
    rows: list[dict[str, Any]] = []
    previous_identity = after_identity
    for raw in cursor.fetchall() or []:
        identity = str(raw[0] or "")
        source_discovery_sha256 = str(raw[2] or "")
        if (
            not identity
            or identity <= previous_identity
            or re.fullmatch(r"[0-9a-f]{64}", source_discovery_sha256) is None
        ):
            raise RuntimeError("retention archive discovery returned an invalid keyset row")
        rows.append(
            {
                "identity": identity,
                "bytes": max(0, int(raw[1] or 0)),
                "source_discovery_sha256": source_discovery_sha256,
            }
        )
        previous_identity = identity
    return rows


def _local_receipt_from_source(*, table_name: str, source: Mapping[str, Any]) -> str | None:
    if table_name == "local_codex_jobs":
        value = str(dict(source.get("row") or {}).get("retention_local_receipt_sha256") or "")
    elif table_name == "standups":
        value = str(source.get("retention_local_receipt_sha256") or "")
    else:
        value = ""
    return value if re.fullmatch(r"[0-9a-f]{64}", value) else None


def _fetch_exact_candidates(
    cursor: Any,
    *,
    rule: Any,
    blocked: bool,
    selected: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Fetch full bodies only for selected IDs and bind them to discovery hashes."""

    if not selected:
        return {}
    query, params = _candidate_query(rule, blocked=blocked)
    normalized_source = _discovery_source_expression(table_name=str(rule.table_name))
    identifiers = [str(item["identity"]) for item in selected]
    expected = {str(item["identity"]): item for item in selected}
    if len(expected) != len(identifiers):
        raise RuntimeError("retention archive selection contains duplicate identities")
    cursor.execute(
        f"""SELECT
            retention_archive_candidates.row_identity::text,
            retention_archive_candidates.source_bytes,
            retention_archive_candidates.source_record,
            encode(
                sha256(convert_to(({normalized_source})::text,'UTF8')),
                'hex'
            ) AS source_discovery_sha256
        FROM ({query}) AS retention_archive_candidates(
            row_identity,source_bytes,source_record
        )
        WHERE retention_archive_candidates.row_identity::text=ANY(%s::text[])
        ORDER BY retention_archive_candidates.row_identity::text""",
        (*params, identifiers),
    )
    candidates: dict[str, dict[str, Any]] = {}
    for raw in cursor.fetchall() or []:
        identity = str(raw[0] or "")
        expected_row = expected.get(identity)
        if expected_row is None or identity in candidates:
            raise RuntimeError("retention archive full fetch returned an unexpected identity")
        source = raw[2]
        if isinstance(source, str):
            source = json.loads(source)
        if not isinstance(source, dict):
            raise RuntimeError("retention archive full fetch returned a non-object source")
        source_discovery_sha256 = str(raw[3] or "")
        if (
            int(raw[1] or 0) != int(expected_row["bytes"])
            or source_discovery_sha256 != expected_row["source_discovery_sha256"]
        ):
            raise RuntimeError("retention archive candidate drifted after discovery")
        candidate = {
            "identity": identity,
            "bytes": int(raw[1] or 0),
            "source": source,
            "source_sha256": _sha256(source),
            "migration_source_sha256": _migration_source_sha256(str(rule.table_name), source),
            "local_migration_receipt_sha256": _local_receipt_from_source(
                table_name=str(rule.table_name),
                source=source,
            ),
            "source_discovery_sha256": source_discovery_sha256,
        }
        if re.fullmatch(r"[0-9a-f]{64}", candidate["migration_source_sha256"]) is None:
            raise RuntimeError("retention archive full fetch produced an invalid source hash")
        candidates[identity] = candidate
    if set(candidates) != set(expected):
        raise RuntimeError("retention archive selected source set changed before full fetch")
    return candidates


def collect_archive_candidates(
    *,
    pool: Any,
    as_of: datetime | None = None,
    max_rows: int = 250,
    excluded_bindings: set[ArchiveBinding] | None = None,
    excluded_discovery_bindings: set[ArchiveDiscoveryBinding] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    """Discover all exact candidates cheaply, then fetch only selected bodies."""

    limit = max(1, min(int(max_rows), 5_000))
    fixed_as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    # Legacy source-row bindings remain authoritative for the later mutation
    # gate. A discovery binding supplements each new archive with the digest
    # needed to exclude its exact remote preimage without downloading it again.
    # Retain this parameter for the collector contract even though a legacy
    # proof without a discovery digest requires one idempotent body refetch to
    # acquire that digest.
    excluded_discovery = excluded_discovery_bindings or set()
    rules = {rule.name: rule for rule in retention_rules(as_of=fixed_as_of)}
    lane_specs = (
        ("completed_large_job_payloads", False),
        ("standup_payload_compaction", True),
        ("standup_rows_after_audit_window", True),
    )
    selected_rows: list[tuple[Any, bool, dict[str, Any]]] = []
    schemas: dict[str, str] = {}
    snapshot_rows: list[dict[str, Any]] = []
    verified_rows = 0
    unarchived_rows = 0
    page_size = min(1_000, max(100, limit))
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            for rule_name, blocked in lane_specs:
                rule = rules[rule_name]
                if rule.table_name not in schemas:
                    schemas[rule.table_name] = _table_schema_sha256(cursor, rule.table_name)
                after_identity = ""
                while True:
                    page = _discover_candidate_page(
                        cursor,
                        rule=rule,
                        blocked=blocked,
                        after_identity=after_identity,
                        limit=page_size,
                    )
                    for discovery in page:
                        discovery_binding: ArchiveDiscoveryBinding = (
                            str(rule.table_name),
                            str(rule.name),
                            str(discovery["identity"]),
                            str(discovery["source_discovery_sha256"]),
                        )
                        snapshot_rows.append(
                            {
                                "source_table": discovery_binding[0],
                                "rule_name": discovery_binding[1],
                                "row_identity": discovery_binding[2],
                                "source_discovery_sha256": discovery_binding[3],
                                "source_schema_sha256": schemas[rule.table_name],
                                "source_bytes": int(discovery["bytes"]),
                            }
                        )
                        if discovery_binding in excluded_discovery:
                            verified_rows += 1
                        else:
                            unarchived_rows += 1
                            if len(selected_rows) < limit:
                                selected_rows.append((rule, blocked, discovery))
                    if len(page) < page_size:
                        break
                    after_identity = str(page[-1]["identity"])

            fetched_by_lane: dict[tuple[str, bool], dict[str, dict[str, Any]]] = {}
            for rule_name, blocked in lane_specs:
                lane_selected = [
                    discovery
                    for selected_rule, selected_blocked, discovery in selected_rows
                    if selected_rule.name == rule_name and selected_blocked == blocked
                ]
                if not lane_selected:
                    continue
                fetched_by_lane[(rule_name, blocked)] = _fetch_exact_candidates(
                    cursor,
                    rule=rules[rule_name],
                    blocked=blocked,
                    selected=lane_selected,
                )
        connection.rollback()
    collected = [
        {
            "rule": rule,
            "candidate": fetched_by_lane[(str(rule.name), blocked)][str(discovery["identity"])],
        }
        for rule, blocked, discovery in selected_rows
    ]
    snapshot_subject = {
        "schema_version": CANDIDATE_SNAPSHOT_SCHEMA_VERSION,
        "as_of": fixed_as_of.isoformat(),
        "rows": snapshot_rows,
    }
    summary = {
        "as_of": fixed_as_of.isoformat(),
        "source_candidate_rows": len(snapshot_rows),
        "previously_verified_rows": verified_rows,
        "unarchived_candidate_rows": unarchived_rows,
        "selected_rows": len(collected),
        "remaining_rows_after_selection": max(0, unarchived_rows - len(collected)),
        "candidate_snapshot_sha256": _sha256(snapshot_subject),
    }
    return collected, schemas, summary


def produce_retention_archives(
    *,
    pool: Any,
    as_of: datetime | None = None,
    max_rows: int = 250,
    state_root: Path | None = None,
    store: IntegratedSystemStore | None = None,
    dry_run: bool = False,
    candidate_collector: Callable[
        ..., tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]
    ] | None = None,
) -> dict[str, Any]:
    collector = candidate_collector or collect_archive_candidates
    canonical_store = store or IntegratedSystemStore()
    excluded_bindings, excluded_discovery_bindings = _verified_local_archive_proofs(
        state_root=state_root,
        store=canonical_store,
    )
    candidates, schemas, collection = collector(
        pool=pool,
        as_of=as_of,
        max_rows=max_rows,
        excluded_bindings=excluded_bindings,
        excluded_discovery_bindings=excluded_discovery_bindings,
    )
    counts: dict[str, int] = {}
    for item in candidates:
        rule_name = item["rule"].name
        counts[rule_name] = counts.get(rule_name, 0) + 1
    if dry_run:
        return {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "mode": "dry_run",
            "candidate_rows": len(candidates),
            "source_candidate_rows": int(collection["source_candidate_rows"]),
            "previously_verified_rows": int(collection["previously_verified_rows"]),
            "remaining_rows_after_run": int(collection["unarchived_candidate_rows"]),
            "archive_set_complete": int(collection["unarchived_candidate_rows"]) == 0,
            "candidate_snapshot_sha256": str(collection["candidate_snapshot_sha256"]),
            "lane_counts": dict(sorted(counts.items())),
            "railway_write_performed": False,
            "local_write_performed": False,
        }

    if not candidates:
        return {
            "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "mode": "no_change",
            "candidate_rows": 0,
            "archived_rows": 0,
            "source_candidate_rows": int(collection["source_candidate_rows"]),
            "previously_verified_rows": int(collection["previously_verified_rows"]),
            "remaining_rows_after_run": int(collection["unarchived_candidate_rows"]),
            "archive_set_complete": int(collection["unarchived_candidate_rows"]) == 0,
            "candidate_snapshot_sha256": str(collection["candidate_snapshot_sha256"]),
            "lane_counts": {},
            "railway_write_performed": False,
            "local_write_performed": False,
        }

    produced: list[dict[str, Any]] = []
    for item in candidates:
        rule = item["rule"]
        produced.append(
            produce_candidate_archive(
                candidate=item["candidate"],
                source_table=rule.table_name,
                rule_name=rule.name,
                source_schema_sha256=schemas[rule.table_name],
                state_root=state_root,
                store=canonical_store,
            )
        )
    run_manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "member_receipt_sha256s": sorted(item["receipt_sha256"] for item in produced),
        "member_count": len(produced),
        "lane_counts": dict(sorted(counts.items())),
        "receipt_manifest_sha256": _sha256(sorted(item["receipt_sha256"] for item in produced)),
        "as_of": str(collection["as_of"]),
        "source_candidate_rows": int(collection["source_candidate_rows"]),
        "previously_verified_rows": int(collection["previously_verified_rows"]),
        "unarchived_candidate_rows_before_run": int(collection["unarchived_candidate_rows"]),
        "remaining_rows_after_run": int(collection["remaining_rows_after_selection"]),
        "archive_set_complete": int(collection["remaining_rows_after_selection"]) == 0,
        "candidate_snapshot_sha256": str(collection["candidate_snapshot_sha256"]),
        "railway_write_performed": False,
    }
    root = _state_root(state_root)
    run_file = _write_content_addressed(root=root, kind="run-manifests", payload=run_manifest)
    canonical_store.put_artifact(
        content_sha256=run_file["sha256"],
        artifact_kind="railway_retention_archive_run_manifest_v2",
        logical_ref=f"state://{run_file['relative_path']}",
        byte_size=run_file["bytes"],
        media_type="application/json",
        metadata={"member_count": len(produced), "lane_count": len(counts)},
    )
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "mode": "local_apply",
        "candidate_rows": len(candidates),
        "archived_rows": len(produced),
        "source_candidate_rows": int(collection["source_candidate_rows"]),
        "previously_verified_rows": int(collection["previously_verified_rows"]),
        "remaining_rows_after_run": int(collection["remaining_rows_after_selection"]),
        "archive_set_complete": int(collection["remaining_rows_after_selection"]) == 0,
        "candidate_snapshot_sha256": str(collection["candidate_snapshot_sha256"]),
        "lane_counts": dict(sorted(counts.items())),
        "receipt_manifest_sha256": run_manifest["receipt_manifest_sha256"],
        "run_manifest_relative_path": run_file["relative_path"],
        "run_manifest_sha256": run_file["sha256"],
        "railway_write_performed": False,
        "local_write_performed": bool(produced),
    }
