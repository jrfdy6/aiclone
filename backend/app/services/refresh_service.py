from __future__ import annotations

from datetime import datetime, timedelta
from app.services import capture_service
from app.services import open_brain_repository as repo
from app.utils.ai_clone_clock import as_utc, utc_now


def delete_expired_vectors() -> int:
    return repo.delete_expired_vectors()


def _canonical_expiry(capture: dict) -> tuple[bool, datetime | None, str | None]:
    """Resolve the exact pre-refresh vector expiry without renewing evidence.

    A missing vector row has no remaining expiry authority. Mixed null/non-null
    values or multiple expiry instants are internally inconsistent. Both cases
    are withheld before any vectors for that capture are deleted.
    """

    vector_count = capture.get("vector_count")
    expiring_vector_count = capture.get("expiring_vector_count")
    distinct_expiry_count = capture.get("distinct_expiry_count")
    if (
        isinstance(vector_count, bool)
        or not isinstance(vector_count, int)
        or isinstance(expiring_vector_count, bool)
        or not isinstance(expiring_vector_count, int)
        or isinstance(distinct_expiry_count, bool)
        or not isinstance(distinct_expiry_count, int)
        or vector_count < 1
    ):
        return False, None, "missing"

    raw_expires_at = capture.get("expires_at")
    if (
        expiring_vector_count == 0
        and distinct_expiry_count == 0
        and raw_expires_at is None
    ):
        return True, None, None
    if (
        expiring_vector_count != vector_count
        or distinct_expiry_count != 1
        or not isinstance(raw_expires_at, datetime)
    ):
        return False, None, "inconsistent"
    try:
        return True, as_utc(raw_expires_at), None
    except ValueError:
        return False, None, "inconsistent"


def refresh_recent_captures(
    hours: int = 24,
    limit: int = 50,
    *,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    observation = as_utc(observed_at) if observed_at is not None else utc_now()
    threshold = observation - timedelta(hours=hours)
    captures = repo.fetch_captures_updated_since(threshold, limit)

    refreshed = 0
    chunk_total = 0
    skipped_missing_expiry = 0
    skipped_inconsistent_expiry = 0

    for capture in captures:
        expiry_valid, canonical_expires_at, expiry_error = _canonical_expiry(capture)
        if not expiry_valid:
            if expiry_error == "inconsistent":
                skipped_inconsistent_expiry += 1
            else:
                skipped_missing_expiry += 1
            continue

        capture_id = capture["id"]
        repo.delete_vectors_for_capture(capture_id)
        records, _ = capture_service.build_chunk_records(
            capture_id=capture_id,
            text=capture["raw_text"],
            importance=capture["importance"],
            observed_at=observation,
            canonical_expires_at=canonical_expires_at,
            preserve_canonical_expiry=True,
        )
        repo.insert_vector_chunks(records)
        refreshed += 1
        chunk_total += len(records)

    return {
        "captures": refreshed,
        "chunks": chunk_total,
        "skipped_captures": (
            skipped_missing_expiry + skipped_inconsistent_expiry
        ),
        "skip_reason_counts": {
            "canonical_vector_expiry_missing": skipped_missing_expiry,
            "canonical_vector_expiry_inconsistent": (
                skipped_inconsistent_expiry
            ),
        },
    }
