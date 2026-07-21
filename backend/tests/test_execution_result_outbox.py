from __future__ import annotations

import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNERS_ROOT = ROOT / "scripts" / "runners"
SCRIPTS_ROOT = ROOT / "scripts"
for import_root in (RUNNERS_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.models import PMCard, PMExecutionResultCommitRequest, PMExecutionResultCommitResult
import execution_result_outbox as outbox


PRODUCTION_API_URL = "https://aiclone-production-32dc.up.railway.app"


def _operation(tmp_path: Path) -> PMExecutionResultCommitRequest:
    card_id, claim_id, result_id = uuid4(), uuid4(), uuid4()
    return PMExecutionResultCommitRequest(
        card_id=card_id,
        claim_id=claim_id,
        worker_id="mac-runner",
        result_id=result_id,
        runner_id="brain-local-action",
        author_agent="Brain Local Action",
        created_at=datetime.now(timezone.utc),
        workspace_key="shared_ops",
        title="Finish a deterministic action",
        status="done",
        summary="The deterministic action completed.",
        decisions=["Keep the narrow result contract."],
        outcomes=["The requested local effect is present."],
        artifacts=[
            str(tmp_path / "result.json"),
            str(tmp_path / "result.md"),
            str(tmp_path / "work-order.json"),
        ],
        result_path=str(tmp_path / "result.json"),
        memo_path=str(tmp_path / "result.md"),
        work_order_path=str(tmp_path / "work-order.json"),
    )


def _response(operation: PMExecutionResultCommitRequest) -> PMExecutionResultCommitResult:
    now = datetime.now(timezone.utc)
    return PMExecutionResultCommitResult(
        card=PMCard(
            id=str(operation.card_id),
            title=operation.title,
            status="done",
            payload={"execution": {"state": "done"}},
            created_at=now,
            updated_at=now,
        ),
        disposition="committed",
    )


@pytest.fixture(autouse=True)
def _outbox_secret(monkeypatch):
    monkeypatch.setattr(outbox, "runtime_secret_value", lambda *_args, **_kwargs: "test-only-secret")


def test_prepare_uses_private_signed_file_without_transport_credentials(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"

    path = outbox.prepare_outbox_entry(operation, root=root)
    loaded = outbox.load_outbox_entry(path, root=root)
    serialized = json.loads(path.read_text(encoding="utf-8"))

    assert loaded.state == "prepared"
    assert loaded.operation.result_id == operation.result_id
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "api_url" not in serialized
    assert "token" not in path.read_text(encoding="utf-8").lower()
    assert "payload" not in serialized["operation"]
    assert serialized["authorization"]["algorithm"] == "hmac-sha256"


def test_tampered_outbox_entry_fails_closed(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"
    path = outbox.prepare_outbox_entry(operation, root=root)
    serialized = json.loads(path.read_text(encoding="utf-8"))
    serialized["operation"]["summary"] = "Tampered after signing"
    path.write_text(json.dumps(serialized), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(outbox.ExecutionResultOutboxSecurityError, match="signature"):
        outbox.load_outbox_entry(path, root=root)


def test_reconcile_archives_materialized_entry_idempotently(monkeypatch, tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"
    path = outbox.prepare_outbox_entry(operation, root=root)
    outbox.mark_outbox_materialized(path, root=root)
    monkeypatch.setattr(outbox, "_commit_request", lambda value, **_kwargs: _response(value))

    response = outbox.reconcile_outbox_entry(path, api_url=PRODUCTION_API_URL, root=root)

    archive_path = root / "archive" / path.name
    assert response.disposition == "committed"
    assert not path.exists()
    assert archive_path.exists()
    assert stat.S_IMODE(archive_path.stat().st_mode) == 0o600
    archived = outbox._load_unlocked(archive_path)
    assert archived.state == "committed"
    assert archived.operation.result_id == operation.result_id


def test_flush_replays_prepared_materialization_before_commit(monkeypatch, tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"
    path = outbox.prepare_outbox_entry(operation, root=root)
    events: list[str] = []

    def materialize(value: PMExecutionResultCommitRequest) -> None:
        assert value.result_id == operation.result_id
        events.append("materialize")

    def commit(value: PMExecutionResultCommitRequest, **_kwargs) -> PMExecutionResultCommitResult:
        events.append("commit")
        return _response(value)

    monkeypatch.setattr(outbox, "_commit_request", commit)
    report = outbox.flush_pending_outbox(
        api_url=PRODUCTION_API_URL,
        materialize=materialize,
        root=root,
    )

    assert report == {"processed": 1, "committed": 1, "pending": 0, "conflicts": 0, "errors": []}
    assert events == ["materialize", "commit"]
    assert not path.exists()


def test_unavailable_commit_retains_signed_materialized_entry(monkeypatch, tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"
    path = outbox.prepare_outbox_entry(operation, root=root)
    outbox.mark_outbox_materialized(path, root=root)

    def unavailable(*_args, **_kwargs):
        raise outbox.ExecutionResultOutboxUnavailable("offline")

    monkeypatch.setattr(outbox, "_commit_request", unavailable)
    with pytest.raises(outbox.ExecutionResultOutboxUnavailable):
        outbox.reconcile_outbox_entry(path, api_url=PRODUCTION_API_URL, root=root)

    retained = outbox.load_outbox_entry(path, root=root)
    assert retained.state == "materialized"
    assert retained.attempt_count == 1
    assert retained.last_error == "offline"


def test_outbox_lock_symlink_fails_closed_without_touching_target(tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"
    root.mkdir(mode=0o700)
    victim = tmp_path / "victim.txt"
    victim.write_text("do not touch\n", encoding="utf-8")
    original_mode = stat.S_IMODE(victim.stat().st_mode)
    (root / ".lock").symlink_to(victim)

    with pytest.raises(outbox.ExecutionResultOutboxSecurityError, match="lock"):
        outbox.prepare_outbox_entry(operation, root=root)

    assert victim.read_text(encoding="utf-8") == "do not touch\n"
    assert stat.S_IMODE(victim.stat().st_mode) == original_mode


def test_existing_committed_archive_completes_interrupted_archive_move(monkeypatch, tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    root = tmp_path / "private-outbox"
    path = outbox.prepare_outbox_entry(operation, root=root)
    entry = outbox.mark_outbox_materialized(path, root=root)
    committed = entry.model_copy(
        update={
            "state": "committed",
            "committed_at": datetime.now(timezone.utc),
            "disposition": "committed",
        }
    )
    archive_path = root / "archive" / path.name
    outbox._atomic_write(archive_path, outbox._signed_payload(committed))
    monkeypatch.setattr(outbox, "_commit_request", lambda value, **_kwargs: _response(value))

    response = outbox.reconcile_outbox_entry(path, api_url=PRODUCTION_API_URL, root=root)

    assert response.disposition == "committed"
    assert not path.exists()
    assert archive_path.exists()


def test_api_allowlist_rejects_arbitrary_https_before_auth_headers(monkeypatch, tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    header_calls: list[dict] = []
    monkeypatch.setattr(outbox, "control_plane_headers", lambda value: header_calls.append(value) or value)

    with pytest.raises(outbox.ExecutionResultOutboxSecurityError, match="allowlisted"):
        outbox._commit_request(operation, api_url="https://evil.example")

    assert header_calls == []


def test_commit_rejects_redirect_without_forwarding_authorization(monkeypatch, tmp_path: Path) -> None:
    operation = _operation(tmp_path)
    opened_requests = []
    installed_handlers = []
    runtime_globals = outbox.open_control_plane_request.__globals__

    class RedirectingOpener:
        def open(self, request, *, timeout):
            opened_requests.append(request)
            raise outbox.urllib.error.HTTPError(
                request.full_url,
                302,
                "Found",
                {"Location": "https://evil.example/collect"},
                None,
            )

    def build_opener(*handlers):
        installed_handlers.extend(handlers)
        return RedirectingOpener()

    monkeypatch.setattr(
        outbox,
        "control_plane_headers",
        lambda value: {**value, "Authorization": "Bearer must-not-leave-production-host"},
    )
    monkeypatch.setattr(runtime_globals["urllib"].request, "build_opener", build_opener)

    with pytest.raises(outbox.ExecutionResultOutboxUnavailable, match="HTTP 302"):
        outbox._commit_request(operation, api_url=PRODUCTION_API_URL)

    assert len(opened_requests) == 1
    assert opened_requests[0].full_url.startswith(PRODUCTION_API_URL)
    assert opened_requests[0].get_header("Authorization") == "Bearer must-not-leave-production-host"
    assert len(installed_handlers) == 1
    assert isinstance(installed_handlers[0], runtime_globals["_NoRedirectHandler"])


def test_environment_outbox_override_cannot_leave_private_state_root(monkeypatch, tmp_path: Path) -> None:
    private_state = tmp_path / "private-state"
    monkeypatch.setattr(outbox, "STATE_ROOT", private_state)
    monkeypatch.setenv("AI_CLONE_EXECUTION_RESULT_OUTBOX_ROOT", str(tmp_path / "public-repo"))

    with pytest.raises(outbox.ExecutionResultOutboxSecurityError, match="AI_CLONE_STATE_ROOT"):
        outbox._outbox_root()


def test_empty_outbox_requires_hmac_secret_without_creating_runtime_directory(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "absent-private-outbox"
    monkeypatch.setattr(outbox, "runtime_secret_value", lambda *_args, **_kwargs: "")

    with pytest.raises(outbox.ExecutionResultOutboxSecurityError, match="signing is not configured"):
        outbox.flush_pending_outbox(api_url=PRODUCTION_API_URL, root=root)

    assert not root.exists()


def test_empty_outbox_rejects_untrusted_api_without_creating_runtime_directory(tmp_path: Path) -> None:
    root = tmp_path / "absent-private-outbox"

    with pytest.raises(outbox.ExecutionResultOutboxSecurityError, match="not allowlisted"):
        outbox.flush_pending_outbox(api_url="https://evil.example", root=root)

    assert not root.exists()
