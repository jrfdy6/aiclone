from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


CLOCK_AUTHORITY = "ai_clone_utc"
CLOCK_SCHEMA_VERSION = "ai_clone_clock/v1"
_CYCLE_OBSERVATION_RE = re.compile(
    r"@(?P<stamp>\d{8}T\d{6}(?:\d{1,6})?Z)$"
)
_DAILY_CYCLE_DATE_RE = re.compile(
    r"^daily-(?P<date>\d{4}-\d{2}-\d{2})(?:@|$)"
)


def utc_now() -> datetime:
    """Return the AI Clone system clock in timezone-aware UTC."""

    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize an explicitly zoned timestamp onto the AI Clone UTC clock.

    A naive datetime does not say which instant it represents.  Assigning UTC
    to it would invent clock meaning, so every caller must provide an explicit
    timezone before this shared authority will accept it.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset.")
    return value.astimezone(timezone.utc)


def parse_utc(value: Any, *, field_name: str = "timestamp") -> datetime:
    """Parse a required ISO-8601 timestamp and normalize it to UTC."""

    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset.")
    return parsed.astimezone(timezone.utc)


def utc_iso(value: datetime, *, seconds: bool = True) -> str:
    """Render a timestamp in the canonical machine-readable UTC form."""

    normalized = as_utc(value)
    if seconds:
        normalized = normalized.replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def same_utc_observation_second(left: datetime, right: datetime) -> bool:
    """Compare two ai_clone_utc observations at the receipt precision.

    Cycle identities may retain the sampled microseconds while persisted
    semantic receipts intentionally render whole seconds.  That is one clock
    with two representations, so agreement is defined on the represented
    second and never by assigning a timezone or consulting another clock.
    """

    return as_utc(left).replace(microsecond=0) == as_utc(right).replace(
        microsecond=0
    )


def clock_receipt(observed_at: datetime) -> dict[str, str]:
    """Describe the single clock reference used for a bounded evaluation cycle."""

    return {
        "schema_version": CLOCK_SCHEMA_VERSION,
        "authority": CLOCK_AUTHORITY,
        "timezone": "UTC",
        "observed_at": utc_iso(observed_at),
    }


def _cycle_observation(cycle_id: str) -> datetime | None:
    match = _CYCLE_OBSERVATION_RE.search(cycle_id)
    if not match:
        return None
    stamp = match.group("stamp")
    try:
        return datetime.strptime(
            stamp,
            "%Y%m%dT%H%M%S%fZ" if len(stamp) > 16 else "%Y%m%dT%H%M%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("cycle_id contains an invalid UTC observation.") from exc


def validate_cycle_observation(cycle_id: Any, observed_at: datetime) -> datetime:
    """Bind a cycle identity to one explicit ``ai_clone_utc`` observation.

    Daily cycle names carry a UTC calendar date.  Canonical cycle identities
    may additionally retain the sampled microseconds after ``@`` while the
    durable clock receipt is intentionally second precision.  Both forms must
    identify the supplied observation; arbitrary non-daily bounded identities
    remain valid because their syntax is governed by their owning subsystem.
    """

    normalized = as_utc(observed_at)
    normalized_cycle_id = str(cycle_id or "").strip()
    if not normalized_cycle_id:
        raise ValueError("cycle_id is required for a clocked cycle observation.")

    daily_match = _DAILY_CYCLE_DATE_RE.match(normalized_cycle_id)
    if daily_match:
        try:
            cycle_date = datetime.strptime(
                daily_match.group("date"), "%Y-%m-%d"
            ).date()
        except ValueError as exc:
            raise ValueError("cycle_id contains an invalid daily UTC date.") from exc
        if cycle_date != normalized.date():
            raise ValueError(
                "daily cycle_id date does not match its ai_clone_utc observation."
            )

    embedded_observation = _cycle_observation(normalized_cycle_id)
    if embedded_observation is not None and not same_utc_observation_second(
        embedded_observation,
        normalized,
    ):
        raise ValueError(
            "cycle_id observation does not match its ai_clone_utc receipt."
        )
    return normalized


def validate_clocked_cycle_observation(
    payload: Mapping[str, Any] | object,
    *,
    cycle_id: Any = None,
) -> datetime:
    """Require one complete, internally consistent canonical clock receipt.

    Rich local prep stores the receipt at the document root; remote standup
    promotion stores it in ``recursion``.  When both are present they must name
    the same represented UTC second.  Persistence or browser timestamps are
    deliberately excluded from this authority check.
    """

    body = dict(payload) if isinstance(payload, Mapping) else {}
    recursion = (
        dict(body.get("recursion"))
        if isinstance(body.get("recursion"), Mapping)
        else {}
    )
    payload_cycle_candidates = [
        str(value or "").strip()
        for value in (body.get("cycle_id"), recursion.get("cycle_id"))
        if str(value or "").strip()
    ]
    if not payload_cycle_candidates:
        raise ValueError("cycle_id is required for a clocked cycle observation.")
    cycle_candidates = [
        *(
            [str(cycle_id).strip()]
            if str(cycle_id or "").strip()
            else []
        ),
        *payload_cycle_candidates,
    ]
    if len(set(cycle_candidates)) != 1:
        raise ValueError("cycle_id conflicts with the clocked cycle payload.")
    canonical_cycle_id = cycle_candidates[0]

    observations: list[datetime] = []
    for label, container in (("payload", body), ("recursion", recursion)):
        raw_observed_at = container.get("observed_at")
        raw_clock = container.get("clock")
        has_observed_at = bool(str(raw_observed_at or "").strip())
        has_clock = isinstance(raw_clock, Mapping) and bool(raw_clock)
        if not has_observed_at and not has_clock:
            continue
        if not has_observed_at or not has_clock:
            raise ValueError(
                f"{label} must contain both observed_at and its canonical clock receipt."
            )
        clock = dict(raw_clock)
        if str(clock.get("schema_version") or "").strip() != CLOCK_SCHEMA_VERSION:
            raise ValueError(f"{label}.clock schema_version is not canonical.")
        if str(clock.get("authority") or "").strip() != CLOCK_AUTHORITY:
            raise ValueError(f"{label}.clock authority must be ai_clone_utc.")
        if str(clock.get("timezone") or "").strip() != "UTC":
            raise ValueError(f"{label}.clock timezone must be UTC.")
        observed = parse_utc(
            raw_observed_at,
            field_name=f"{label}.observed_at",
        )
        clock_observed = parse_utc(
            clock.get("observed_at"),
            field_name=f"{label}.clock.observed_at",
        )
        if not same_utc_observation_second(observed, clock_observed):
            raise ValueError(
                f"{label}.observed_at conflicts with its ai_clone_utc receipt."
            )
        observations.append(observed)

    if not observations:
        raise ValueError(
            "A clocked cycle requires an explicit observed_at and canonical ai_clone_utc receipt."
        )
    represented_seconds = {
        value.replace(microsecond=0) for value in observations
    }
    if len(represented_seconds) != 1:
        raise ValueError("Clocked cycle observations conflict across payload lanes.")
    return validate_cycle_observation(canonical_cycle_id, observations[0])


def resolve_payload_observation(
    payload: Mapping[str, Any] | object,
    *,
    created_at: Any = None,
) -> tuple[datetime | None, str]:
    """Resolve artifact freshness from semantic observation time.

    ``created_at`` is a persistence timestamp and is intentionally only a
    degraded legacy fallback.  New coordination and meeting records carry the
    cycle observation in ``payload.observed_at`` or ``payload.recursion``; an
    explicit timestamp embedded in a canonical cycle id is also accepted.  All
    available semantic values must be timezone-aware and agree.
    """

    body = dict(payload) if isinstance(payload, Mapping) else {}
    recursion = (
        dict(body.get("recursion"))
        if isinstance(body.get("recursion"), Mapping)
        else {}
    )
    candidates: list[tuple[str, Any]] = []
    invalid_clock = False
    for prefix, container in (("payload", body), ("recursion", recursion)):
        observed = container.get("observed_at")
        if str(observed or "").strip():
            candidates.append((f"{prefix}.observed_at", observed))
        clock = container.get("clock")
        if isinstance(clock, Mapping):
            authority = str(
                clock.get("authority") or clock.get("clock") or ""
            ).strip()
            if authority and authority != CLOCK_AUTHORITY:
                invalid_clock = True
            clock_observed = clock.get("observed_at")
            if str(clock_observed or "").strip():
                candidates.append(
                    (f"{prefix}.clock.observed_at", clock_observed)
                )

    cycle_candidates: list[tuple[str, datetime]] = []
    for prefix, container in (("payload", body), ("recursion", recursion)):
        cycle_id = str(container.get("cycle_id") or "").strip()
        match = _CYCLE_OBSERVATION_RE.search(cycle_id)
        if not match:
            continue
        stamp = match.group("stamp")
        try:
            cycle_observed = datetime.strptime(
                stamp,
                "%Y%m%dT%H%M%S%fZ" if len(stamp) > 16 else "%Y%m%dT%H%M%SZ",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None, "invalid_semantic_cycle_observation"
        cycle_candidates.append((f"{prefix}.cycle_id", cycle_observed))

    if invalid_clock:
        return None, "invalid_semantic_clock_authority"

    parsed_candidates: list[tuple[str, datetime]] = []
    for source, value in candidates:
        try:
            parsed_candidates.append(
                (source, parse_utc(value, field_name=source))
            )
        except ValueError:
            return None, "invalid_semantic_observation"
    # The canonical cycle id retains microseconds while persisted observation
    # receipts are intentionally second-precision.  Both still identify the
    # same machine-clock observation and therefore must agree on the second.
    # The cycle identity is a fallback only when no explicit receipt exists.
    if parsed_candidates and cycle_candidates:
        explicit_seconds = {
            value.replace(microsecond=0) for _source, value in parsed_candidates
        }
        cycle_seconds = {
            value.replace(microsecond=0) for _source, value in cycle_candidates
        }
        if len(explicit_seconds) != 1 or cycle_seconds != explicit_seconds:
            return None, "conflicting_semantic_observation"
    elif not parsed_candidates:
        parsed_candidates.extend(cycle_candidates)
    if parsed_candidates:
        unique = {value for _source, value in parsed_candidates}
        if len(unique) != 1:
            return None, "conflicting_semantic_observation"
        source = (
            "semantic_observed_at"
            if candidates
            else "semantic_cycle_observation"
        )
        return parsed_candidates[0][1], source

    if str(created_at or "").strip():
        try:
            return (
                parse_utc(created_at, field_name="created_at"),
                "legacy_created_at_fallback",
            )
        except ValueError:
            return None, "invalid_legacy_created_at"
    return None, "missing_semantic_observation"
