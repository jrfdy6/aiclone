from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.utils.ai_clone_clock import (
    as_utc,
    clock_receipt,
    parse_utc,
    resolve_payload_observation,
    same_utc_observation_second,
    utc_iso,
    validate_clocked_cycle_observation,
    validate_cycle_observation,
)


def test_clock_normalizes_offsets_and_emits_one_utc_authority() -> None:
    eastern = timezone(timedelta(hours=-4))
    observed_at = datetime(2026, 8, 26, 11, 0, 12, 345000, tzinfo=eastern)

    normalized = as_utc(observed_at)
    receipt = clock_receipt(observed_at)

    assert normalized == datetime(2026, 8, 26, 15, 0, 12, 345000, tzinfo=timezone.utc)
    assert utc_iso(observed_at) == "2026-08-26T15:00:12Z"
    assert receipt == {
        "schema_version": "ai_clone_clock/v1",
        "authority": "ai_clone_utc",
        "timezone": "UTC",
        "observed_at": "2026-08-26T15:00:12Z",
    }


def test_clock_rejects_unzoned_machine_time() -> None:
    with pytest.raises(ValueError, match="timezone offset"):
        parse_utc("2026-08-26T15:00:00", field_name="observed_at")

    naive = datetime(2026, 8, 26, 15, 0, 0)
    with pytest.raises(ValueError, match="timezone offset"):
        as_utc(naive)
    with pytest.raises(ValueError, match="timezone offset"):
        utc_iso(naive)
    with pytest.raises(ValueError, match="timezone offset"):
        clock_receipt(naive)


def test_explicit_observation_and_cycle_identity_must_name_the_same_second() -> None:
    compatible, compatible_source = resolve_payload_observation(
        {
            "cycle_id": "daily-cycle@20260826T150012345678Z",
            "observed_at": "2026-08-26T15:00:12Z",
            "clock": {
                "authority": "ai_clone_utc",
                "observed_at": "2026-08-26T15:00:12Z",
            },
        },
        created_at=None,
    )
    assert compatible == datetime(2026, 8, 26, 15, 0, 12, tzinfo=timezone.utc)
    assert compatible_source == "semantic_observed_at"

    conflicting, conflict_source = resolve_payload_observation(
        {
            "cycle_id": "daily-cycle@20260826T150012345678Z",
            "observed_at": "2026-01-01T00:00:00Z",
            "clock": {
                "authority": "ai_clone_utc",
                "observed_at": "2026-01-01T00:00:00Z",
            },
        },
        created_at=None,
    )
    assert conflicting is None
    assert conflict_source == "conflicting_semantic_observation"


def test_clock_receipt_precision_compares_the_same_utc_second_only() -> None:
    sampled = datetime(
        2026, 8, 26, 15, 0, 12, 482752, tzinfo=timezone.utc
    )
    persisted_receipt = datetime(
        2026, 8, 26, 15, 0, 12, tzinfo=timezone.utc
    )
    next_second = datetime(
        2026, 8, 26, 15, 0, 13, tzinfo=timezone.utc
    )

    assert same_utc_observation_second(sampled, persisted_receipt) is True
    assert same_utc_observation_second(sampled, next_second) is False
    with pytest.raises(ValueError, match="timezone offset"):
        same_utc_observation_second(
            sampled,
            datetime(2026, 8, 26, 15, 0, 12),
        )


def test_daily_cycle_date_and_embedded_observation_share_one_utc_instant() -> None:
    observed = datetime(2026, 8, 26, 23, 59, 59, tzinfo=timezone.utc)

    assert validate_cycle_observation("daily-2026-08-26", observed) == observed
    assert (
        validate_cycle_observation(
            "daily-2026-08-26@20260826T235959482752Z",
            observed,
        )
        == observed
    )

    with pytest.raises(ValueError, match="daily cycle_id date"):
        validate_cycle_observation(
            "daily-2026-08-25",
            observed,
        )
    with pytest.raises(ValueError, match="cycle_id observation"):
        validate_cycle_observation(
            "daily-2026-08-26@20260826T235958482752Z",
            observed,
        )


def test_clocked_cycle_requires_complete_canonical_receipt() -> None:
    cycle_id = "daily-2026-08-26@20260826T150012345678Z"
    payload = {
        "cycle_id": cycle_id,
        "observed_at": "2026-08-26T15:00:12Z",
        "clock": {
            "schema_version": "ai_clone_clock/v1",
            "authority": "ai_clone_utc",
            "timezone": "UTC",
            "observed_at": "2026-08-26T15:00:12Z",
        },
    }

    assert validate_clocked_cycle_observation(payload) == datetime(
        2026, 8, 26, 15, 0, 12, tzinfo=timezone.utc
    )

    for invalid in (
        {**payload, "clock": {}},
        {
            **payload,
            "clock": {**payload["clock"], "authority": "browser_time"},
        },
        {
            **payload,
            "clock": {**payload["clock"], "timezone": "America/New_York"},
        },
        {
            **payload,
            "clock": {
                **payload["clock"],
                "observed_at": "2026-08-26T15:00:13Z",
            },
        },
    ):
        with pytest.raises(ValueError):
            validate_clocked_cycle_observation(invalid)


def test_root_and_recursion_clock_receipts_must_agree() -> None:
    payload = {
        "cycle_id": "daily-2026-08-26",
        "observed_at": "2026-08-26T23:59:59Z",
        "clock": clock_receipt(
            datetime(2026, 8, 26, 23, 59, 59, tzinfo=timezone.utc)
        ),
        "recursion": {
            "cycle_id": "daily-2026-08-26",
            "observed_at": "2026-08-27T00:00:00Z",
            "clock": clock_receipt(
                datetime(2026, 8, 27, 0, 0, 0, tzinfo=timezone.utc)
            ),
        },
    }

    with pytest.raises(ValueError, match="conflict"):
        validate_clocked_cycle_observation(payload)
