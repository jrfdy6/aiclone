from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services import local_codex_context_cache_service as service


def _payload(*, created_at: str, version: str = service._CACHE_VERSION) -> dict:
    return {
        "cache_key": "key",
        "workspace_slug": "linkedin-content-os",
        "snapshot_hash": "snapshot",
        "request": {},
        "context_packet": {"prompt": "hello"},
        "created_at": created_at,
        "cache_version": version,
    }


def test_context_cache_rejects_expired_persona_context(tmp_path: Path) -> None:
    cache_dir = tmp_path / "context-cache"
    cache_dir.mkdir(parents=True)
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    (cache_dir / "key.json").write_text(json.dumps(_payload(created_at=old.isoformat())), encoding="utf-8")

    with patch.object(service, "_store_dir", return_value=tmp_path), patch.dict(
        "os.environ",
        {"LOCAL_CODEX_CONTEXT_CACHE_TTL_SECONDS": "14400"},
    ):
        assert service.load_cached_context_packet(cache_key="key") is None


def test_context_cache_accepts_fresh_current_version(tmp_path: Path) -> None:
    cache_dir = tmp_path / "context-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "key.json").write_text(
        json.dumps(_payload(created_at=datetime.now(timezone.utc).isoformat())),
        encoding="utf-8",
    )

    with patch.object(service, "_store_dir", return_value=tmp_path):
        assert service.load_cached_context_packet(cache_key="key")["context_packet"]["prompt"] == "hello"


def test_context_cache_rejects_prior_contract_version(tmp_path: Path) -> None:
    cache_dir = tmp_path / "context-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "key.json").write_text(
        json.dumps(_payload(created_at=datetime.now(timezone.utc).isoformat(), version="local-codex-context-v3")),
        encoding="utf-8",
    )

    with patch.object(service, "_store_dir", return_value=tmp_path):
        assert service.load_cached_context_packet(cache_key="key") is None
