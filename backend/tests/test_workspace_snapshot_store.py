from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import workspace_snapshot_store


def _snapshot_row(payload: dict) -> dict:
    return {
        "id": "snapshot-1",
        "workspace_key": "shared_ops",
        "snapshot_type": "ops_standup",
        "payload": payload,
        "metadata": {},
        "created_at": datetime(2026, 8, 20, 7, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 8, 20, 7, tzinfo=timezone.utc),
    }


def _pool_cursor() -> tuple[MagicMock, MagicMock, MagicMock]:
    pool = MagicMock()
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    return pool, connection, cursor


def test_monotonic_snapshot_uses_semantic_observation_sql_and_value() -> None:
    pool, connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    generated_at = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": generated_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "state": "ready",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            incoming,
            generated_at=generated_at,
            semantic_observed_at=observed_at,
            semantic_order_required=True,
        )

    query, params = cursor.execute.call_args.args
    assert "workspace_snapshots.payload->>'observed_at'" in query
    assert (
        "jsonb_typeof(workspace_snapshots.payload->'observed_at') = 'string'"
        in query
    )
    assert "(\\.[0-9]{1,6})?Z$" in query
    assert "ELSE NULL::timestamptz" in query
    assert "-infinity" not in query
    assert params[-2] is True
    assert params[-1] == observed_at
    assert stored is True
    assert snapshot is not None
    connection.commit.assert_called_once()


def test_monotonic_snapshot_rejects_naive_receipt_times_before_storage() -> None:
    pool, _connection, cursor = _pool_cursor()
    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        with pytest.raises(ValueError, match="timezone offset"):
            workspace_snapshot_store.upsert_snapshot_monotonic(
                "shared_ops",
                "ops_standup",
                {"generated_at": "2026-08-21T12:00:00", "state": "ready"},
                generated_at=datetime(2026, 8, 21, 12, 0),
            )

    cursor.execute.assert_not_called()


def test_generated_at_ordering_retains_exact_utc_offset_compatibility() -> None:
    pool, connection, cursor = _pool_cursor()
    generated_at = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": generated_at.isoformat(),
        "state": "ready",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "generic_projection",
            incoming,
            generated_at=generated_at,
        )

    query, _params = cursor.execute.call_args.args
    assert "workspace_snapshots.payload->>'generated_at'" in query
    assert "(Z|[+]00:00)$" in query
    assert stored is True
    assert snapshot is not None
    connection.commit.assert_called_once()


def test_monotonic_snapshot_orders_equal_observation_by_next_canonical_revision() -> None:
    pool, connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    generated_at = datetime(2026, 8, 20, 6, 17, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": generated_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "ops_conclusion_attempt_number": 2,
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
        "state": "ready",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            incoming,
            generated_at=generated_at,
            semantic_observed_at=observed_at,
            semantic_order_required=True,
            semantic_revision=2,
            semantic_revision_field="ops_conclusion_attempt_number",
            semantic_revision_required=True,
            semantic_revision_strict_increment=True,
            semantic_identity_fields=(
                "ops_conclusion_id",
                "portfolio_cycle_id",
            ),
        )

    query, params = cursor.execute.call_args.args
    assert "workspace_snapshots.payload->>'observed_at'" in query
    assert "workspace_snapshots.payload->>'ops_conclusion_attempt_number'" in query
    assert "workspace_snapshots.payload->>'ops_conclusion_id' = %s" in query
    assert "workspace_snapshots.payload->>'portfolio_cycle_id' = %s" in query
    assert (
        "jsonb_typeof(workspace_snapshots.payload->'ops_conclusion_id') = 'string'"
        in query
    )
    assert (
        "jsonb_typeof(workspace_snapshots.payload->'portfolio_cycle_id') = 'string'"
        in query
    )
    assert (
        "jsonb_typeof(workspace_snapshots.payload->'schema_version') = 'string'"
        in query
    )
    assert "workspace_snapshots.payload->>'schema_version' = %s" in query
    assert "+ 1 = %s" in query
    assert params[-7] is True
    assert params[-6:-4] == (observed_at, observed_at)
    assert params[-4] == "ops_projection/v3"
    assert params[-3:-1] == ("ops-1", "cycle-1")
    assert params[-1] == 2
    assert stored is True
    assert snapshot is not None
    connection.commit.assert_called_once()


def test_semantic_revision_requires_exact_incoming_schema_before_storage() -> None:
    pool, _connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        with pytest.raises(ValueError, match="exact payload schema"):
            workspace_snapshot_store.upsert_snapshot_monotonic(
                "shared_ops",
                "ops_standup",
                {
                    "observed_at": "2026-08-20T06:15:00Z",
                    "ops_conclusion_attempt_number": 2,
                    "ops_conclusion_id": "ops-1",
                    "portfolio_cycle_id": "cycle-1",
                },
                generated_at=observed_at,
                semantic_observed_at=observed_at,
                semantic_revision=2,
                semantic_revision_field="ops_conclusion_attempt_number",
                semantic_identity_fields=(
                    "ops_conclusion_id",
                    "portfolio_cycle_id",
                ),
            )

    cursor.execute.assert_not_called()


def test_noncanonical_existing_semantic_observation_cannot_use_newer_branch() -> None:
    pool, connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    generated_at = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": generated_at.isoformat(),
        "observed_at": "2026-08-20T06:15:00Z",
        "ops_conclusion_attempt_number": 2,
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            incoming,
            generated_at=generated_at,
            semantic_observed_at=observed_at,
            semantic_revision=2,
            semantic_revision_field="ops_conclusion_attempt_number",
            semantic_identity_fields=(
                "ops_conclusion_id",
                "portfolio_cycle_id",
            ),
        )

    query, _params = cursor.execute.call_args.args
    canonical_validity = (
        "COALESCE(workspace_snapshots.payload->>'observed_at', '') ~ "
        "'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        "(\\.[0-9]{1,6})?Z$'"
    )
    assert f"{canonical_validity} AND" in query
    assert "+00:00" not in query.split("ON CONFLICT", 1)[1]
    assert "-infinity" not in query
    assert stored is True
    assert snapshot is not None
    connection.commit.assert_called_once()


def test_monotonic_snapshot_migrates_only_closed_legacy_shape_to_named_revision() -> None:
    pool, connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    generated_at = datetime(2026, 8, 20, 6, 17, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": generated_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "ops_conclusion_attempt_number": 2,
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
        "state": "ready",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)
    schemas = {
        "ops_projection/v1": (
            "schema_version",
            "observed_at",
            "ops_conclusion_id",
            "portfolio_cycle_id",
            "data_policy",
        ),
        "ops_projection/v2": (
            "schema_version",
            "observed_at",
            "ops_conclusion_id",
            "portfolio_cycle_id",
            "workspace_recursion",
            "data_policy",
        ),
    }
    expected_legacy = {
        "schema_version": "ops_projection/v1",
        "observed_at": "2026-08-20T06:15:00+00:00",
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
        "data_policy": {"canonical_authority": "mac_local_sql"},
    }

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            incoming,
            generated_at=generated_at,
            semantic_observed_at=observed_at,
            semantic_order_required=True,
            semantic_revision=2,
            semantic_revision_field="ops_conclusion_attempt_number",
            semantic_revision_required=True,
            semantic_revision_strict_increment=True,
            semantic_identity_fields=(
                "ops_conclusion_id",
                "portfolio_cycle_id",
            ),
            semantic_legacy_migration_revision=2,
            semantic_legacy_migration_schemas=schemas,
            semantic_legacy_migration_required_values={
                "data_policy": {"canonical_authority": "mac_local_sql"},
            },
            semantic_legacy_migration_max_bytes=256 * 1024,
            semantic_legacy_migration_expected_payload=expected_legacy,
        )

    query, params = cursor.execute.call_args.args
    assert "jsonb_object_keys(workspace_snapshots.payload)" in query
    assert 'ORDER BY legacy_key COLLATE "C"' in query
    assert "octet_length(workspace_snapshots.payload::text) <= %s" in query
    assert "workspace_snapshots.payload = %s" in query
    assert "workspace_snapshots.payload->>'schema_version' = %s" in query
    assert "workspace_snapshots.payload->'data_policy' = %s" in query
    assert "workspace_snapshots.payload->>'ops_conclusion_id' = %s" in query
    assert "workspace_snapshots.payload->>'portfolio_cycle_id' = %s" in query
    assert "~ '^[1-9][0-9]{0,8}$'" in query
    assert "ops_projection/v1" in params
    assert "ops_projection/v2" in params
    assert 256 * 1024 in params
    assert any(
        getattr(param, "obj", None) == expected_legacy
        for param in params
    )
    assert params[-1].obj == {"canonical_authority": "mac_local_sql"}
    assert stored is True
    assert snapshot is not None
    connection.commit.assert_called_once()


@pytest.mark.parametrize("attempt_number", [1, 3])
def test_monotonic_snapshot_never_treats_legacy_revision_as_zero_or_skippable(
    attempt_number: int,
) -> None:
    pool, connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    generated_at = datetime(2026, 8, 20, 6, 17, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": generated_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "ops_conclusion_attempt_number": attempt_number,
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
        "state": "ready",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            incoming,
            generated_at=generated_at,
            semantic_observed_at=observed_at,
            semantic_order_required=True,
            semantic_revision=attempt_number,
            semantic_revision_field="ops_conclusion_attempt_number",
            semantic_revision_required=True,
            semantic_revision_strict_increment=True,
            semantic_identity_fields=(
                "ops_conclusion_id",
                "portfolio_cycle_id",
            ),
            semantic_legacy_migration_revision=2,
            semantic_legacy_migration_schemas={
                "ops_projection/v1": (
                    "schema_version",
                    "observed_at",
                ),
            },
            semantic_legacy_migration_required_values={},
            semantic_legacy_migration_max_bytes=256 * 1024,
            semantic_legacy_migration_expected_payload={
                "schema_version": "ops_projection/v1",
                "observed_at": "2026-08-20T06:15:00+00:00",
            },
        )

    query, _params = cursor.execute.call_args.args
    assert "~ '^[1-9][0-9]{0,8}$'" in query
    assert "jsonb_object_keys(workspace_snapshots.payload)" not in query
    connection.commit.assert_called_once()


def test_monotonic_snapshot_rejects_partial_legacy_migration_contract() -> None:
    pool, _connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        with pytest.raises(ValueError, match="complete contract"):
            workspace_snapshot_store.upsert_snapshot_monotonic(
                "shared_ops",
                "ops_standup",
                {
                    "observed_at": observed_at.isoformat(),
                    "ops_conclusion_attempt_number": 2,
                    "ops_conclusion_id": "ops-1",
                    "portfolio_cycle_id": "cycle-1",
                },
                generated_at=observed_at,
                semantic_observed_at=observed_at,
                semantic_revision=2,
                semantic_revision_field="ops_conclusion_attempt_number",
                semantic_revision_strict_increment=True,
                semantic_identity_fields=(
                    "ops_conclusion_id",
                    "portfolio_cycle_id",
                ),
                semantic_legacy_migration_revision=2,
            )

    cursor.execute.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ops_conclusion_id", " ops-1"),
        ("portfolio_cycle_id", "cycle-1 "),
        ("ops_conclusion_id", ""),
    ],
)
def test_monotonic_snapshot_rejects_non_exact_semantic_identity_before_storage(
    field: str,
    value: str,
) -> None:
    pool, _connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "observed_at": observed_at.isoformat(),
        "ops_conclusion_attempt_number": 2,
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
    }
    incoming[field] = value

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        with pytest.raises(ValueError, match="identity values"):
            workspace_snapshot_store.upsert_snapshot_monotonic(
                "shared_ops",
                "ops_standup",
                incoming,
                generated_at=observed_at,
                semantic_observed_at=observed_at,
                semantic_revision=2,
                semantic_revision_field="ops_conclusion_attempt_number",
                semantic_identity_fields=(
                    "ops_conclusion_id",
                    "portfolio_cycle_id",
                ),
            )

    cursor.execute.assert_not_called()


def test_non_strict_revision_still_requires_valid_existing_revision() -> None:
    pool, connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)
    incoming = {
        "schema_version": "ops_projection/v3",
        "generated_at": observed_at.isoformat(),
        "observed_at": observed_at.isoformat(),
        "ops_conclusion_attempt_number": 2,
        "ops_conclusion_id": "ops-1",
        "portfolio_cycle_id": "cycle-1",
    }
    cursor.fetchone.return_value = _snapshot_row(incoming)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            incoming,
            generated_at=observed_at,
            semantic_observed_at=observed_at,
            semantic_revision=2,
            semantic_revision_field="ops_conclusion_attempt_number",
            semantic_identity_fields=(
                "ops_conclusion_id",
                "portfolio_cycle_id",
            ),
        )

    query, _params = cursor.execute.call_args.args
    assert "~ '^[1-9][0-9]{0,8}$' AND" in query
    assert "< %s" in query
    assert stored is True
    assert snapshot is not None
    connection.commit.assert_called_once()


def test_monotonic_snapshot_requires_revision_before_storage_when_governed() -> None:
    pool, _connection, cursor = _pool_cursor()
    observed_at = datetime(2026, 8, 20, 6, 15, tzinfo=timezone.utc)

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        with pytest.raises(ValueError, match="semantic revision is required"):
            workspace_snapshot_store.upsert_snapshot_monotonic(
                "shared_ops",
                "ops_standup",
                {"observed_at": observed_at.isoformat(), "state": "ready"},
                generated_at=observed_at,
                semantic_observed_at=observed_at,
                semantic_order_required=True,
                semantic_revision_required=True,
            )

    cursor.execute.assert_not_called()


def test_observationless_projection_cannot_overwrite_semantic_snapshot() -> None:
    pool, connection, cursor = _pool_cursor()
    current_payload = {
        "generated_at": "2026-08-20T08:00:00Z",
        "observed_at": "2026-08-20T07:15:00Z",
        "state": "ready",
    }
    current = _snapshot_row(current_payload)
    cursor.fetchone.side_effect = [None, current]
    later_projection_receipt = datetime(
        2026, 8, 21, 12, 0, tzinfo=timezone.utc
    )
    observationless_degraded = {
        "generated_at": later_projection_receipt.isoformat(),
        "observed_at": None,
        "clock": None,
        "state": "degraded",
        "reason_codes": ["ops_conclusion_clock_unverified"],
    }

    with patch.object(workspace_snapshot_store, "_maybe_pool", return_value=pool):
        snapshot, stored = workspace_snapshot_store.upsert_snapshot_monotonic(
            "shared_ops",
            "ops_standup",
            observationless_degraded,
            generated_at=later_projection_receipt,
            semantic_observed_at=None,
            semantic_order_required=True,
        )

    insert_query, insert_params = cursor.execute.call_args_list[0].args
    assert "workspace_snapshots.payload->>'observed_at'" in insert_query
    assert insert_params[-2] is False
    assert insert_params[-1] is None
    assert stored is False
    assert snapshot is not None
    assert snapshot["payload"] == current_payload
    connection.commit.assert_called_once()
