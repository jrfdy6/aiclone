from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.services import brain_docs_service  # noqa: E402


brain_docs_route = importlib.import_module("app.routes.brain_docs")


class BrainDocsServiceTests(unittest.TestCase):
    def test_canonical_read_order_starts_with_source_of_truth_and_labels_authority(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            (root / "memory").mkdir()
            (root / "SOPs").mkdir()
            for relative_path in (
                "SOURCE_OF_TRUTH.md",
                "CODEX_STARTUP.md",
                "AGENTS.md",
                "MEMORY.md",
                "memory/persistent_state.md",
                "memory/roadmap.md",
                "SOPs/_index.md",
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {path.stem}\n", encoding="utf-8")

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                payload = brain_docs_service.list_brain_docs()

            paths = [item["path"] for item in payload["docs"]]
            self.assertEqual(paths[:3], ["SOURCE_OF_TRUTH.md", "CODEX_STARTUP.md", "AGENTS.md"])
            docs = {item["path"]: item for item in payload["docs"]}
            self.assertEqual(payload["authority_path"], "SOURCE_OF_TRUTH.md")
            self.assertEqual(docs["SOURCE_OF_TRUTH.md"]["authority"], "binding")
            self.assertEqual(docs["memory/roadmap.md"]["status"], "directional")
            self.assertEqual(docs["SOURCE_OF_TRUTH.md"]["readOrder"], 0)

    def test_latest_daily_log_excludes_literal_template_name(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            memory = root / "memory"
            memory.mkdir()
            (memory / "2026-07-19.md").write_text("# Real daily log\n", encoding="utf-8")
            (memory / "YYYY-MM-DD.md").write_text("# Template\n", encoding="utf-8")

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                payload = brain_docs_service.list_brain_docs()

            paths = {item["path"] for item in payload["docs"]}
            self.assertIn("memory/2026-07-19.md", paths)
            self.assertNotIn("memory/YYYY-MM-DD.md", paths)

    def test_index_is_metadata_only_and_deployed_memory_keeps_logical_path(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            (root / "docs").mkdir()
            (root / "docs" / "architecture.md").write_text("# Architecture\nPrivate body", encoding="utf-8")
            (root / "memory" / "runtime").mkdir(parents=True)
            (root / "memory" / "runtime" / "persistent_state.md").write_text("# Current state\nRuntime truth", encoding="utf-8")

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                payload = brain_docs_service.list_brain_docs()
                shared_count = brain_docs_service.count_brain_docs()

            docs = {item["path"]: item for item in payload["docs"]}
            self.assertEqual(shared_count, payload["count"])
            self.assertIn("docs/architecture.md", docs)
            self.assertIn("memory/persistent_state.md", docs)
            self.assertNotIn("content", docs["docs/architecture.md"])
            self.assertNotIn(str(root), str(payload))
            self.assertEqual(docs["memory/persistent_state.md"]["readMode"], "deployed_snapshot")
            self.assertEqual(docs["memory/persistent_state.md"]["resolvedPath"], "memory/runtime/persistent_state.md")

    def test_index_never_serializes_jsonl_content_and_sanitizes_markdown_snippets(self) -> None:
        sentinel = "SENTINEL_PRIVATE_VALUE_7f9a"
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            (root / "docs").mkdir()
            long_heading = "**A title** with [a link](https://private.example/path) " + ("x" * 400)
            (root / "docs" / "long-title.md").write_text(
                "# " + long_heading + "\n" + sentinel + "\n",
                encoding="utf-8",
            )
            (root / "memory" / "runtime").mkdir(parents=True)
            (root / "memory" / "runtime" / "codex_session_handoff.jsonl").write_text(
                json.dumps({"secret": sentinel}) + "\n",
                encoding="utf-8",
            )

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                payload = brain_docs_service.list_brain_docs()

            serialized = json.dumps(payload)
            docs = {item["path"]: item for item in payload["docs"]}
            markdown = docs["docs/long-title.md"]
            jsonl = docs["memory/codex_session_handoff.jsonl"]

            self.assertNotIn(sentinel, serialized)
            self.assertNotIn("content", serialized)
            self.assertTrue(markdown["snippet"].startswith("A title with a link "))
            self.assertEqual(len(markdown["snippet"]), brain_docs_service.MAX_MARKDOWN_SNIPPET_CHARS)
            self.assertNotIn("\n", markdown["snippet"])
            self.assertNotIn("snippet", jsonl)

    def test_default_index_excludes_runtime_snapshots_and_retired_openclaw_material(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            (root / "docs" / "runtime_snapshots").mkdir(parents=True)
            (root / "docs" / "runtime_snapshots" / "memory.md").write_text("# Old snapshot", encoding="utf-8")
            (root / "docs" / "openclaw_runtime_backup.md").write_text("# Retired", encoding="utf-8")
            (root / "docs" / "qmd_migration.md").write_text("# Retired QMD", encoding="utf-8")
            (root / "docs" / "current.md").write_text("# Current", encoding="utf-8")

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                payload = brain_docs_service.list_brain_docs()

            paths = {item["path"] for item in payload["docs"]}
            self.assertIn("docs/current.md", paths)
            self.assertNotIn("docs/runtime_snapshots/memory.md", paths)
            self.assertNotIn("docs/openclaw_runtime_backup.md", paths)
            self.assertNotIn("docs/qmd_migration.md", paths)

    def test_content_reads_only_an_indexed_allowlisted_document(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir) / "repo"
            root.mkdir()
            (root / "SOPs").mkdir()
            (root / "SOPs" / "safe.md").write_text("# Safe\nAllowed content", encoding="utf-8")
            outside = root.parent / "outside.md"
            outside.write_text("secret", encoding="utf-8")

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                doc = brain_docs_service.read_brain_doc("SOPs/safe.md")
                self.assertIsNotNone(doc)
                self.assertEqual((doc or {}).get("content"), "# Safe\nAllowed content")
                with self.assertRaises(ValueError):
                    brain_docs_service.read_brain_doc("../outside.md")

    def test_large_jsonl_returns_a_bounded_tail_preview(self) -> None:
        with TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            runtime = root / "memory" / "runtime"
            runtime.mkdir(parents=True)
            rows = ['{{"row":{},"value":"{}"}}'.format(index, "x" * 80) for index in range(7_000)]
            (runtime / "codex_session_handoff.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")

            with patch.object(brain_docs_service, "WORKSPACE_ROOT", root):
                doc = brain_docs_service.read_brain_doc("memory/codex_session_handoff.jsonl")

            self.assertIsNotNone(doc)
            self.assertTrue((doc or {}).get("truncated"))
            self.assertIn("showing the latest", (doc or {}).get("content", ""))
            self.assertIn('"row":6999', (doc or {}).get("content", ""))
            self.assertNotIn('"row":0', (doc or {}).get("content", ""))


class BrainDocsRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_docs_index_route(self) -> None:
        payload = {"schema_version": "brain_docs_index/v1", "count": 1, "groups": {"System Docs": 1}, "docs": []}
        with patch.object(brain_docs_route, "list_brain_docs", return_value=payload):
            response = self.client.get("/api/brain/docs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.headers.get("cache-control"), "no-store, max-age=0")

    def test_docs_content_route_hides_unknown_paths(self) -> None:
        with patch.object(brain_docs_route, "read_brain_doc", return_value=None):
            response = self.client.get("/api/brain/docs/content", params={"path": "docs/missing.md"})
        self.assertEqual(response.status_code, 404)

    def test_docs_routes_do_not_expose_internal_exception_details(self) -> None:
        secret_path = "/private/runtime/secrets/control_plane.env"
        with patch.object(brain_docs_route, "list_brain_docs", side_effect=RuntimeError(secret_path)):
            index_response = self.client.get("/api/brain/docs")
        with patch.object(brain_docs_route, "read_brain_doc", side_effect=RuntimeError(secret_path)):
            content_response = self.client.get("/api/brain/docs/content", params={"path": "docs/current.md"})

        self.assertEqual(index_response.status_code, 500)
        self.assertEqual(content_response.status_code, 500)
        self.assertNotIn(secret_path, index_response.text)
        self.assertNotIn(secret_path, content_response.text)


if __name__ == "__main__":
    unittest.main()
