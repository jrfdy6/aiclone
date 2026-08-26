from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CLOCK_AUTHORITY = "ai_clone_utc"
CLOCK_SCHEMA_VERSION = "ai_clone_clock/v1"


def utc_now() -> datetime:
    """Return the AI Clone system clock in timezone-aware UTC."""

    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Normalize one timestamp onto the AI Clone UTC clock."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
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


def clock_receipt(observed_at: datetime) -> dict[str, str]:
    """Describe the single clock reference used for a bounded evaluation cycle."""

    return {
        "schema_version": CLOCK_SCHEMA_VERSION,
        "authority": CLOCK_AUTHORITY,
        "timezone": "UTC",
        "observed_at": utc_iso(observed_at),
    }
