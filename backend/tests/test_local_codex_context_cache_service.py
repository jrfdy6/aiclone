from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import local_codex_context_cache_service as service


SNAPSHOT_HASH = "b" * 64
DEFAULT_REQUEST: dict = {}
CACHE_KEY = service._bound_cache_key(
    workspace_slug="linkedin-content-os",
    snapshot_hash=SNAPSHOT_HASH,
    request_payload=DEFAULT_REQUEST,
)


def _payload(*, created_at: str, version: str = service._CACHE_VERSION) -> dict:
    payload = {
        "cache_key": CACHE_KEY,
        "workspace_slug": "linkedin-content-os",
        "snapshot_hash": SNAPSHOT_HASH,
        "request": service._request_fingerprint({}),
        "context_packet": {"prompt": "hello"},
        "created_at": created_at,
        "cache_version": version,
    }
    payload["payload_sha256"] = service._cache_payload_sha256(payload)
    return payload


def _persist_payload(tmp_path: Path, payload: dict) -> Path:
    cache_dir = tmp_path / "context-cache"
    cache_dir.mkdir(mode=0o700, parents=True)
    cache_dir.chmod(0o700)
    path = cache_dir / f"{CACHE_KEY}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def _load(*, request_payload: dict | None = None) -> dict | None:
    return service.load_cached_context_packet(
        cache_key=CACHE_KEY,
        workspace_slug="linkedin-content-os",
        snapshot_hash=SNAPSHOT_HASH,
        request_payload=request_payload or {},
    )


def test_context_cache_rejects_expired_persona_context(tmp_path: Path) -> None:
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    _persist_payload(tmp_path, _payload(created_at=old.isoformat()))

    with patch.object(service, "_store_dir", return_value=tmp_path), patch.dict(
        "os.environ",
        {"LOCAL_CODEX_CONTEXT_CACHE_TTL_SECONDS": "14400"},
    ):
        assert _load() is None


def test_context_cache_accepts_fresh_current_version(tmp_path: Path) -> None:
    _persist_payload(tmp_path, _payload(created_at=datetime.now(timezone.utc).isoformat()))

    with patch.object(service, "_store_dir", return_value=tmp_path):
        assert _load()["context_packet"]["prompt"] == "hello"


def test_context_cache_rejects_prior_contract_version(tmp_path: Path) -> None:
    _persist_payload(
        tmp_path,
        _payload(created_at=datetime.now(timezone.utc).isoformat(), version="local-codex-context-v3"),
    )

    with patch.object(service, "_store_dir", return_value=tmp_path):
        assert _load() is None


def test_context_cache_requires_timestamp_key_hash_and_private_file_mode(tmp_path: Path) -> None:
    payload = _payload(created_at=datetime.now(timezone.utc).isoformat())
    path = _persist_payload(tmp_path, payload)

    with patch.object(service, "_store_dir", return_value=tmp_path):
        tampered = dict(payload)
        tampered["context_packet"] = {"prompt": "changed after receipt"}
        path.write_text(json.dumps(tampered), encoding="utf-8")
        path.chmod(0o600)
        assert _load() is None

        missing_timestamp = _payload(created_at=datetime.now(timezone.utc).isoformat())
        missing_timestamp["created_at"] = ""
        missing_timestamp["payload_sha256"] = service._cache_payload_sha256(missing_timestamp)
        path.write_text(json.dumps(missing_timestamp), encoding="utf-8")
        path.chmod(0o600)
        assert _load() is None

        fresh = _payload(created_at=datetime.now(timezone.utc).isoformat())
        path.write_text(json.dumps(fresh), encoding="utf-8")
        path.chmod(0o644)
        assert _load() is None


def test_context_cache_rejects_future_timestamp_and_symlink(tmp_path: Path) -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    path = _persist_payload(tmp_path, _payload(created_at=future.isoformat()))
    with patch.object(service, "_store_dir", return_value=tmp_path):
        assert _load() is None

    path.unlink()
    target = tmp_path / "outside.json"
    target.write_text(json.dumps(_payload(created_at=datetime.now(timezone.utc).isoformat())), encoding="utf-8")
    path.symlink_to(target)
    with patch.object(service, "_store_dir", return_value=tmp_path):
        assert _load() is None


def test_context_cache_writer_is_hash_bound_and_private(tmp_path: Path) -> None:
    request_payload = {"topic": "bounded cache"}
    writer_cache_key = service._bound_cache_key(
        workspace_slug="linkedin-content-os",
        snapshot_hash=SNAPSHOT_HASH,
        request_payload=request_payload,
    )
    with patch.object(service, "_store_dir", return_value=tmp_path):
        payload = service.write_cached_context_packet(
            cache_key=writer_cache_key,
            workspace_slug="linkedin-content-os",
            snapshot_hash=SNAPSHOT_HASH,
            request_payload=request_payload,
            context_packet={"prompt": "private local packet"},
        )
        loaded = service.load_cached_context_packet(
            cache_key=writer_cache_key,
            workspace_slug="linkedin-content-os",
            snapshot_hash=SNAPSHOT_HASH,
            request_payload=request_payload,
        )

    path = tmp_path / "context-cache" / f"{writer_cache_key}.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "context-cache").stat().st_mode & 0o777 == 0o700
    assert payload["payload_sha256"] == service._cache_payload_sha256(payload)
    assert loaded == payload

    with patch.object(service, "_store_dir", return_value=tmp_path):
        with pytest.raises(ValueError, match="does not match"):
            service.write_cached_context_packet(
                cache_key=CACHE_KEY,
                workspace_slug="linkedin-content-os",
                snapshot_hash=SNAPSHOT_HASH,
                request_payload=request_payload,
                context_packet={"prompt": "wrong binding"},
            )


def test_context_cache_rejects_wrong_embedded_workspace_snapshot_or_request(tmp_path: Path) -> None:
    path = _persist_payload(tmp_path, _payload(created_at=datetime.now(timezone.utc).isoformat()))

    with patch.object(service, "_store_dir", return_value=tmp_path):
        for field, replacement in (
            ("workspace_slug", "another-workspace"),
            ("snapshot_hash", "c" * 64),
            ("request", {"topic": "different request"}),
        ):
            payload = _payload(created_at=datetime.now(timezone.utc).isoformat())
            payload[field] = replacement
            payload["payload_sha256"] = service._cache_payload_sha256(payload)
            path.write_text(json.dumps(payload), encoding="utf-8")
            path.chmod(0o600)
            assert _load() is None, field


def test_context_cache_key_changes_with_strategy_contract() -> None:
    request = {
        "user_id": "public-owner",
        "topic": "workflow clarity",
        "category": "value",
        "audience": "tech_ai",
        "source_mode": "persona_only",
    }
    with patch.object(service, "_snapshot_hash", return_value="workspace"), patch.object(
        service,
        "_persona_context_hash",
        return_value="persona",
    ), patch.object(service, "_strategy_contract_hash", side_effect=["contract-a", "contract-b"]):
        first_key, first_source_hash = service.build_context_cache_key(
            workspace_slug="linkedin-content-os",
            request_payload=request,
        )
        second_key, second_source_hash = service.build_context_cache_key(
            workspace_slug="linkedin-content-os",
            request_payload=request,
        )

    assert first_key != second_key
    assert first_source_hash != second_source_hash


def test_context_cache_key_changes_with_persona_context() -> None:
    request = {
        "user_id": "public-owner",
        "topic": "workflow clarity",
        "category": "value",
        "audience": "tech_ai",
        "source_mode": "persona_only",
    }
    with patch.object(service, "_snapshot_hash", return_value="workspace"), patch.object(
        service,
        "_strategy_contract_hash",
        return_value="contract",
    ), patch.object(service, "_persona_context_hash", side_effect=["persona-a", "persona-b"]):
        first_key, _ = service.build_context_cache_key(
            workspace_slug="linkedin-content-os",
            request_payload=request,
        )
        second_key, _ = service.build_context_cache_key(
            workspace_slug="linkedin-content-os",
            request_payload=request,
        )

    assert first_key != second_key


def test_context_cache_key_changes_with_generation_classification() -> None:
    base_request = {
        "user_id": "public-owner",
        "topic": "workflow clarity",
        "category": "value",
        "audience": "tech_ai",
        "source_mode": "persona_only",
        "employer_safety": "pass",
    }
    with patch.object(service, "_snapshot_hash", return_value="workspace"), patch.object(
        service,
        "_strategy_contract_hash",
        return_value="contract",
    ), patch.object(service, "_persona_context_hash", return_value="persona"):
        first_key, _ = service.build_context_cache_key(
            workspace_slug="linkedin-content-os",
            request_payload=base_request,
        )
        second_key, _ = service.build_context_cache_key(
            workspace_slug="linkedin-content-os",
            request_payload={**base_request, "employer_safety": "owner_review_required"},
        )

    assert first_key != second_key


def test_snapshot_hash_includes_privacy_safe_portfolio_performance_learning() -> None:
    snapshots = {
        "source_assets": {"count": 1},
        "publication_performance_summary": {
            "schema_version": "linkedin_publication_summary/v1",
            "workspace_key": "feezie-os",
            "counts": {"owner_decisions": 10, "confirmed_publications": 6},
            "learning_gate": {"state": "advisory_ready"},
        },
    }

    calls: list[tuple[str, str]] = []

    def read_snapshot(workspace: str, snapshot_type: str):
        calls.append((workspace, snapshot_type))
        return snapshots.get(snapshot_type)

    with patch.object(service, "get_snapshot_payload", side_effect=read_snapshot):
        first = service._snapshot_hash("linkedin-content-os")
        snapshots["publication_performance_summary"]["counts"]["confirmed_publications"] = 7
        second = service._snapshot_hash("linkedin-content-os")

    assert "publication_performance_summary" in service._SNAPSHOT_TYPES
    assert ("feezie-os", "publication_performance_summary") in calls
    assert first != second
