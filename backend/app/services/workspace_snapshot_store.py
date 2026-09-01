from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from app.utils.ai_clone_clock import as_utc

try:
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    dict_row = None  # type: ignore
    Jsonb = None  # type: ignore

try:
    from app.services.open_brain_db import get_pool
except Exception:  # pragma: no cover
    get_pool = None  # type: ignore


_RETAINED_SNAPSHOT_CONTRACT = "railway_retained_workspace_snapshot_receipt/v1"
_CLEAR_ARCHIVE_PROOF_SQL = """COALESCE(workspace_snapshots.metadata, '{}'::jsonb)
    - 'local_archive_verified' - 'local_archive_receipt_sha256' - 'retention_contract'
    - 'retention_row_identity' - 'retention_workspace_key' - 'retention_snapshot_type'
    - 'retention_replacement_schema_version'"""
_CANONICAL_UTC_OBSERVATION_SQL_RE = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]{1,6})?Z$"
)
_LEGACY_UTC_OBSERVATION_SQL_RE = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]{1,6})?(Z|[+]00:00)$"
)


def _maybe_pool():
    if get_pool is None or dict_row is None or Jsonb is None:
        return None
    try:
        return get_pool()
    except Exception:
        return None


def _row_to_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "workspace_key": row["workspace_key"],
        "snapshot_type": row["snapshot_type"],
        "payload": row.get("payload") or {},
        "metadata": row.get("metadata") or {},
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_snapshot(workspace_key: str, snapshot_type: str) -> Optional[dict[str, Any]]:
    pool = _maybe_pool()
    if pool is None:
        return None
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                FROM workspace_snapshots
                WHERE workspace_key = %s AND snapshot_type = %s
                """,
                (workspace_key, snapshot_type),
            )
            row = cur.fetchone()
    return _row_to_snapshot(row) if row else None


def get_snapshot_payload(workspace_key: str, snapshot_type: str) -> Optional[dict[str, Any]]:
    snapshot = get_snapshot(workspace_key, snapshot_type)
    if not snapshot:
        return None
    payload = snapshot.get("payload")
    return payload if isinstance(payload, dict) else None


def list_snapshot_payloads(workspace_key: str) -> dict[str, dict[str, Any]]:
    pool = _maybe_pool()
    if pool is None:
        return {}
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                FROM workspace_snapshots
                WHERE workspace_key = %s
                """,
                (workspace_key,),
            )
            rows = cur.fetchall() or []
    payloads: dict[str, dict[str, Any]] = {}
    for row in rows:
        snapshot = _row_to_snapshot(row)
        payload = snapshot.get("payload")
        if isinstance(payload, dict):
            payloads[snapshot["snapshot_type"]] = payload
    return payloads


def delete_snapshot_types(
    workspace_key: str,
    snapshot_types: list[str],
) -> int:
    """Delete an explicit, bounded set of snapshot rows and return the row count."""
    cleaned = list(dict.fromkeys(str(value or "").strip() for value in snapshot_types if str(value or "").strip()))
    if not cleaned:
        return 0
    if len(cleaned) > 100:
        raise ValueError("Snapshot cleanup is limited to 100 explicit snapshot types.")
    pool = _maybe_pool()
    if pool is None:
        return 0
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                DELETE FROM workspace_snapshots
                WHERE workspace_key = %s AND snapshot_type = ANY(%s)
                  AND COALESCE(metadata->>'retained_contract','') <> %s
                """,
                (workspace_key, cleaned, _RETAINED_SNAPSHOT_CONTRACT),
            )
            deleted = int(cur.rowcount or 0)
        conn.commit()
    return deleted


def upsert_snapshot(
    workspace_key: str,
    snapshot_type: str,
    payload: dict[str, Any],
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    pool = _maybe_pool()
    if pool is None:
        return None
    snapshot_id = str(uuid4())
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO workspace_snapshots (id, workspace_key, snapshot_type, payload, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_key, snapshot_type) DO UPDATE
                SET payload = EXCLUDED.payload,
                    metadata = (""" + _CLEAR_ARCHIVE_PROOF_SQL + """) || EXCLUDED.metadata,
                    updated_at = NOW()
                WHERE COALESCE(workspace_snapshots.metadata->>'retained_contract','') <> %s
                RETURNING id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                """,
                (
                    snapshot_id,
                    workspace_key,
                    snapshot_type,
                    Jsonb(payload),
                    Jsonb(metadata or {}),
                    _RETAINED_SNAPSHOT_CONTRACT,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Archived workspace snapshot is immutable; restore it before replacement.")
        conn.commit()
    return _row_to_snapshot(row) if row else None


def upsert_snapshot_monotonic(
    workspace_key: str,
    snapshot_type: str,
    payload: dict[str, Any],
    *,
    generated_at: datetime,
    semantic_observed_at: datetime | None = None,
    semantic_order_required: bool = False,
    semantic_revision: int | None = None,
    semantic_revision_field: str | None = None,
    semantic_revision_required: bool = False,
    semantic_revision_strict_increment: bool = False,
    semantic_identity_fields: tuple[str, ...] = (),
    semantic_legacy_migration_revision: int | None = None,
    semantic_legacy_migration_schemas: dict[str, tuple[str, ...]] | None = None,
    semantic_legacy_migration_required_values: dict[str, Any] | None = None,
    semantic_legacy_migration_max_bytes: int | None = None,
    semantic_legacy_migration_expected_payload: dict[str, Any] | None = None,
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[Optional[dict[str, Any]], bool]:
    """Store a snapshot only when its governing source timestamp is newer.

    Most projections are ordered by ``generated_at``. Callers with a validated
    semantic clock may instead provide ``semantic_observed_at``; projection or
    browser receipt time can then never overwrite a newer source observation.
    A caller may also supply a canonical semantic revision. In that case equal
    observations advance only by the governed revision, never by projection or
    browser receipt time. Strict-increment mode rejects skipped revisions.
    A caller may additionally describe one closed legacy-schema migration. It
    is evaluated in the same ``ON CONFLICT`` statement and can only install the
    named target revision at the same observation and identity. Missing legacy
    revisions are never treated as revision zero.
    """
    pool = _maybe_pool()
    if pool is None:
        return None, False
    normalized_generated_at = as_utc(generated_at)
    normalized_semantic_observed_at = semantic_observed_at
    if normalized_semantic_observed_at is not None:
        if (
            normalized_semantic_observed_at.tzinfo is None
            or normalized_semantic_observed_at.utcoffset() is None
        ):
            raise ValueError("semantic_observed_at must include a timezone offset")
        normalized_semantic_observed_at = as_utc(
            normalized_semantic_observed_at
        )
    use_semantic_order = (
        semantic_order_required or normalized_semantic_observed_at is not None
    )
    if semantic_revision is not None and (
        not isinstance(semantic_revision, int)
        or isinstance(semantic_revision, bool)
        or semantic_revision < 1
    ):
        raise ValueError("semantic_revision must be a positive integer")
    if semantic_revision_field is not None and not re.fullmatch(
        r"[a-z][a-z0-9_]{0,63}", semantic_revision_field
    ):
        raise ValueError("semantic_revision_field is invalid")
    if (semantic_revision is None) != (semantic_revision_field is None):
        raise ValueError(
            "semantic_revision and semantic_revision_field must be supplied together"
        )
    if semantic_revision_required and (
        semantic_revision is None or semantic_revision_field is None
    ):
        raise ValueError("a canonical semantic revision is required")
    if semantic_revision_strict_increment and semantic_revision is None:
        raise ValueError("strict semantic revision ordering requires a revision")
    if (
        len(semantic_identity_fields) > 8
        or len(set(semantic_identity_fields)) != len(semantic_identity_fields)
        or any(
            re.fullmatch(r"[a-z][a-z0-9_]{0,63}", field) is None
            for field in semantic_identity_fields
        )
    ):
        raise ValueError("semantic_identity_fields are invalid")
    if semantic_identity_fields and semantic_revision is None:
        raise ValueError("semantic identity matching requires a revision")
    legacy_migration_configured = any(
        value is not None
        for value in (
            semantic_legacy_migration_revision,
            semantic_legacy_migration_schemas,
            semantic_legacy_migration_required_values,
            semantic_legacy_migration_max_bytes,
            semantic_legacy_migration_expected_payload,
        )
    )
    if legacy_migration_configured and (
        semantic_legacy_migration_revision is None
        or semantic_legacy_migration_schemas is None
        or semantic_legacy_migration_required_values is None
        or semantic_legacy_migration_max_bytes is None
        or semantic_legacy_migration_expected_payload is None
    ):
        raise ValueError("legacy semantic migration requires a complete contract")
    if legacy_migration_configured:
        if (
            not semantic_revision_strict_increment
            or semantic_revision is None
            or not isinstance(semantic_legacy_migration_revision, int)
            or isinstance(semantic_legacy_migration_revision, bool)
            or semantic_legacy_migration_revision < 1
            or not isinstance(semantic_legacy_migration_max_bytes, int)
            or isinstance(semantic_legacy_migration_max_bytes, bool)
            or not 1 <= semantic_legacy_migration_max_bytes <= 2 * 1024 * 1024
            or not semantic_identity_fields
            or not isinstance(semantic_legacy_migration_expected_payload, dict)
        ):
            raise ValueError("legacy semantic migration contract is invalid")
        if (
            not semantic_legacy_migration_schemas
            or len(semantic_legacy_migration_schemas) > 8
            or any(
                not isinstance(schema, str)
                or not schema
                or len(schema) > 120
                or not isinstance(fields, tuple)
                or not fields
                or len(fields) > 64
                or len(set(fields)) != len(fields)
                or "schema_version" not in fields
                or any(
                    re.fullmatch(r"[a-z][a-z0-9_]{0,63}", field) is None
                    for field in fields
                )
                for schema, fields in semantic_legacy_migration_schemas.items()
            )
        ):
            raise ValueError("legacy semantic migration schemas are invalid")
        if (
            len(semantic_legacy_migration_required_values) > 8
            or any(
                re.fullmatch(r"[a-z][a-z0-9_]{0,63}", field) is None
                for field in semantic_legacy_migration_required_values
            )
        ):
            raise ValueError("legacy semantic migration required values are invalid")
    semantic_identity_values_list: list[str] = []
    for field in semantic_identity_fields:
        raw_identity = payload.get(field)
        if (
            not isinstance(raw_identity, str)
            or raw_identity != raw_identity.strip()
            or not raw_identity
            or len(raw_identity) > 200
        ):
            raise ValueError("semantic identity values are missing or invalid")
        semantic_identity_values_list.append(raw_identity)
    semantic_identity_values = tuple(semantic_identity_values_list)
    use_semantic_revision = (
        use_semantic_order
        and semantic_revision is not None
        and semantic_revision_field is not None
    )
    semantic_schema_value: str | None = None
    if use_semantic_revision:
        raw_semantic_schema = payload.get("schema_version")
        if (
            not isinstance(raw_semantic_schema, str)
            or not raw_semantic_schema
            or raw_semantic_schema != raw_semantic_schema.strip()
            or len(raw_semantic_schema) > 120
        ):
            raise ValueError(
                "semantic revision ordering requires an exact payload schema"
            )
        semantic_schema_value = raw_semantic_schema
    comparison_field = (
        "observed_at"
        if use_semantic_order
        else "generated_at"
    )
    comparison_value = (
        normalized_semantic_observed_at
        if use_semantic_order
        else normalized_generated_at
    )
    allow_conflict_update = comparison_value is not None
    snapshot_id = str(uuid4())
    effective_metadata = {
        **(metadata or {}),
        "payload_generated_at": normalized_generated_at.isoformat(),
        **(
            {
                "payload_semantic_observed_at": (
                    normalized_semantic_observed_at.isoformat()
                )
            }
            if normalized_semantic_observed_at is not None
            else {}
        ),
        **(
            {"payload_semantic_revision": semantic_revision}
            if semantic_revision is not None
            else {}
        ),
    }
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            existing_observation_text_sql = (
                "COALESCE(workspace_snapshots.payload->>"
                f"'{comparison_field}', '')"
            )
            existing_order_observation_sql_re = (
                _CANONICAL_UTC_OBSERVATION_SQL_RE
                if use_semantic_order
                else _LEGACY_UTC_OBSERVATION_SQL_RE
            )
            existing_observation_is_valid_sql = (
                "jsonb_typeof(workspace_snapshots.payload->"
                f"'{comparison_field}') = 'string' AND "
                f"{existing_observation_text_sql} ~ "
                f"'{existing_order_observation_sql_re}'"
            )
            existing_legacy_observation_is_valid_sql = (
                "jsonb_typeof(workspace_snapshots.payload->"
                f"'{comparison_field}') = 'string' AND "
                f"{existing_observation_text_sql} ~ "
                f"'{_LEGACY_UTC_OBSERVATION_SQL_RE}'"
            )
            existing_observation_sql = f"""CASE
                    WHEN {existing_observation_is_valid_sql}
                    THEN (workspace_snapshots.payload->>'{comparison_field}')::timestamptz
                    ELSE NULL::timestamptz
                END"""
            existing_legacy_observation_sql = f"""CASE
                    WHEN {existing_legacy_observation_is_valid_sql}
                    THEN (workspace_snapshots.payload->>'{comparison_field}')::timestamptz
                    ELSE NULL::timestamptz
                END"""
            order_sql = (
                f"{existing_observation_is_valid_sql} AND "
                f"{existing_observation_sql} < %s"
            )
            order_params: tuple[Any, ...] = (comparison_value,)
            if use_semantic_revision:
                existing_revision_is_valid_sql = f"""COALESCE(
                    workspace_snapshots.payload->>'{semantic_revision_field}', ''
                ) ~ '^[1-9][0-9]{{0,8}}$'"""
                existing_revision_sql = f"""CASE
                    WHEN {existing_revision_is_valid_sql}
                    THEN (workspace_snapshots.payload->>'{semantic_revision_field}')::bigint
                    ELSE 0
                END"""
                revision_comparison = (
                    f"{existing_revision_is_valid_sql} AND "
                    f"{existing_revision_sql} + 1 = %s"
                    if semantic_revision_strict_increment
                    else (
                        f"{existing_revision_is_valid_sql} AND "
                        f"{existing_revision_sql} < %s"
                    )
                )
                identity_comparison = " AND ".join(
                    "jsonb_typeof(workspace_snapshots.payload->"
                    f"'{field}') = 'string' AND "
                    f"workspace_snapshots.payload->>'{field}' = %s"
                    for field in semantic_identity_fields
                )
                canonical_same_observation_sql = (
                    f"{existing_observation_is_valid_sql} AND "
                    f"{existing_observation_sql} = %s AND "
                    "jsonb_typeof(workspace_snapshots.payload->"
                    "'schema_version') = 'string' AND "
                    "workspace_snapshots.payload->>'schema_version' = %s"
                )
                if identity_comparison:
                    canonical_same_observation_sql += (
                        f" AND {identity_comparison}"
                    )
                canonical_same_observation_sql += f" AND ({revision_comparison})"
                same_observation_sql = canonical_same_observation_sql
                same_observation_params: tuple[Any, ...] = (
                    comparison_value,
                    semantic_schema_value,
                    *semantic_identity_values,
                    semantic_revision,
                )
                if (
                    legacy_migration_configured
                    and semantic_revision == semantic_legacy_migration_revision
                ):
                    legacy_schema_clauses: list[str] = []
                    legacy_schema_params: list[Any] = []
                    for schema, fields in sorted(
                        semantic_legacy_migration_schemas.items()
                    ):
                        legacy_schema_clauses.append(
                            "("
                            "workspace_snapshots.payload->>'schema_version' = %s "
                            "AND ARRAY(SELECT legacy_key FROM "
                            "jsonb_object_keys(workspace_snapshots.payload) "
                            "AS legacy_keys(legacy_key) "
                            'ORDER BY legacy_key COLLATE "C") '
                            "= %s::text[]"
                            ")"
                        )
                        legacy_schema_params.extend((schema, sorted(fields)))
                    required_value_clauses = [
                        f"workspace_snapshots.payload->'{field}' = %s"
                        for field in sorted(
                            semantic_legacy_migration_required_values
                        )
                    ]
                    required_value_params = [
                        Jsonb(semantic_legacy_migration_required_values[field])
                        for field in sorted(
                            semantic_legacy_migration_required_values
                        )
                    ]
                    legacy_comparison = (
                        "jsonb_typeof(workspace_snapshots.payload) = 'object' "
                        "AND octet_length(workspace_snapshots.payload::text) <= %s "
                        "AND workspace_snapshots.payload = %s "
                        f"AND ({' OR '.join(legacy_schema_clauses)})"
                    )
                    if required_value_clauses:
                        legacy_comparison += (
                            f" AND {' AND '.join(required_value_clauses)}"
                        )
                    legacy_same_observation_sql = (
                        f"{existing_legacy_observation_is_valid_sql} AND "
                        f"{existing_legacy_observation_sql} = %s"
                    )
                    if identity_comparison:
                        legacy_same_observation_sql += (
                            f" AND {identity_comparison}"
                        )
                    legacy_same_observation_sql += f" AND ({legacy_comparison})"
                    same_observation_sql = (
                        f"(({canonical_same_observation_sql}) OR "
                        f"({legacy_same_observation_sql}))"
                    )
                    same_observation_params = (
                        comparison_value,
                        semantic_schema_value,
                        *semantic_identity_values,
                        semantic_revision,
                        comparison_value,
                        *semantic_identity_values,
                        semantic_legacy_migration_max_bytes,
                        Jsonb(semantic_legacy_migration_expected_payload),
                        *legacy_schema_params,
                        *required_value_params,
                    )
                order_sql = (
                    f"(({existing_observation_is_valid_sql} AND "
                    f"{existing_observation_sql} < %s) OR "
                    f"({same_observation_sql}))"
                )
                order_params = (
                    comparison_value,
                    *same_observation_params,
                )
            monotonic_upsert_sql = f"""
                INSERT INTO workspace_snapshots (id, workspace_key, snapshot_type, payload, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_key, snapshot_type) DO UPDATE
                SET payload = EXCLUDED.payload,
                    metadata = ({_CLEAR_ARCHIVE_PROOF_SQL}) || EXCLUDED.metadata,
                    updated_at = NOW()
                WHERE COALESCE(workspace_snapshots.metadata->>'retained_contract','') <> %s
                  AND %s
                  AND {order_sql}
                RETURNING id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
            """
            cur.execute(
                monotonic_upsert_sql,
                (
                    snapshot_id,
                    workspace_key,
                    snapshot_type,
                    Jsonb(payload),
                    Jsonb(effective_metadata),
                    _RETAINED_SNAPSHOT_CONTRACT,
                    allow_conflict_update,
                    *order_params,
                ),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """
                    SELECT id, workspace_key, snapshot_type, payload, metadata, created_at, updated_at
                    FROM workspace_snapshots
                    WHERE workspace_key = %s AND snapshot_type = %s
                    """,
                    (workspace_key, snapshot_type),
                )
                current = cur.fetchone()
                if current and str((current.get("metadata") or {}).get("retained_contract") or "") == _RETAINED_SNAPSHOT_CONTRACT:
                    raise ValueError("Archived workspace snapshot is immutable; restore it before replacement.")
            else:
                current = None
        conn.commit()
    if row is not None:
        return _row_to_snapshot(row), True
    return (_row_to_snapshot(current) if current else None), False
