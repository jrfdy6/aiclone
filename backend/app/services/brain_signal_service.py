from __future__ import annotations

import errno
import fcntl
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import (
    BrainSignal,
    BrainSignalCreateRequest,
    BrainSignalReviewRequest,
    BrainSignalRouteRequest,
    PMCardCreate,
    PersonaDeltaCreate,
    StandupCreate,
)
from app.services import persona_delta_service, pm_card_service, standup_service
from app.services.brain_system_route_service import validate_brain_pm_route
from app.services.pm_execution_contract_service import build_execution_contract
from app.services.workspace_snapshot_store import get_snapshot_payload, list_snapshot_payloads
from app.services.workspace_runtime_contract_service import (
    canonical_standup_kind_for_workspace,
    standup_participants_for,
    standup_relevance_required_for,
)
from app.services.workspace_registry_service import REPO_ROOT, canonicalize_workspace_key
from app.utils.ai_clone_clock import as_utc, clock_receipt, utc_iso


ROOT = REPO_ROOT
_SCRIPTS_ROOT = ROOT / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from runtime_paths import (  # noqa: E402
    STATE_ROOT as RUNTIME_STATE_ROOT,
    memory_state_path,
    resolve_memory_read_path,
    seed_memory_state_file,
)


STATE_ROOT = RUNTIME_STATE_ROOT
# Tests and one-off maintenance tools may still provide an explicit path. The
# production default is resolved lazily so AI_CLONE_STATE_ROOT owns generated
# signal state and the project copy remains a read-only legacy fallback.
SIGNALS_PATH: Path | None = None
BRAIN_SIGNAL_SNAPSHOT_WORKSPACE_KEY = "shared_ops"
BRAIN_SIGNAL_SNAPSHOT_TYPE = "brain_signals"
BRAIN_SIGNAL_CHUNK_PREFIX = "brain_signals_chunk_"
_LOCK_PERMISSION_ERRNOS = frozenset({errno.EACCES, errno.EPERM, errno.EROFS})

_WORKSPACE_KEY_FIELDS = frozenset(
    {
        "source_workspace_key",
        "target_workspace_key",
        "workspace_key",
    }
)
_WORKSPACE_KEY_LIST_FIELDS = frozenset(
    {
        "brain_workspace_candidates",
        "target_workspace_keys",
        "workspace_candidates",
        "workspace_keys",
    }
)
_LEGACY_FEEZIE_LABELS = frozenset({"linkedin os", "linkedin content os"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _clean_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _clean_text(value)
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _canonical_workspace_list(values: Any) -> list[Any]:
    if not isinstance(values, list):
        normalized = _normalize_signal_payload(values)
        return normalized if isinstance(normalized, list) else []

    cleaned: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str):
            item = canonicalize_workspace_key(value, default=value)
            key = item.lower()
            if not item or key in seen:
                continue
            seen.add(key)
            cleaned.append(item)
            continue
        cleaned.append(_normalize_signal_payload(value))
    return cleaned


def _normalize_feezie_route_text(value: str) -> str:
    text = value
    replacements = (
        ("LinkedIn OS", "FEEZIE OS"),
        ("Linkedin OS", "FEEZIE OS"),
        ("LinkedIn/FEEZIE", "FEEZIE"),
        ("Linkedin/FEEZIE", "FEEZIE"),
        ("Feeze / LinkedIn", "Feeze / FEEZIE"),
        ("Feeze / Linkedin", "Feeze / FEEZIE"),
        ("LinkedIn lane", "FEEZIE lane"),
        ("Linkedin lane", "FEEZIE lane"),
        ("linkedin-os", "feezie-os"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.replace(
        "starting with LinkedIn and expanding over time into a broader personal-brand and career-positioning lane",
        "supporting identity-grounded public presence and career positioning",
    )
    return text


def _normalize_signal_payload(value: Any, *, field_name: str | None = None) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key in _WORKSPACE_KEY_FIELDS and isinstance(item, str):
                normalized[key] = canonicalize_workspace_key(item, default=item)
            elif key in _WORKSPACE_KEY_LIST_FIELDS:
                normalized[key] = _canonical_workspace_list(item)
            elif key in {"label", "workspace_label"} and isinstance(item, str):
                normalized[key] = "FEEZIE OS" if _clean_text(item).lower() in _LEGACY_FEEZIE_LABELS else item
            elif key in {"contract_excerpt", "reason", "route_reason"} and isinstance(item, str):
                normalized[key] = _normalize_feezie_route_text(item)
            elif key == "reasons" and isinstance(item, list):
                normalized[key] = [
                    _normalize_feezie_route_text(reason) if isinstance(reason, str) else _normalize_signal_payload(reason)
                    for reason in item
                ]
            else:
                normalized[key] = _normalize_signal_payload(item, field_name=key)
        return normalized

    if isinstance(value, list):
        if field_name in _WORKSPACE_KEY_LIST_FIELDS:
            return _canonical_workspace_list(value)
        return [_normalize_signal_payload(item, field_name=field_name) for item in value]

    return value


def _normalize_signal(signal: BrainSignal) -> BrainSignal:
    workspace_key = canonicalize_workspace_key(signal.source_workspace_key, default="shared_ops")
    candidates = _canonical_workspace_list(signal.workspace_candidates)
    if workspace_key and workspace_key not in candidates:
        candidates.insert(0, workspace_key)
    return signal.model_copy(
        update={
            "source_workspace_key": workspace_key,
            "workspace_candidates": candidates,
            "route_decision": _normalize_signal_payload(signal.route_decision or {}),
        }
    )


def _signals_read_path() -> Path:
    if SIGNALS_PATH is not None:
        return Path(SIGNALS_PATH).expanduser().resolve()
    return resolve_memory_read_path(
        "brain_signals.jsonl",
        project_root=ROOT,
        state_root=STATE_ROOT,
    )


def _signals_write_path(*, seed_legacy: bool = False) -> Path:
    if SIGNALS_PATH is not None:
        return Path(SIGNALS_PATH).expanduser().resolve()
    if seed_legacy:
        return seed_memory_state_file(
            "brain_signals.jsonl",
            project_root=ROOT,
            state_root=STATE_ROOT,
        )
    return memory_state_path("brain_signals.jsonl", state_root=STATE_ROOT)


def _signals_lock_path() -> Path:
    signals_path = _signals_write_path()
    return signals_path.with_name(f"{signals_path.name}.lock")


def _is_lock_permission_error(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or exc.errno in _LOCK_PERMISSION_ERRNOS


@contextmanager
def _signals_lock(*, exclusive: bool):
    if exclusive:
        # Preserve the complete legacy history before the first private-state
        # mutation. The seed helper is copy-only and publishes atomically.
        _signals_write_path(seed_legacy=True)
    lock_path = _signals_lock_path()
    lock_file = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = lock_path.open("a+", encoding="utf-8")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    except OSError as exc:
        if lock_file is not None:
            lock_file.close()
        if exclusive or not _is_lock_permission_error(exc):
            raise
        # Railway may mount the deployed snapshot read-only. In that case no
        # process can acquire the sibling lock *or* mutate the JSONL, so a
        # shared read can safely continue without manufacturing a 500/504.
        yield
        return

    assert lock_file is not None
    try:
        yield
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def _deserialize_signals(lines: list[str]) -> list[BrainSignal]:
    signals: list[BrainSignal] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            signals.append(_normalize_signal(BrainSignal.model_validate(payload)))
        except Exception:
            continue
    return signals


def _load_local_signals_unlocked() -> list[BrainSignal]:
    signals_path = _signals_read_path()
    if not signals_path.exists():
        return []
    return _deserialize_signals(signals_path.read_text(encoding="utf-8", errors="ignore").splitlines())


def _load_persisted_signals() -> list[BrainSignal] | None:
    try:
        payload = get_snapshot_payload(BRAIN_SIGNAL_SNAPSHOT_WORKSPACE_KEY, BRAIN_SIGNAL_SNAPSHOT_TYPE)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") == "brain_signals/v1":
        raw_signals = payload.get("signals")
        if not isinstance(raw_signals, list) or payload.get("count") != len(raw_signals):
            return None
    elif payload.get("schema_version") == "brain_signals_manifest/v1":
        manifest_chunks = payload.get("chunks")
        chunk_count = payload.get("chunk_count")
        total_count = payload.get("total_count")
        if (
            not isinstance(manifest_chunks, list)
            or not isinstance(chunk_count, int)
            or chunk_count < 1
            or chunk_count > 100
            or len(manifest_chunks) != chunk_count
            or not isinstance(total_count, int)
            or total_count < 0
            or total_count > 5_000
        ):
            return None
        try:
            persisted = list_snapshot_payloads(BRAIN_SIGNAL_SNAPSHOT_WORKSPACE_KEY)
        except Exception:
            return None
        raw_signals = []
        for index, chunk_ref in enumerate(manifest_chunks):
            if not isinstance(chunk_ref, dict):
                return None
            snapshot_type = chunk_ref.get("snapshot_type")
            if not isinstance(snapshot_type, str) or not snapshot_type.startswith(BRAIN_SIGNAL_CHUNK_PREFIX):
                return None
            chunk = persisted.get(snapshot_type)
            if (
                not isinstance(chunk, dict)
                or chunk.get("schema_version") != "brain_signals_chunk/v1"
                or chunk.get("snapshot_id") != payload.get("snapshot_id")
                or chunk.get("generated_at") != payload.get("generated_at")
                or chunk.get("source") != payload.get("source")
                or chunk.get("chunk_index") != index
                or chunk.get("chunk_count") != chunk_count
                or chunk.get("total_count") != total_count
                or not isinstance(chunk.get("signals"), list)
                or chunk_ref.get("chunk_index") != index
                or chunk_ref.get("count") != len(chunk["signals"])
            ):
                return None
            raw_signals.extend(chunk["signals"])
        if len(raw_signals) != total_count:
            return None
    else:
        return None
    signals: list[BrainSignal] = []
    try:
        for item in raw_signals:
            signals.append(_normalize_signal(BrainSignal.model_validate(item)))
    except Exception:
        return None
    return signals


def _load_signals() -> list[BrainSignal]:
    persisted = _load_persisted_signals()
    if persisted is not None:
        return persisted
    with _signals_lock(exclusive=False):
        return _load_local_signals_unlocked()


def _write_local_signals_unlocked(signals: list[BrainSignal]) -> None:
    signals_path = _signals_write_path(seed_legacy=True)
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(_normalize_signal(signal).model_dump(mode="json"), sort_keys=True) for signal in signals)
    fd, temp_path_raw = tempfile.mkstemp(
        prefix=f".{signals_path.name}.",
        suffix=".tmp",
        dir=str(signals_path.parent),
    )
    temp_path = Path(temp_path_raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write((text + "\n") if text else "")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, signals_path)
        try:
            directory_fd = os.open(signals_path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_signals(signals: list[BrainSignal]) -> None:
    with _signals_lock(exclusive=True):
        _write_local_signals_unlocked(signals)


def build_local_brain_signal_snapshot() -> dict[str, Any]:
    with _signals_lock(exclusive=False):
        signals = _load_local_signals_unlocked()
    return {
        "schema_version": "brain_signals/v1",
        "generated_at": _now().isoformat(),
        "source": "codex_local_runner",
        "count": len(signals),
        "signals": [signal.model_dump(mode="json") for signal in signals],
    }


def _source_signature(signal: BrainSignal | BrainSignalCreateRequest) -> tuple[str, str] | None:
    source_ref = _clean_text(signal.source_ref)
    if not source_ref:
        return None
    return (_clean_text(signal.source_kind).lower(), source_ref)


def list_signals(
    *,
    limit: int = 50,
    review_status: str | None = None,
    workspace_key: str | None = None,
) -> list[BrainSignal]:
    signals = _filtered_signals(review_status=review_status, workspace_key=workspace_key)
    return sorted(signals, key=lambda signal: signal.updated_at, reverse=True)[: max(1, min(int(limit or 50), 500))]


def count_signals(
    *,
    review_status: str | None = None,
    workspace_key: str | None = None,
) -> int:
    return len(_filtered_signals(review_status=review_status, workspace_key=workspace_key))


def list_signals_with_count(
    *,
    limit: int = 50,
    review_status: str | None = None,
    workspace_key: str | None = None,
) -> tuple[list[BrainSignal], int]:
    """Return a bounded preview and exact count from one on-disk snapshot read."""
    signals = _filtered_signals(review_status=review_status, workspace_key=workspace_key)
    bounded_limit = max(1, min(int(limit or 50), 500))
    return sorted(signals, key=lambda signal: signal.updated_at, reverse=True)[:bounded_limit], len(signals)


def _filtered_signals(*, review_status: str | None = None, workspace_key: str | None = None) -> list[BrainSignal]:
    normalized_status = _clean_text(review_status).lower()
    normalized_workspace = canonicalize_workspace_key(workspace_key, default="") if workspace_key else ""
    signals = _load_signals()
    if normalized_status:
        signals = [signal for signal in signals if _clean_text(signal.review_status).lower() == normalized_status]
    if normalized_workspace:
        signals = [
            signal
            for signal in signals
            if signal.source_workspace_key == normalized_workspace or normalized_workspace in signal.workspace_candidates
        ]
    return signals


def get_signal(signal_id: str) -> BrainSignal | None:
    for signal in _load_signals():
        if signal.id == signal_id:
            return signal
    return None


def get_local_signal(signal_id: str) -> BrainSignal | None:
    with _signals_lock(exclusive=False):
        for signal in _load_local_signals_unlocked():
            if signal.id == signal_id:
                return signal
    return None


def create_signal(payload: BrainSignalCreateRequest, *, action_card_id: str | None = None) -> BrainSignal:
    with _signals_lock(exclusive=True):
        return _create_signal_unlocked(payload, action_card_id=action_card_id)


def _create_signal_unlocked(
    payload: BrainSignalCreateRequest,
    *,
    action_card_id: str | None = None,
) -> BrainSignal:
    now = _now()
    workspace_key = canonicalize_workspace_key(payload.source_workspace_key, default="shared_ops")
    candidates = [canonicalize_workspace_key(item, default=item) for item in _clean_list(payload.workspace_candidates)]
    if workspace_key and workspace_key not in candidates:
        candidates.insert(0, workspace_key)

    signals = _load_local_signals_unlocked()
    if action_card_id:
        for signal in signals:
            route_decision = signal.route_decision if isinstance(signal.route_decision, dict) else {}
            if route_decision.get("brain_local_action_create_card_id") == action_card_id:
                return signal
    signature = _source_signature(payload)
    existing_index = None
    if signature is not None:
        for index, signal in enumerate(signals):
            if _source_signature(signal) == signature:
                existing_index = index
                break

    if existing_index is not None:
        existing = signals[existing_index]
        updated = existing.model_copy(
            update={
                "source_workspace_key": workspace_key,
                "raw_summary": _clean_text(payload.raw_summary) or existing.raw_summary,
                "digest": _clean_text(payload.digest) or existing.digest,
                "signal_types": _clean_list([*existing.signal_types, *payload.signal_types]),
                "durability": _clean_text(payload.durability) or existing.durability,
                "confidence": _clean_text(payload.confidence) or existing.confidence,
                "actionability": _clean_text(payload.actionability) or existing.actionability,
                "identity_relevance": _clean_text(payload.identity_relevance) or existing.identity_relevance,
                "workspace_candidates": _clean_list([*existing.workspace_candidates, *candidates]),
                "executive_interpretation": {
                    **(existing.executive_interpretation or {}),
                    **(payload.executive_interpretation or {}),
                },
                "route_decision": _normalize_signal_payload({
                    **(existing.route_decision or {}),
                    **(payload.route_decision or {}),
                    **({"brain_local_action_create_card_id": action_card_id} if action_card_id else {}),
                }),
                "updated_at": now,
            }
        )
        signals[existing_index] = updated
        _write_local_signals_unlocked(signals)
        return updated

    signal = BrainSignal(
        id=str(uuid4()),
        source_kind=_clean_text(payload.source_kind),
        source_ref=_clean_text(payload.source_ref) or None,
        source_workspace_key=workspace_key,
        raw_summary=_clean_text(payload.raw_summary) or _clean_text(payload.digest),
        digest=_clean_text(payload.digest) or None,
        signal_types=_clean_list(payload.signal_types),
        durability=_clean_text(payload.durability) or "unknown",
        confidence=_clean_text(payload.confidence) or "unknown",
        actionability=_clean_text(payload.actionability) or "unknown",
        identity_relevance=_clean_text(payload.identity_relevance) or "unknown",
        workspace_candidates=candidates,
        executive_interpretation=payload.executive_interpretation or {},
        route_decision=_normalize_signal_payload(
            {
                **(payload.route_decision or {}),
                **({"brain_local_action_create_card_id": action_card_id} if action_card_id else {}),
            }
        ),
        review_status="new",
        created_at=now,
        updated_at=now,
    )
    signals.append(signal)
    _write_local_signals_unlocked(signals)
    return signal


def review_signal(signal_id: str, payload: BrainSignalReviewRequest) -> BrainSignal | None:
    with _signals_lock(exclusive=True):
        return _review_signal_unlocked(signal_id, payload)


def _review_signal_unlocked(signal_id: str, payload: BrainSignalReviewRequest) -> BrainSignal | None:
    signals = _load_local_signals_unlocked()
    for index, signal in enumerate(signals):
        if signal.id != signal_id:
            continue
        update: dict[str, Any] = {"updated_at": _now()}
        for field in (
            "digest",
            "durability",
            "confidence",
            "actionability",
            "identity_relevance",
            "review_status",
        ):
            value = getattr(payload, field)
            if value is not None:
                update[field] = _clean_text(value)
        if payload.signal_types is not None:
            update["signal_types"] = _clean_list(payload.signal_types)
        if payload.workspace_candidates is not None:
            update["workspace_candidates"] = [
                canonicalize_workspace_key(item, default=item) for item in _clean_list(payload.workspace_candidates)
            ]
        if payload.executive_interpretation is not None:
            update["executive_interpretation"] = {
                key: _clean_text(value)
                for key, value in payload.executive_interpretation.items()
                if _clean_text(key) and _clean_text(value)
            }
        if payload.route_decision is not None:
            update["route_decision"] = _normalize_signal_payload(payload.route_decision)
        updated = signal.model_copy(update=update)
        signals[index] = updated
        _write_local_signals_unlocked(signals)
        return updated
    return None


def route_signal(
    signal_id: str,
    payload: BrainSignalRouteRequest,
    *,
    route_effect: dict[str, Any] | None = None,
    action_card_id: str | None = None,
) -> BrainSignal | None:
    with _signals_lock(exclusive=True):
        return _route_signal_unlocked(
            signal_id,
            payload,
            route_effect=route_effect,
            action_card_id=action_card_id,
        )


def _route_signal_unlocked(
    signal_id: str,
    payload: BrainSignalRouteRequest,
    *,
    route_effect: dict[str, Any] | None = None,
    action_card_id: str | None = None,
) -> BrainSignal | None:
    signals = _load_local_signals_unlocked()
    for index, signal in enumerate(signals):
        if signal.id != signal_id:
            continue

        workspace_key = canonicalize_workspace_key(payload.workspace_key, default=signal.source_workspace_key or "shared_ops")
        summary = _clean_text(payload.summary) or _clean_text(payload.route_reason) or signal.digest or signal.raw_summary
        now = _now()
        route_result: dict[str, Any] = {
            "route": payload.route,
            "workspace_key": workspace_key,
            "summary": summary,
            "route_reason": _clean_text(payload.route_reason),
            "canonical_memory_targets": _clean_list(payload.canonical_memory_targets),
            "routed_at": now.isoformat(),
        }
        if action_card_id:
            route_result["brain_local_action_card_id"] = action_card_id
        executive_interpretation = {
            **(signal.executive_interpretation or {}),
            **{
                _clean_text(key): _clean_text(value)
                for key, value in (payload.executive_interpretation or {}).items()
                if _clean_text(key) and _clean_text(value)
            },
        }

        if payload.route == "standup":
            if route_effect is not None:
                standup_payload = route_effect.get("standup")
                if not isinstance(standup_payload, dict):
                    raise ValueError("Brain signal standup route effect is missing.")
                route_result["standup"] = standup_payload
            else:
                standup = _create_signal_standup(
                    signal=signal,
                    workspace_key=workspace_key,
                    summary=summary,
                    requested_kind=payload.standup_kind,
                    observed_at=now,
                )
                route_result["standup"] = standup.model_dump(mode="json")
        elif payload.route == "pm":
            if route_effect is not None:
                pm_card_payload = route_effect.get("pm_card")
                if not isinstance(pm_card_payload, dict):
                    raise ValueError("Brain signal PM route effect is missing.")
                route_result["pm_card"] = pm_card_payload
            else:
                pm_card = _create_signal_pm_card(
                    signal=signal,
                    workspace_key=workspace_key,
                    summary=summary,
                    pm_title=payload.pm_title,
                )
                route_result["pm_card"] = pm_card.model_dump(mode="json")
        elif payload.route == "canonical_memory":
            canonical_payload = (route_effect or {}).get("canonical_memory")
            if not isinstance(canonical_payload, dict):
                raise ValueError("Brain signal canonical-memory route effect is missing.")
            route_result["canonical_memory"] = canonical_payload
        elif payload.route == "persona_canon":
            persona_payload = (route_effect or {}).get("persona_delta")
            if not isinstance(persona_payload, dict):
                raise ValueError("Brain signal persona-canon route effect is missing.")
            route_result["persona_delta"] = persona_payload
        elif payload.route == "workspace_local":
            workspace_payload = (route_effect or {}).get("workspace_local")
            if not isinstance(workspace_payload, dict):
                raise ValueError("Brain signal workspace-local route effect is missing.")
            route_result["workspace_local"] = workspace_payload
        elif payload.route == "ignore":
            route_result["ignored_reason"] = summary or "Signal explicitly ignored."

        updated = signal.model_copy(
            update={
                "source_workspace_key": workspace_key,
                "workspace_candidates": _clean_list([*signal.workspace_candidates, workspace_key]),
                "executive_interpretation": executive_interpretation,
                "route_decision": _normalize_signal_payload({
                    **(signal.route_decision or {}),
                    "latest": route_result,
                    "history": [*(signal.route_decision or {}).get("history", []), route_result],
                }),
                "review_status": "ignored" if payload.route == "ignore" else "routed",
                "updated_at": now,
            }
        )
        signals[index] = updated
        _write_local_signals_unlocked(signals)
        return updated
    return None


def build_signal_route_effect(
    signal: BrainSignal,
    payload: BrainSignalRouteRequest,
    *,
    action_card_id: str,
) -> dict[str, Any]:
    """Commit only the Postgres side of a signed local signal route."""
    workspace_key = canonicalize_workspace_key(payload.workspace_key, default=signal.source_workspace_key or "shared_ops")
    summary = _clean_text(payload.summary) or _clean_text(payload.route_reason) or signal.digest or signal.raw_summary
    if payload.route == "standup":
        for existing in standup_service.list_standups(limit=500, workspace_key=workspace_key):
            existing_payload = dict(existing.payload or {})
            if existing_payload.get("brain_local_action_card_id") == action_card_id:
                return {"standup": existing.model_dump(mode="json"), "reused": True}
        standup = _create_signal_standup(
            signal=signal,
            workspace_key=workspace_key,
            summary=summary,
            requested_kind=payload.standup_kind,
            action_card_id=action_card_id,
            observed_at=_now(),
        )
        return {"standup": standup.model_dump(mode="json"), "reused": False}
    if payload.route == "pm":
        title = _clean_text(payload.pm_title)
        source_signature = f"brain-signal:{signal.id}:{workspace_key}"
        existing = pm_card_service.find_card_by_signature(title, source_signature)
        if existing is None:
            existing = pm_card_service.find_active_card_by_title(title, workspace_key)
        if existing is not None:
            return {"pm_card": existing.model_dump(mode="json"), "reused": True}
        pm_card = _create_signal_pm_card(
            signal=signal,
            workspace_key=workspace_key,
            summary=summary,
            pm_title=payload.pm_title,
            action_card_id=action_card_id,
        )
        return {"pm_card": pm_card.model_dump(mode="json"), "reused": False}
    if payload.route == "persona_canon":
        for existing in persona_delta_service.list_deltas(limit=500):
            metadata = dict(existing.metadata or {})
            if metadata.get("brain_local_action_card_id") == action_card_id:
                return {"persona_delta": existing.model_dump(mode="json"), "reused": True}
        candidate_summary = summary[:2_000]
        source_evidence = _clean_text(signal.source_ref) or signal.id
        delta = persona_delta_service.create_delta(
            PersonaDeltaCreate(
                persona_target="feeze.core",
                trait=candidate_summary,
                notes=(signal.raw_summary or candidate_summary)[:4_000],
                metadata={
                    "review_source": "brain_signal.route",
                    "source": "brain_signal",
                    "brain_signal_id": signal.id,
                    "brain_local_action_card_id": action_card_id,
                    "source_kind": signal.source_kind[:120],
                    "source_ref": source_evidence[:500],
                    "workspace_key": workspace_key,
                    "route_summary": candidate_summary,
                    "target_file": "identity/philosophy.md",
                    "talking_points": [
                        {
                            "label": "Brain Signal canon candidate",
                            "content": candidate_summary,
                            "evidence": source_evidence[:500],
                            "target_file": "identity/philosophy.md",
                        }
                    ],
                },
            )
        )
        return {"persona_delta": delta.model_dump(mode="json"), "reused": False}
    return {"reused": True}


def _create_signal_standup(
    *,
    signal: BrainSignal,
    workspace_key: str,
    summary: str,
    requested_kind: str,
    action_card_id: str | None = None,
    observed_at: datetime | None = None,
) -> Any:
    standup_kind = canonical_standup_kind_for_workspace(
        workspace_key,
        requested_kind,
    )
    participants = standup_participants_for(workspace_key, standup_kind)
    routed_at = as_utc(observed_at or _now())
    relevance_pending = standup_relevance_required_for(workspace_key)
    participant_claims: dict[str, Any] = {"participants": participants}
    if relevance_pending:
        participant_claims.update(
            {
                "participants": [],
                "participant_selection_state": "pending_standup_prep_relevance",
                "participant_selection_authority": "standup_relevance/v1",
                "participant_selection_next_step": "standup_prep",
                "canonical_pm_execution_authority": "Jean-Claude",
                "pm_execution_authority_transferred": False,
            }
        )
    review_label = (
        "governed FEEZIE relevance evaluation"
        if relevance_pending
        else "meeting review"
    )
    return standup_service.create_standup(
        StandupCreate(
            owner="Jean-Claude",
            workspace_key=workspace_key,
            status="queued",
            needs=[f"Brain Signal routed for {review_label}: {signal.raw_summary}"],
            source="brain_signal",
            payload={
                "standup_kind": standup_kind,
                "observed_at": utc_iso(routed_at),
                "clock": clock_receipt(routed_at),
                "summary": summary,
                "agenda": [
                    f"Review Brain Signal: {signal.raw_summary}",
                    "Decide whether this stays source-only, becomes memory, becomes PM work, or remains workspace-local.",
                ],
                **participant_claims,
                "brain_signal_id": signal.id,
                "brain_local_action_card_id": action_card_id,
                "source_kind": signal.source_kind,
                "source_ref": signal.source_ref,
            },
        )
    )


def _create_signal_pm_card(
    *,
    signal: BrainSignal,
    workspace_key: str,
    summary: str,
    pm_title: str | None,
    action_card_id: str | None = None,
) -> Any:
    title = _clean_text(pm_title)
    if not title:
        raise ValueError("Provide pm_title for PM routes.")
    source_signature = f"brain-signal:{signal.id}:{workspace_key}"
    execution_defaults = pm_card_service.execution_defaults_for_workspace(workspace_key)
    owner = str(execution_defaults.get("manager_agent") or "Jean-Claude").strip() or "Jean-Claude"
    why_pm_now = f"Brain Signal review routed this into executable work: {summary}"
    contract = build_execution_contract(
        title=title,
        workspace_key=workspace_key,
        source="brain_signal",
        reason=why_pm_now,
        instructions=[
            "Use the Brain Signal digest and executive interpretation as the source of truth.",
            "Convert the signal into one bounded workspace outcome without forwarding raw global source intelligence.",
            "Write back the execution result with concrete outcome, artifact, and blocker state.",
        ],
        acceptance_criteria=[
            f"`{title}` produces a bounded execution result inside `{workspace_key}`.",
            "PM write-back cites the Brain Signal and includes a concrete outcome or artifact.",
        ],
        artifacts_expected=[
            "updated PM execution result",
            "workspace-local artifact or execution memo tied to the Brain Signal",
        ],
    )
    source_signal = {
        "kind": "brain_signal",
        "signal_id": signal.id,
        "source_kind": signal.source_kind,
        "source_ref": signal.source_ref,
        "summary": summary,
    }
    validation = validate_brain_pm_route(
        title=title,
        workspace_key=workspace_key,
        summary=summary,
        owner=owner,
        why_pm_now=why_pm_now,
        acceptance_criteria=contract["acceptance_criteria"],
        completion_contract=contract["completion_contract"],
        source_signal=source_signal,
    )
    if not validation["ok"]:
        raise ValueError(str(validation["reason"]))
    existing = pm_card_service.find_card_by_signature(title, source_signature)
    if existing is None:
        existing = pm_card_service.find_active_card_by_title(title, workspace_key)
    if existing is not None:
        raise ValueError("Brain Signal PM route rejected: duplicate active PM card already exists.")
    return pm_card_service.create_card(
        PMCardCreate(
            title=title,
            owner=owner,
            status="todo",
            source=source_signature,
            link_type="brain_signal",
            link_id=signal.id,
            payload={
                "workspace_key": workspace_key,
                "reason": why_pm_now,
                "why_pm_now": why_pm_now,
                "source_signal": source_signal,
                "brain_signal_id": signal.id,
                "brain_local_action_card_id": action_card_id,
                "brain_signal_summary": summary,
                "route_guardrail": validation,
                "instructions": contract["instructions"],
                "acceptance_criteria": contract["acceptance_criteria"],
                "artifacts_expected": contract["artifacts_expected"],
                "completion_contract": contract["completion_contract"],
                "writeback_requirements": contract["completion_contract"].get("result_requirements", {}),
                "execution": {
                    "lane": "codex",
                    "state": "queued",
                    "manager_agent": execution_defaults["manager_agent"],
                    "target_agent": execution_defaults["target_agent"],
                    "workspace_agent": execution_defaults.get("workspace_agent"),
                    "execution_mode": execution_defaults["execution_mode"],
                    "requested_by": "Brain",
                    "assigned_runner": "codex",
                    "reason": f"Brain routed signal {signal.id}.",
                    "queued_at": _now().isoformat(),
                    "last_transition_at": _now().isoformat(),
                    "source": "brain_signal",
                },
            },
        )
    )
