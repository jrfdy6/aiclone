from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from app.services.railway_retention_service import (
    _LOCAL_PROOF_BINDING_FIELDS,
    RETENTION_LOCK_ID,
    _canonical_json,
    _migration_source_sha256,
    _normalize_receipt_proofs,
    _normalized_utc_timestamp,
)


_MUTABLE_TABLES = {"automation_runs", "local_codex_jobs", "standups", "workspace_snapshots"}
_ROLLBACK_BATCH_SIZE = 1_000


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _columns(connection: Any, table: str) -> list[str]:
    rows = connection.execute(
        """SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
        (table,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _column_types(connection: Any, table: str) -> dict[str, str]:
    rows = connection.execute(
        """SELECT column_name,data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
        (table,),
    ).fetchall()
    return {str(name): str(data_type) for name, data_type in rows}


def _schema_sha256(connection: Any, table: str) -> str:
    rows = connection.execute(
        """SELECT table_name,ordinal_position,column_name,data_type,udt_name,is_nullable
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=ANY(%s) ORDER BY table_name,ordinal_position""",
        ([table, "local_codex_job_artifacts"] if table == "local_codex_jobs" else [table],),
    ).fetchall()
    return _sha256([list(row) for row in rows])


def _receipt(connection: Any, receipt_id: str, *, lock: bool = False) -> tuple[Any, ...] | None:
    suffix = " FOR UPDATE" if lock else ""
    return connection.execute(
        """SELECT lifecycle_status,as_of,backup_manifest_sha256,rules_sha256,plan_sha256,plan_json
        FROM railway_retention_receipts WHERE receipt_id=%s""" + suffix,
        (receipt_id,),
    ).fetchone()


def _validate_plan(receipt: tuple[Any, ...]) -> dict[str, Any]:
    payload = receipt[5] if isinstance(receipt[5], dict) else json.loads(receipt[5])
    if payload.get("schema_version") != "railway_retention_plan/v4":
        raise ValueError("backup retention plan schema is unsupported")
    expected = str(payload.get("plan_sha256") or "")
    core = {key: value for key, value in payload.items() if key != "plan_sha256"}
    if expected != receipt[4] or _sha256(core) != expected:
        raise ValueError("backup retention plan hash is invalid")
    raw_proofs = payload.get("verified_local_migration_proofs")
    if not isinstance(raw_proofs, list):
        raise ValueError("backup retention plan lacks exact local migration proof bindings")
    normalized = _normalize_receipt_proofs(
        {
            str(item.get("receipt_sha256") or ""): {
                field: str(item.get(field) or "") for field in _LOCAL_PROOF_BINDING_FIELDS
            }
            for item in raw_proofs
            if isinstance(item, dict)
        }
    )
    if list(normalized) != raw_proofs or [item["receipt_sha256"] for item in normalized] != list(
        payload.get("verified_local_migration_receipts") or []
    ):
        raise ValueError("backup retention plan local migration proof bindings are invalid")
    automation_manifest = payload.get("verified_local_automation_proof_manifest")
    if not isinstance(automation_manifest, dict) or set(automation_manifest) != {
        "rows",
        "manifest_sha256",
    } or not isinstance(automation_manifest.get("rows"), int) or int(automation_manifest["rows"]) < 0 or re.fullmatch(
        r"[0-9a-f]{64}", str(automation_manifest.get("manifest_sha256") or "")
    ) is None:
        raise ValueError("backup retention plan lacks the local automation proof manifest")
    return payload


def _chunks(values: list[str]) -> list[list[str]]:
    return [values[index : index + _ROLLBACK_BATCH_SIZE] for index in range(0, len(values), _ROLLBACK_BATCH_SIZE)]


def _automation_aggregate_receipts(connection: Any, receipt_id: str) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """SELECT dimension_key,bucket_date,automation_id,automation_name,normalized_status,
        workspace_key,source,runtime,run_count,delivered_count,total_duration_ms,
        first_run_at,last_run_at,source_row_ids,source_row_ids_sha256
        FROM automation_run_daily_receipts WHERE retention_receipt_id=%s
        ORDER BY dimension_key""",
        (receipt_id,),
    ).fetchall()
    receipts: dict[str, dict[str, Any]] = {}
    all_identifiers: set[str] = set()
    for row in rows:
        dimension_key = str(row[0] or "")
        identifiers_payload = row[13] if isinstance(row[13], list) else json.loads(row[13])
        if not isinstance(identifiers_payload, list):
            raise ValueError("automation aggregate source IDs are not a list")
        identifiers = [str(item) for item in identifiers_payload]
        if (
            not dimension_key
            or any(not item for item in identifiers)
            or len(set(identifiers)) != len(identifiers)
            or all_identifiers.intersection(identifiers)
            or int(row[8] or 0) != len(identifiers)
            or str(row[14] or "") != _sha256(identifiers)
        ):
            raise ValueError("automation aggregate count/hash contract is invalid")
        dimensions = (
            str(row[1]),
            row[2],
            row[3],
            str(row[4] or "unknown"),
            row[5],
            row[6],
            row[7],
        )
        if dimension_key != _sha256(list(dimensions)) or dimension_key in receipts:
            raise ValueError("automation aggregate dimension contract is invalid")
        all_identifiers.update(identifiers)
        receipts[dimension_key] = {
            "dimensions": dimensions,
            "run_count": int(row[8] or 0),
            "delivered_count": int(row[9] or 0),
            "total_duration_ms": int(row[10] or 0),
            "first_run_at": _normalized_utc_timestamp(row[11]),
            "last_run_at": _normalized_utc_timestamp(row[12]),
            "source_row_ids": identifiers,
            "source_row_ids_sha256": str(row[14] or ""),
        }
    return receipts


def _automation_snapshots(connection: Any, identities: list[str]) -> dict[str, Any]:
    snapshots: dict[str, Any] = {}
    for batch in _chunks(sorted(set(identities))):
        rows = connection.execute(
            """SELECT id::text,to_jsonb(t) FROM automation_runs t
            WHERE id::text=ANY(%s) ORDER BY id::text""",
            (batch,),
        ).fetchall()
        for identity, source in rows:
            key = str(identity)
            if key in snapshots:
                raise ValueError("duplicate automation row identity in rollback source")
            snapshots[key] = source
    return snapshots


def _validate_automation_aggregate_sources(
    receipts: dict[str, dict[str, Any]],
    restored_sources: dict[str, Any],
) -> None:
    groups: dict[tuple[Any, ...], list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for identity in sorted(restored_sources):
        source = dict(restored_sources[identity] or {})
        timestamp = _normalized_utc_timestamp(
            source.get("finished_at") or source.get("run_at") or source.get("created_at")
        )
        dimensions = (
            str(timestamp)[:10],
            source.get("automation_id"),
            source.get("automation_name"),
            str(source.get("status") or "unknown").lower(),
            source.get("workspace_key"),
            source.get("source"),
            source.get("runtime"),
        )
        groups[dimensions].append((identity, source))
    expected: dict[str, dict[str, Any]] = {}
    for dimensions, members in groups.items():
        identifiers = [identity for identity, _source in members]
        timestamps = sorted(
            timestamp
            for timestamp in (
                _normalized_utc_timestamp(
                    source.get("finished_at") or source.get("run_at") or source.get("created_at")
                )
                for _identity, source in members
            )
            if timestamp is not None
        )
        expected[_sha256(list(dimensions))] = {
            "dimensions": dimensions,
            "run_count": len(members),
            "delivered_count": sum(1 for _identity, source in members if source.get("delivered") is True),
            "total_duration_ms": sum(
                max(0, int(source.get("duration_ms") or 0)) for _identity, source in members
            ),
            "first_run_at": timestamps[0] if timestamps else None,
            "last_run_at": timestamps[-1] if timestamps else None,
            "source_row_ids": identifiers,
            "source_row_ids_sha256": _sha256(identifiers),
        }
    if receipts != expected:
        raise ValueError("automation aggregate receipts do not match restored source rows")


def _row_receipts(connection: Any, receipt_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT rule_name,table_name,row_identity,mutation_kind,source_row_sha256,target_row_sha256,
        source_schema_sha256,local_migration_receipt_sha256
        FROM railway_retention_row_receipts WHERE retention_receipt_id=%s
        ORDER BY rule_name,row_identity""",
        (receipt_id,),
    ).fetchall()
    return [
        {
            "rule_name": str(row[0]),
            "table_name": str(row[1]),
            "row_identity": str(row[2]),
            "mutation_kind": str(row[3]),
            "source_row_sha256": str(row[4]),
            "target_row_sha256": str(row[5]) if row[5] is not None else None,
            "source_schema_sha256": str(row[6] or ""),
            "local_migration_receipt_sha256": str(row[7] or ""),
        }
        for row in rows
    ]


def _row_snapshot(connection: Any, *, table_name: str, identity: str) -> Any | None:
    if table_name not in _MUTABLE_TABLES:
        raise ValueError("retention row receipt names an unsupported table")
    if table_name == "local_codex_jobs":
        row = connection.execute(
            """SELECT jsonb_build_object(
                'row',to_jsonb(t),
                'child_artifacts',COALESCE((
                    SELECT jsonb_agg(to_jsonb(a) ORDER BY a.artifact_id)
                    FROM local_codex_job_artifacts a WHERE a.job_id=t.id
                ),'[]'::jsonb)
            ) FROM local_codex_jobs t WHERE t.id::text=%s""",
            (identity,),
        ).fetchone()
    else:
        row = connection.execute(
            sql.SQL("SELECT to_jsonb(t) FROM {} t WHERE t.id::text=%s").format(sql.Identifier(table_name)),
            (identity,),
        ).fetchone()
    return row[0] if row else None


def _row_values(connection: Any, *, table_name: str, identity: str) -> tuple[list[str], tuple[Any, ...]] | None:
    columns = _columns(connection, table_name)
    if not columns:
        raise ValueError(f"restored backup is missing table {table_name}")
    query = sql.SQL("SELECT {} FROM {} WHERE id::text=%s").format(
        sql.SQL(",").join(sql.Identifier(name) for name in columns),
        sql.Identifier(table_name),
    )
    row = connection.execute(query, (identity,)).fetchone()
    return (columns, row) if row else None


def _restore_row(
    live_connection: Any,
    restored_connection: Any,
    *,
    table_name: str,
    identity: str,
    expected_target: Any | None,
) -> None:
    restored = _row_values(restored_connection, table_name=table_name, identity=identity)
    if restored is None:
        raise ValueError(f"restored backup is missing exact {table_name} row {identity}")
    columns, row = restored
    if columns != _columns(live_connection, table_name):
        raise ValueError(f"live and restored {table_name} schemas do not match")
    id_index = columns.index("id")
    column_types = _column_types(restored_connection, table_name)

    def adapted(name: str, value: Any) -> Any:
        return Jsonb(value) if column_types.get(name) in {"json", "jsonb"} and value is not None else value
    exists = live_connection.execute(
        sql.SQL("SELECT 1 FROM {} WHERE id::text=%s").format(sql.Identifier(table_name)),
        (identity,),
    ).fetchone()
    if exists:
        if expected_target is None:
            raise RuntimeError("retention rollback expected an absent target row")
        update_columns = [name for name in columns if name != "id"]
        update_values = [adapted(name, row[columns.index(name)]) for name in update_columns]
        expected_parent = expected_target
        if table_name == "local_codex_jobs":
            expected_children = list(dict(expected_target).get("child_artifacts") or [])
            if expected_children:
                raise ValueError("compacted job target unexpectedly retains child artifacts")
            expected_parent = dict(expected_target).get("row")
        statement = sql.SQL("UPDATE {} SET {} WHERE id=%s AND to_jsonb({})=%s::jsonb").format(
            sql.Identifier(table_name),
            sql.SQL(",").join(
                sql.Composed([sql.Identifier(name), sql.SQL("="), sql.Placeholder()])
                for name in update_columns
            ),
            sql.Identifier(table_name),
        )
        updated = live_connection.execute(
            statement,
            (*update_values, row[id_index], _canonical_json(expected_parent)),
        ).rowcount
        if updated != 1:
            raise RuntimeError("retention rollback target changed after conflict preflight")
    else:
        if expected_target is not None:
            raise RuntimeError("retention rollback target disappeared after conflict preflight")
        statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(",").join(sql.Identifier(name) for name in columns),
            sql.SQL(",").join(sql.Placeholder() for _ in columns),
        )
        live_connection.execute(statement, tuple(adapted(name, value) for name, value in zip(columns, row, strict=True)))

    if table_name == "local_codex_jobs":
        artifact_columns = _columns(restored_connection, "local_codex_job_artifacts")
        if artifact_columns != _columns(live_connection, "local_codex_job_artifacts"):
            raise ValueError("live and restored local job artifact schemas do not match")
        remaining = live_connection.execute(
            "SELECT COUNT(*) FROM local_codex_job_artifacts WHERE job_id=%s",
            (identity,),
        ).fetchone()[0]
        if int(remaining or 0) != 0:
            raise RuntimeError("retention rollback found an unplanned job artifact")
        artifact_query = sql.SQL("SELECT {} FROM local_codex_job_artifacts WHERE job_id=%s ORDER BY artifact_id").format(
            sql.SQL(",").join(sql.Identifier(name) for name in artifact_columns)
        )
        artifact_rows = restored_connection.execute(artifact_query, (identity,)).fetchall()
        if artifact_rows:
            insert = sql.SQL("INSERT INTO local_codex_job_artifacts ({}) VALUES ({})").format(
                sql.SQL(",").join(sql.Identifier(name) for name in artifact_columns),
                sql.SQL(",").join(sql.Placeholder() for _ in artifact_columns),
            )
            for artifact_row in artifact_rows:
                live_connection.execute(insert, artifact_row)
    live = _row_snapshot(live_connection, table_name=table_name, identity=identity)
    restored = _row_snapshot(restored_connection, table_name=table_name, identity=identity)
    if live is None or restored is None or _sha256(live) != _sha256(restored):
        raise RuntimeError("retention rollback postimage verification failed")


def _restore_automation_rows(
    live_connection: Any,
    restored_connection: Any,
    *,
    identities: list[str],
) -> None:
    if not identities:
        return
    columns = _columns(restored_connection, "automation_runs")
    if not columns or columns != _columns(live_connection, "automation_runs"):
        raise ValueError("live and restored automation_runs schemas do not match")
    column_types = _column_types(restored_connection, "automation_runs")
    statement = sql.SQL("INSERT INTO automation_runs ({}) VALUES ({})").format(
        sql.SQL(",").join(sql.Identifier(name) for name in columns),
        sql.SQL(",").join(sql.Placeholder() for _ in columns),
    )

    def adapted(name: str, value: Any) -> Any:
        return Jsonb(value) if column_types.get(name) in {"json", "jsonb"} and value is not None else value

    for batch in _chunks(sorted(set(identities))):
        query = sql.SQL("SELECT {} FROM automation_runs WHERE id::text=ANY(%s) ORDER BY id::text").format(
            sql.SQL(",").join(sql.Identifier(name) for name in columns)
        )
        rows = restored_connection.execute(query, (batch,)).fetchall()
        if len(rows) != len(batch):
            raise ValueError("restored backup lost an automation row during rollback")
        values = [
            tuple(adapted(name, value) for name, value in zip(columns, row, strict=True))
            for row in rows
        ]
        with live_connection.cursor() as cursor:
            cursor.executemany(statement, values)
            if int(cursor.rowcount or 0) != len(values):
                raise RuntimeError("automation rollback bulk insert affected-row mismatch")
    live = _automation_snapshots(live_connection, identities)
    restored = _automation_snapshots(restored_connection, identities)
    if set(live) != set(restored) or any(_sha256(live[key]) != _sha256(restored[key]) for key in restored):
        raise RuntimeError("automation rollback bulk postimage verification failed")


def _lock_restore_targets(connection: Any, source_records: list[dict[str, Any]]) -> None:
    identities_by_table: dict[str, list[str]] = {}
    for record in source_records:
        identities_by_table.setdefault(record["table_name"], []).append(record["row_identity"])
    for table_name in sorted(identities_by_table):
        identities = sorted(set(identities_by_table[table_name]))
        for batch in _chunks(identities):
            connection.execute(
                sql.SQL("SELECT id FROM {} WHERE id::text=ANY(%s) ORDER BY id::text FOR UPDATE").format(
                    sql.Identifier(table_name)
                ),
                (batch,),
            ).fetchall()
            if table_name == "local_codex_jobs":
                connection.execute(
                    """SELECT artifact_id FROM local_codex_job_artifacts
                    WHERE job_id=ANY(%s) ORDER BY artifact_id FOR UPDATE""",
                    (batch,),
                ).fetchall()


def _planned_rule_counts(plan: dict[str, Any]) -> dict[str, int]:
    return {
        str(item.get("rule") or ""): int(item.get("candidate_rows") or 0)
        for item in (plan.get("rules") or [])
        if isinstance(item, dict)
    }


def rollback_retention(
    *,
    live_connection: Any,
    restored_connection: Any,
    receipt_id: str,
    expected_backup_manifest_sha256: str,
    apply: bool = False,
) -> dict[str, Any]:
    """Restore only rows changed by one receipt; reject every concurrent difference."""

    if not receipt_id.strip():
        raise ValueError("retention receipt id is required")
    restored_receipt = _receipt(restored_connection, receipt_id)
    if not restored_receipt or restored_receipt[0] != "planned":
        raise ValueError("backup does not contain the exact pre-apply retention plan")
    restored_plan = _validate_plan(restored_receipt)

    with live_connection.transaction():
        live_connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        live_connection.execute("SELECT pg_advisory_xact_lock(%s)", (RETENTION_LOCK_ID,))
        live_receipt = _receipt(live_connection, receipt_id, lock=True)
        if not live_receipt or live_receipt[0] not in {"applied", "partially_applied"}:
            raise ValueError("retention receipt is not in the applied lifecycle state")
        live_plan = _validate_plan(live_receipt)
        if live_receipt[2] != expected_backup_manifest_sha256:
            raise ValueError("retention receipt does not name the supplied backup manifest")
        if (
            live_receipt[1] != restored_receipt[1]
            or live_receipt[3] != restored_receipt[3]
            or live_receipt[4] != restored_receipt[4]
            or _canonical_json(live_plan) != _canonical_json(restored_plan)
        ):
            raise ValueError("live retention plan does not match the restored pre-apply plan")

        planned_counts = _planned_rule_counts(restored_plan)
        aggregate_receipts = _automation_aggregate_receipts(live_connection, receipt_id)
        aggregate_ids = {
            identity
            for receipt in aggregate_receipts.values()
            for identity in receipt["source_row_ids"]
        }
        automation_plan_rule = next(
            (
                item for item in restored_plan.get("rules") or []
                if isinstance(item, dict) and item.get("rule") == "automation_non_action_detail"
            ),
            {},
        )
        expected_automation_rows = (
            planned_counts.get("automation_non_action_detail", 0)
            if automation_plan_rule.get("migration_gate_enabled") is True
            and automation_plan_rule.get("mutation_status") != "blocked"
            else 0
        )
        if len(aggregate_ids) != expected_automation_rows:
            raise ValueError("aggregate receipt source IDs do not match the exact retention plan")

        row_receipts = _row_receipts(live_connection, receipt_id)
        proof_by_receipt = {
            str(item["receipt_sha256"]): item
            for item in (restored_plan.get("verified_local_migration_proofs") or [])
        }
        receipt_counts: dict[str, int] = {}
        for receipt in row_receipts:
            receipt_counts[receipt["rule_name"]] = receipt_counts.get(receipt["rule_name"], 0) + 1
        for rule_name, planned_count in planned_counts.items():
            if rule_name == "automation_non_action_detail":
                continue
            planned_rule = next(
                (item for item in restored_plan.get("rules") or [] if item.get("rule") == rule_name),
                {},
            )
            expected_applied = planned_count if planned_rule.get("migration_gate_enabled") is True else 0
            if receipt_counts.get(rule_name, 0) != expected_applied:
                raise ValueError(f"row receipts do not match the exact {rule_name} plan")

        source_records: list[dict[str, Any]] = []
        restored_automation_proofs: list[dict[str, str]] = []
        restored_automation = _automation_snapshots(restored_connection, sorted(aggregate_ids))
        if set(restored_automation) != aggregate_ids:
            missing = sorted(aggregate_ids - set(restored_automation))
            raise ValueError(f"restored backup is missing exact automation row {missing[0]}")
        _validate_automation_aggregate_sources(aggregate_receipts, restored_automation)
        for identity in sorted(aggregate_ids):
            source = restored_automation[identity]
            restored_automation_proofs.append(
                {
                    "row_identity": identity,
                    "source_row_sha256": _migration_source_sha256("automation_runs", source),
                }
            )
            source_records.append(
                {
                    "rule_name": "automation_non_action_detail",
                    "table_name": "automation_runs",
                    "row_identity": identity,
                    "source_row_sha256": _sha256(source),
                    "target_row_sha256": None,
                }
            )
        if expected_automation_rows:
            proof_manifest = dict(restored_plan["verified_local_automation_proof_manifest"])
            if proof_manifest.get("rows") != len(restored_automation_proofs) or proof_manifest.get(
                "manifest_sha256"
            ) != _sha256(restored_automation_proofs):
                raise ValueError("restored automation rows do not match the local-ledger proof manifest")
        for receipt in row_receipts:
            source = _row_snapshot(
                restored_connection,
                table_name=receipt["table_name"],
                identity=receipt["row_identity"],
            )
            if source is None or _sha256(source) != receipt["source_row_sha256"]:
                raise ValueError(
                    f"restored backup source hash does not match {receipt['rule_name']} row {receipt['row_identity']}"
                )
            if (
                _schema_sha256(restored_connection, receipt["table_name"]) != receipt["source_schema_sha256"]
                or _schema_sha256(live_connection, receipt["table_name"]) != receipt["source_schema_sha256"]
            ):
                raise ValueError("retention row receipt schema digest no longer matches live and restored schemas")
            proof = proof_by_receipt.get(receipt["local_migration_receipt_sha256"])
            if not proof or (
                proof.get("source_table") != receipt["table_name"]
                or proof.get("rule_name") != receipt["rule_name"]
                or proof.get("row_identity") != receipt["row_identity"]
                or proof.get("source_row_sha256")
                != _migration_source_sha256(receipt["table_name"], source)
            ):
                raise ValueError("retention row receipt lost its exact local migration proof binding")
            source_records.append(receipt)

        _lock_restore_targets(live_connection, source_records)
        live_automation = _automation_snapshots(live_connection, sorted(aggregate_ids))
        conflicts: list[str] = []
        already_present = 0
        rows_to_restore = 0
        for record in source_records:
            if record["table_name"] == "automation_runs":
                live = live_automation.get(record["row_identity"])
                restored = restored_automation.get(record["row_identity"])
            else:
                live = _row_snapshot(
                    live_connection,
                    table_name=record["table_name"],
                    identity=record["row_identity"],
                )
                restored = _row_snapshot(
                    restored_connection,
                    table_name=record["table_name"],
                    identity=record["row_identity"],
                )
            if live is not None and _sha256(live) == _sha256(restored):
                already_present += 1
                record["_already_source"] = True
                continue
            target_sha = record.get("target_row_sha256")
            if target_sha is None:
                if live is not None:
                    conflicts.append(f"{record['table_name']}:{record['row_identity']}")
                    continue
            elif live is None or _sha256(live) != target_sha:
                conflicts.append(f"{record['table_name']}:{record['row_identity']}")
                continue
            record["_expected_target"] = live
            rows_to_restore += 1

        if conflicts:
            raise ValueError(f"rollback refused concurrently changed rows: {', '.join(conflicts[:10])}")

        if apply:
            automation_to_restore = [
                record["row_identity"]
                for record in source_records
                if record["table_name"] == "automation_runs"
                and record.get("_already_source") is not True
            ]
            _restore_automation_rows(
                live_connection,
                restored_connection,
                identities=automation_to_restore,
            )
            for record in source_records:
                if record.get("_already_source") is True or record["table_name"] == "automation_runs":
                    continue
                _restore_row(
                    live_connection,
                    restored_connection,
                    table_name=record["table_name"],
                    identity=record["row_identity"],
                    expected_target=record.get("_expected_target"),
                )
            deleted_aggregates = live_connection.execute(
                "DELETE FROM automation_run_daily_receipts WHERE retention_receipt_id=%s",
                (receipt_id,),
            ).rowcount
            if int(deleted_aggregates or 0) != len(aggregate_receipts):
                raise RuntimeError("automation aggregate rollback affected-row mismatch")
            updated = live_connection.execute(
                """UPDATE railway_retention_receipts SET lifecycle_status='rolled_back',rolled_back_at=NOW()
                WHERE receipt_id=%s AND lifecycle_status IN ('applied','partially_applied')""",
                (receipt_id,),
            ).rowcount
            if updated != 1:
                raise RuntimeError("retention rollback lifecycle update failed")
            live_connection.execute(
                """UPDATE railway_retention_rule_receipts
                SET lifecycle_status='rolled_back',updated_at=NOW()
                WHERE retention_receipt_id=%s AND lifecycle_status IN ('applied','partially_applied')""",
                (receipt_id,),
            )
        else:
            deleted_aggregates = 0

    per_rule: dict[str, int] = {}
    for record in source_records:
        per_rule[record["rule_name"]] = per_rule.get(record["rule_name"], 0) + 1
    return {
        "schema_version": "railway_retention_rollback_receipt/v2",
        "mode": "apply" if apply else "dry_run",
        "retention_receipt_id": receipt_id,
        "backup_manifest_sha256": expected_backup_manifest_sha256,
        "candidate_rows": len(source_records),
        "already_present_rows": already_present,
        "rows_to_restore": rows_to_restore,
        "restored_rows": rows_to_restore if apply else 0,
        "removed_aggregate_rows": int(deleted_aggregates or 0),
        "validated_aggregate_rows": len(aggregate_receipts),
        "retained_row_mutation_receipts": len(row_receipts),
        "restored_rows_by_rule": per_rule if apply else {},
        "conflicts": [],
        "whole_database_restore": False,
    }
