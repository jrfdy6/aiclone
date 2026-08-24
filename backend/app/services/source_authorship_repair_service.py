from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json
from app.services.source_authorship_policy_service import (
    AUTHORSHIP_POLICY_VERSION,
    owner_authorship_attested,
)


SOURCE_AUTHORSHIP_REPAIR_SCHEMA = "source_authorship_rights_repair/v1"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _repair_connection(store: IntegratedSystemStore, *, apply: bool):
    if apply:
        with store.connection() as connection:
            yield connection
        return

    # `IntegratedSystemStore.connection()` enables WAL and creates the parent
    # directory, so it is deliberately not used for an audit. SQLite's URI
    # read-only mode makes the dry-run guarantee enforceable by the database.
    connection = sqlite3.connect(
        f"{store.database_path.as_uri()}?mode=ro",
        uri=True,
        timeout=10,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    try:
        yield connection
    finally:
        connection.close()


def repair_unattested_owner_rights(
    store: IntegratedSystemStore,
    *,
    apply: bool = False,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Audit or conservatively repair legacy owner-controlled source rows.

    The default is read-only. Apply mode changes only rows whose metadata lacks
    an explicit boolean owner-authorship attestation, records one compact event
    per source, and can be rerun without creating duplicate events.
    """

    # A dry run is intentionally read-only. Schema creation/migration belongs
    # only to the explicitly authorized apply path; an uninitialized audit
    # target should fail visibly instead of being changed during inspection.
    if apply:
        store.migrate()
    now = occurred_at or _utcnow()
    with _repair_connection(store, apply=apply) as connection:
        candidates = []
        for row in connection.execute(
            """SELECT source_id,rights_state,metadata_json,merged_into_source_id
            FROM sources WHERE rights_state='owner_controlled' ORDER BY source_id"""
        ):
            if owner_authorship_attested(row["metadata_json"]):
                continue
            candidates.append(
                {
                    "source_id": str(row["source_id"]),
                    "merged_alias": bool(row["merged_into_source_id"]),
                }
            )

        repaired = 0
        events_written = 0
        if apply and candidates:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for candidate in candidates:
                    row = connection.execute(
                        "SELECT * FROM sources WHERE source_id=?",
                        (candidate["source_id"],),
                    ).fetchone()
                    if (
                        not row
                        or row["rights_state"] != "owner_controlled"
                        or owner_authorship_attested(row["metadata_json"])
                    ):
                        continue
                    try:
                        metadata = json.loads(row["metadata_json"] or "{}")
                    except (TypeError, ValueError, json.JSONDecodeError):
                        metadata = {}
                    metadata = dict(metadata) if isinstance(metadata, dict) else {}
                    metadata.update(
                        {
                            "authorship_classification": "unattested_attribution_required",
                            "authorship_policy_version": AUTHORSHIP_POLICY_VERSION,
                            "owner_authorship_attested": False,
                            "rights_repair_version": SOURCE_AUTHORSHIP_REPAIR_SCHEMA,
                        }
                    )
                    connection.execute(
                        """UPDATE sources SET rights_state='permitted',metadata_json=?,updated_at=?
                        WHERE source_id=? AND rights_state='owner_controlled'""",
                        (_canonical_json(metadata), now, row["source_id"]),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0] != 1:
                        continue
                    repaired += 1
                    event_key = f"source-authorship-rights-repair:v1:{row['source_id']}"
                    before = connection.total_changes
                    connection.execute(
                        """INSERT INTO system_events(
                            event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                            payload_json,provenance_json,artifact_refs_json,idempotency_key
                        ) VALUES (?,?,?,?,?,'governed_repair',?,?,?,?)
                        ON CONFLICT(idempotency_key) DO NOTHING""",
                        (
                            str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}")),
                            "source.authorship_rights_repaired",
                            "source",
                            row["source_id"],
                            now,
                            _canonical_json(
                                {
                                    "schema_version": SOURCE_AUTHORSHIP_REPAIR_SCHEMA,
                                    "prior_rights_state": "owner_controlled",
                                    "new_rights_state": "permitted",
                                    "owner_authorship_attested": False,
                                }
                            ),
                            _canonical_json(
                                {
                                    "policy_version": AUTHORSHIP_POLICY_VERSION,
                                    "reason": "legacy_owner_authorship_unattested",
                                }
                            ),
                            "[]",
                            event_key,
                        ),
                    )
                    events_written += int(connection.total_changes > before)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    receipt = {
        "schema_version": SOURCE_AUTHORSHIP_REPAIR_SCHEMA,
        "mode": "apply" if apply else "dry_run",
        "applied": bool(apply),
        "candidate_count": len(candidates),
        "repaired_count": repaired,
        "events_written": events_written,
        "candidates": candidates,
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        _canonical_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt
