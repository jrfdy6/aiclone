from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.feezie_positioning_contract_service import load_feezie_strategy_contract
from app.services.persona_bundle_context_service import load_bundle_persona_chunks, load_committed_overlay_chunks
from app.services.workspace_snapshot_store import get_snapshot_payload


_CACHE_VERSION = "local-codex-context-v9"
_CACHE_KEYS = {
    "cache_key",
    "workspace_slug",
    "snapshot_hash",
    "request",
    "context_packet",
    "created_at",
    "cache_version",
    "payload_sha256",
}
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_MAX_CACHE_BYTES = 2 * 1024 * 1024
_MAX_FUTURE_SKEW_SECONDS = 300
_SNAPSHOT_TYPES = (
    "source_assets",
    "content_reservoir",
    "operator_story_signals",
    "content_safe_operator_lessons",
    "weekly_plan",
    "reaction_queue",
    "publication_performance_summary",
    "feezie_runtime_context",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_dir() -> Path:
    explicit = (os.getenv("LOCAL_CODEX_JOB_STORE_DIR") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path(tempfile.gettempdir()) / "aiclone-local-codex-jobs"


def _cache_dir() -> Path:
    return _store_dir() / "context-cache"


def _ensure_private_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise RuntimeError("Local Codex context cache directories must be absolute.")
    if path.is_symlink():
        raise RuntimeError("Local Codex context cache directories must not be symlinks.")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError("Local Codex context cache path is not a directory.")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RuntimeError("Local Codex context cache directory has the wrong owner.")
    if stat.S_IMODE(info.st_mode) != 0o700:
        os.chmod(path, 0o700)
        if stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) != 0o700:
            raise RuntimeError("Local Codex context cache directory is not private.")
    return path


def _secure_cache_dir() -> Path:
    store_dir = _ensure_private_directory(_store_dir())
    return _ensure_private_directory(store_dir / "context-cache")


def _validated_cache_key(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(normalized) is None:
        raise ValueError("Local Codex context cache keys must be lowercase SHA-256 digests.")
    return normalized


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _cache_payload_core(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in (
            "cache_key",
            "workspace_slug",
            "snapshot_hash",
            "request",
            "context_packet",
            "created_at",
            "cache_version",
        )
    }


def _cache_payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(_cache_payload_core(payload))).hexdigest()


def _normalize_workspace_slug(value: str | None) -> str:
    slug = " ".join((value or "").split()).strip().lower()
    return slug or "linkedin-content-os"


def _snapshot_hash(workspace_slug: str) -> str:
    normalized_workspace = _normalize_workspace_slug(workspace_slug)
    payloads: dict[str, Any] = {}
    for snapshot_type in _SNAPSHOT_TYPES:
        snapshot_workspace = (
            "feezie-os"
            if snapshot_type in {"publication_performance_summary", "feezie_runtime_context"}
            else normalized_workspace
        )
        payload = get_snapshot_payload(snapshot_workspace, snapshot_type)
        if isinstance(payload, dict):
            payloads[snapshot_type] = payload
    serialized = json.dumps(payloads, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _strategy_contract_hash() -> str:
    contract = load_feezie_strategy_contract()
    return str(contract.get("contract_hash") or "").strip()


def _persona_context_hash() -> str:
    chunks = [*load_committed_overlay_chunks(), *load_bundle_persona_chunks()]
    safe_manifest = [
        {
            "source_id": str(item.get("source_id") or ""),
            "chunk_hash": hashlib.sha256(str(item.get("chunk") or "").encode("utf-8")).hexdigest(),
            "persona_tag": str(item.get("persona_tag") or ""),
            "source_kind": str((item.get("metadata") or {}).get("source_kind") or ""),
        }
        for item in chunks
        if isinstance(item, dict)
    ]
    serialized = json.dumps(safe_manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _request_fingerprint(request_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(request_payload.get("user_id") or ""),
        "topic": str(request_payload.get("topic") or ""),
        "context": str(request_payload.get("context") or ""),
        "content_type": str(request_payload.get("content_type") or ""),
        "category": str(request_payload.get("category") or ""),
        "tone": str(request_payload.get("tone") or ""),
        "audience": str(request_payload.get("audience") or ""),
        "source_mode": str(request_payload.get("source_mode") or ""),
        "canonical_pillar": str(request_payload.get("canonical_pillar") or ""),
        "career_signal": str(request_payload.get("career_signal") or ""),
        "employer_proximity": str(request_payload.get("employer_proximity") or ""),
        "employer_safety": str(request_payload.get("employer_safety") or ""),
        "proof_posture": str(request_payload.get("proof_posture") or ""),
        "treatment": str(request_payload.get("treatment") or ""),
    }


def _bound_cache_key(*, workspace_slug: str, snapshot_hash: str, request_payload: dict[str, Any]) -> str:
    binding = {
        "version": _CACHE_VERSION,
        "workspace_slug": _normalize_workspace_slug(workspace_slug),
        "snapshot_hash": str(snapshot_hash or "").strip().lower(),
        "request": _request_fingerprint(request_payload),
    }
    return hashlib.sha256(_canonical_json_bytes(binding)).hexdigest()


def build_context_cache_key(*, workspace_slug: str, request_payload: dict[str, Any]) -> tuple[str, str]:
    normalized_workspace = _normalize_workspace_slug(workspace_slug)
    source_hashes = {
        "workspace_snapshots": _snapshot_hash(normalized_workspace),
        "strategy_contract": _strategy_contract_hash(),
        "persona_context": _persona_context_hash(),
    }
    serialized_source_hashes = json.dumps(source_hashes, sort_keys=True, separators=(",", ":"))
    snapshot_hash = hashlib.sha256(serialized_source_hashes.encode("utf-8")).hexdigest()
    return (
        _bound_cache_key(
            workspace_slug=normalized_workspace,
            snapshot_hash=snapshot_hash,
            request_payload=request_payload,
        ),
        snapshot_hash,
    )


def load_cached_context_packet(
    *,
    cache_key: str,
    workspace_slug: str,
    snapshot_hash: str,
    request_payload: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        normalized_key = _validated_cache_key(cache_key)
        normalized_workspace = _normalize_workspace_slug(workspace_slug)
        normalized_snapshot_hash = str(snapshot_hash or "").strip().lower()
        if _SHA256_RE.fullmatch(normalized_snapshot_hash) is None:
            return None
        if not isinstance(request_payload, dict):
            return None
        expected_request = _request_fingerprint(request_payload)
        if normalized_key != _bound_cache_key(
            workspace_slug=normalized_workspace,
            snapshot_hash=normalized_snapshot_hash,
            request_payload=request_payload,
        ):
            return None
        cache_dir = _secure_cache_dir()
    except (OSError, RuntimeError, ValueError):
        return None
    path = cache_dir / f"{normalized_key}.json"
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size <= 0
            or info.st_size > _MAX_CACHE_BYTES
            or stat.S_IMODE(info.st_mode) & 0o077
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())
        ):
            os.close(descriptor)
            return None
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            rendered = handle.read(_MAX_CACHE_BYTES + 1)
        if len(rendered.encode("utf-8")) > _MAX_CACHE_BYTES:
            return None
        payload = json.loads(rendered)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or set(payload) != _CACHE_KEYS
        or payload.get("cache_version") != _CACHE_VERSION
        or payload.get("cache_key") != normalized_key
        or payload.get("workspace_slug") != normalized_workspace
        or payload.get("snapshot_hash") != normalized_snapshot_hash
        or payload.get("request") != expected_request
        or not isinstance(payload.get("request"), dict)
        or not isinstance(payload.get("context_packet"), dict)
        or _SHA256_RE.fullmatch(str(payload.get("payload_sha256") or "")) is None
    ):
        return None
    try:
        if payload["payload_sha256"] != _cache_payload_sha256(payload):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    try:
        ttl_seconds = max(0, int(os.getenv("LOCAL_CODEX_CONTEXT_CACHE_TTL_SECONDS", "14400")))
    except ValueError:
        ttl_seconds = 14400
    created_at = str(payload.get("created_at") or "").strip()
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if created.tzinfo is None or created.utcoffset() is None:
        return None
    age_seconds = (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()
    if age_seconds < -_MAX_FUTURE_SKEW_SECONDS:
        return None
    if ttl_seconds and age_seconds > ttl_seconds:
        return None
    return payload


def write_cached_context_packet(
    *,
    cache_key: str,
    workspace_slug: str,
    snapshot_hash: str,
    request_payload: dict[str, Any],
    context_packet: dict[str, Any],
) -> dict[str, Any]:
    normalized_key = _validated_cache_key(cache_key)
    normalized_snapshot_hash = str(snapshot_hash or "").strip().lower()
    if _SHA256_RE.fullmatch(normalized_snapshot_hash) is None:
        raise ValueError("Local Codex context snapshot hashes must be lowercase SHA-256 digests.")
    if not isinstance(request_payload, dict) or not isinstance(context_packet, dict):
        raise ValueError("Local Codex context cache payloads must be mappings.")
    normalized_workspace = _normalize_workspace_slug(workspace_slug)
    expected_key = _bound_cache_key(
        workspace_slug=normalized_workspace,
        snapshot_hash=normalized_snapshot_hash,
        request_payload=request_payload,
    )
    if normalized_key != expected_key:
        raise ValueError("Local Codex context cache key does not match its workspace, snapshot, and request binding.")
    cache_dir = _secure_cache_dir()
    payload = {
        "cache_key": normalized_key,
        "workspace_slug": normalized_workspace,
        "snapshot_hash": normalized_snapshot_hash,
        "request": _request_fingerprint(request_payload),
        "context_packet": context_packet,
        "created_at": _utcnow_iso(),
        "cache_version": _CACHE_VERSION,
    }
    payload["payload_sha256"] = _cache_payload_sha256(payload)
    rendered = _canonical_json_bytes(payload)
    if len(rendered) > _MAX_CACHE_BYTES:
        raise ValueError("Local Codex context cache payload exceeds the private size bound.")
    path = cache_dir / f"{normalized_key}.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".context-", suffix=".tmp", dir=cache_dir)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
        directory_descriptor = os.open(cache_dir, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        except OSError:
            pass
    return payload
