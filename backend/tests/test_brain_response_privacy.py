from __future__ import annotations

import asyncio
import importlib
import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import Response


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import brain_docs_service, portfolio_workspace_snapshot_service  # noqa: E402
from app.services.brain_response_privacy_service import sanitize_brain_payload, sanitize_brain_text  # noqa: E402


brain_docs_routes = importlib.import_module("app.routes.brain_docs")
brain_routes = importlib.import_module("app.routes.brain")


FORBIDDEN_MARKERS = (
    "/Users/",
    ".openclaw",
    ".codex",
    "CONTROL_PLANE_SERVICE_TOKEN",
    "CONTROL_PLANE_JOB_SIGNING_SECRET",
    "CONTROL_PLANE_PASSWORD",
    "LOCAL_CODEX_BRIDGE_TOKEN",
    "OPENAI_API_KEY",
    "/home/",
    "/app/",
    "/usr/",
)


def _assert_brain_safe(payload: object) -> str:
    serialized = json.dumps(payload, default=str)
    lowered = serialized.lower()
    for marker in FORBIDDEN_MARKERS:
        lowered_marker = marker.lower()
        if lowered_marker.startswith("/"):
            assert re.search(rf"(?<![a-z0-9]){re.escape(lowered_marker)}", lowered) is None
        else:
            assert lowered_marker not in lowered
    return serialized


def test_text_sanitizer_preserves_relative_artifact_context() -> None:
    leaked = (
        "When a real partner or buyer route appears, update "
        "`/Users/neo/.openclaw/workspace/workspaces/agc/analytics/inbound_email_log.csv` first, then "
        "`/Users/neo/Documents/Codex/AI-Clone/workspaces/agc/analytics/opportunity_ledger.csv`. "
        "CONTROL_PLANE_SERVICE_TOKEN=super-secret and OPENAI_API_KEY are private."
    )

    sanitized = sanitize_brain_text(leaked)

    _assert_brain_safe(sanitized)
    assert "workspaces/agc/analytics/inbound_email_log.csv" in sanitized
    assert "workspaces/agc/analytics/opportunity_ledger.csv" in sanitized
    assert "super-secret" not in sanitized
    assert "[credential]=[redacted]" in sanitized


def test_text_sanitizer_does_not_mangle_normal_token_prose() -> None:
    prose = "Model API tokens are not required for local Codex execution; the token budget remains visible."

    assert sanitize_brain_text(prose) == prose
    assert "CONTROL_PLANE_PASSWORD" not in sanitize_brain_text("CONTROL_PLANE_PASSWORD is private")
    assert "LOCAL_CODEX_BRIDGE_TOKEN" not in sanitize_brain_text("LOCAL_CODEX_BRIDGE_TOKEN is private")


def test_recursive_sanitizer_handles_keys_values_hidden_runtime_and_token_shapes() -> None:
    payload = {
        "CONTROL_PLANE_JOB_SIGNING_SECRET": "top-secret",
        "nested": {
            "tail": (
                "Read ~/.codex/ai-clone/secrets/control_plane.env, /Users/neo/dev/work-life-tools, "
                "/home/runner/work/AI-Clone/backend/app/main.py, and /app/backend/workspaces/agc/docs/plan.md. "
                "The retired roots .openclaw and .codex must stay hidden; /usr/local/bin/python3 is local. "
                "CONTROL_PLANE_PASSWORD=hunter2 LOCAL_CODEX_BRIDGE_TOKEN=bridge-secret"
            ),
            "provider": "Bearer abcdefghijklmnopqrstuvwxyz123456",
        },
    }

    sanitized = sanitize_brain_payload(payload)
    serialized = _assert_brain_safe(sanitized)

    assert "top-secret" not in serialized
    assert "hunter2" not in serialized
    assert "bridge-secret" not in serialized
    assert "abcdefghijklmnopqrstuvwxyz123456" not in serialized
    assert "[private-runtime]" in serialized
    assert "[local-path]/work-life-tools" in serialized
    assert "backend/app/main.py" in serialized
    assert "backend/workspaces/agc/docs/plan.md" in serialized
    assert "[retired-runtime]" in serialized
    assert "[local-runtime]" in serialized
    assert "[local-path]/python3" in serialized


def test_portfolio_execution_log_tail_is_sanitized_at_the_snapshot_boundary() -> None:
    with TemporaryDirectory() as temporary_dir:
        repo_root = Path(temporary_dir)
        workspace_root = repo_root / "workspaces" / "agc"
        (workspace_root / "memory").mkdir(parents=True)
        (workspace_root / "memory" / "execution_log.md").write_text(
            "# Log\n\n"
            "### Follow-ups\n"
            "- When a real partner or buyer route appears, update "
            "`/Users/neo/.openclaw/workspace/workspaces/agc/analytics/inbound_email_log.csv` first.\n"
            "- Local proof lives at `/Users/neo/Documents/Codex/AI-Clone/workspaces/agc/memory/execution_log.md`.\n"
            "- Never return CONTROL_PLANE_SERVICE_TOKEN or OPENAI_API_KEY=secret-provider-value.\n",
            encoding="utf-8",
        )
        entry = {
            "key": "agc",
            "kind": "workspace",
            "display_name": "AGC",
            "workspace_root": "agc",
            "status": "live",
            "priority_order": 1,
            "portfolio_visible": True,
        }

        with patch.object(portfolio_workspace_snapshot_service, "workspace_registry_entries", return_value=(entry,)), patch.object(
            portfolio_workspace_snapshot_service,
            "workspace_root_path",
            return_value=workspace_root,
        ), patch.object(portfolio_workspace_snapshot_service, "workspace_root_slug", return_value="agc"), patch.object(
            portfolio_workspace_snapshot_service.pm_card_service,
            "list_cards",
            return_value=[],
        ), patch.object(
            portfolio_workspace_snapshot_service.standup_service,
            "list_standups",
            return_value=[],
        ), patch.object(portfolio_workspace_snapshot_service, "list_snapshot_payloads", return_value={}):
            snapshot = portfolio_workspace_snapshot_service.build_portfolio_workspace_snapshot()

    serialized = _assert_brain_safe(snapshot)
    workspace = snapshot["workspaces"][0]
    assert workspace["execution_log"]["path"] == "workspaces/agc/memory/execution_log.md"
    assert "workspaces/agc/analytics/inbound_email_log.csv" in workspace["execution_log"]["tail"]
    assert "secret-provider-value" not in serialized


def test_brain_bounded_read_applies_privacy_filter_to_every_read_payload() -> None:
    leaked = {
        "snippet": "/Users/neo/.openclaw/workspace/workspaces/agc/docs/plan.md",
        "credential": "CONTROL_PLANE_SERVICE_TOKEN",
    }

    payload = asyncio.run(
        brain_routes._run_bounded_read(
            lambda: leaked,
            timeout_seconds=1.0,
            label="privacy test",
        )
    )

    _assert_brain_safe(payload)
    assert payload["snippet"] == "workspaces/agc/docs/plan.md"


def test_brain_docs_index_and_content_sanitize_local_paths_and_credentials() -> None:
    with TemporaryDirectory() as temporary_dir:
        root = Path(temporary_dir)
        (root / "CODEX_STARTUP.md").write_text(
            "# Startup at /Users/neo/Documents/Codex/AI-Clone/workspaces/shared-ops\n\n"
            "Project root: `/Users/neo/Documents/Codex/AI-Clone`.\n"
            "Runtime root: `/Users/neo/.codex/ai-clone`.\n"
            "Retired file: `/Users/neo/.openclaw/workspace/workspaces/agc/docs/plan.md`.\n"
            "Secrets: `/Users/neo/.codex/ai-clone/secrets/control_plane.env`, "
            "CONTROL_PLANE_JOB_SIGNING_SECRET, and OPENAI_API_KEY=provider-secret.\n"
            "Stable anchor: `workspaces/agc/docs/plan.md`.\n",
            encoding="utf-8",
        )

        with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
            index_payload = brain_docs_service.list_brain_docs()
            content_payload = brain_docs_service.read_brain_doc("CODEX_STARTUP.md")

    _assert_brain_safe(index_payload)
    serialized_content = _assert_brain_safe(content_payload)
    assert "provider-secret" not in serialized_content
    assert "workspaces/agc/docs/plan.md" in (content_payload or {}).get("content", "")
    assert "[project-root]" in (content_payload or {}).get("content", "")
    assert "[private-runtime]" in (content_payload or {}).get("content", "")


def test_brain_docs_routes_enforce_privacy_even_for_unsanitized_service_results() -> None:
    index_leak = {
        "docs": [
            {
                "path": "docs/example.md",
                "snippet": "/Users/neo/.openclaw/workspace/workspaces/agc/docs/plan.md CONTROL_PLANE_SERVICE_TOKEN",
            }
        ]
    }
    content_leak = {
        "path": "docs/example.md",
        "content": "/Users/neo/.codex/ai-clone/secrets/control_plane.env OPENAI_API_KEY=provider-secret",
    }

    with patch.object(brain_docs_routes, "list_brain_docs", return_value=index_leak):
        index_payload = asyncio.run(brain_docs_routes.get_brain_docs(Response()))
    with patch.object(brain_docs_routes, "read_brain_doc", return_value=content_leak):
        content_payload = asyncio.run(brain_docs_routes.get_brain_doc_content(Response(), path="docs/example.md"))

    _assert_brain_safe(index_payload)
    serialized_content = _assert_brain_safe(content_payload)
    assert index_payload["docs"][0]["snippet"].startswith("workspaces/agc/docs/plan.md")
    assert "provider-secret" not in serialized_content
