from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.workspace_snapshot_store import get_snapshot_payload


_CACHE_VERSION = "local-codex-context-v3"
_SNAPSHOT_TYPES = (
    "source_assets",
    "content_reservoir",
    "operator_story_signals",
    "content_safe_operator_lessons",
    "weekly_plan",
    "reaction_queue",
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


def _normalize_workspace_slug(value: str | None) -> str:
    slug = " ".join((value or "").split()).strip().lower()
    return slug or "linkedin-content-os"


def _snapshot_hash(workspace_slug: str) -> str:
    normalized_workspace = _normalize_workspace_slug(workspace_slug)
    payloads: dict[str, Any] = {}
    for snapshot_type in _SNAPSHOT_TYPES:
        payload = get_snapshot_payload(normalized_workspace, snapshot_type)
        if isinstance(payload, dict):
            payloads[snapshot_type] = payload
    serialized = json.dumps(payloads, sort_keys=True, separators=(",", ":"), default=str)
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
    }


def build_context_cache_key(*, workspace_slug: str, request_payload: dict[str, Any]) -> tuple[str, str]:
    normalized_workspace = _normalize_workspace_slug(workspace_slug)
    snapshot_hash = _snapshot_hash(normalized_workspace)
    key_payload = {
        "version": _CACHE_VERSION,
        "workspace_slug": normalized_workspace,
        "snapshot_hash": snapshot_hash,
        "request": _request_fingerprint(request_payload),
    }
    serialized = json.dumps(key_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest(), snapshot_hash


def load_cached_context_packet(*, cache_key: str) -> dict[str, Any] | None:
    path = _cache_dir() / f"{cache_key}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_cached_context_packet(
    *,
    cache_key: str,
    workspace_slug: str,
    snapshot_hash: str,
    request_payload: dict[str, Any],
    context_packet: dict[str, Any],
) -> dict[str, Any]:
    _cache_dir().mkdir(parents=True, exist_ok=True)
    payload = {
        "cache_key": cache_key,
        "workspace_slug": _normalize_workspace_slug(workspace_slug),
        "snapshot_hash": snapshot_hash,
        "request": _request_fingerprint(request_payload),
        "context_packet": context_packet,
        "created_at": _utcnow_iso(),
        "cache_version": _CACHE_VERSION,
    }
    path = _cache_dir() / f"{cache_key}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload
