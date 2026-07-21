from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_documentation_truth.py"
SPEC = importlib.util.spec_from_file_location("verify_documentation_truth", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_valid_repository(root: Path) -> None:
    _write(
        root,
        "SOURCE_OF_TRUTH.md",
        "# Source of Truth\n\n## Mandatory read order\n\n1. [SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md)\n",
    )
    _write(
        root,
        "CODEX_STARTUP.md",
        "# Startup\n\n## First read order\n\n1. [SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md)\n",
    )
    _write(
        root,
        "AGENTS.md",
        "# Agents\n\n## Startup snapshot\n\n1. Read [SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md) first.\n",
    )
    for path in ("IDENTITY.md", "CHARTER.md", "SOUL.md", "USER.md", "memory/persistent_state.md"):
        _write(root, path, f"# {Path(path).stem}\n")

    _write(root, "README.md", "# Project\n\nCurrent authority: [SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md).\n")
    for path in verifier.SOURCE_BACKLINK_FILES:
        if path in {"README.md", "MEMORY.md", "memory/roadmap.md"}:
            continue
        depth = len(Path(path).parent.parts)
        source_target = "../" * depth + "SOURCE_OF_TRUTH.md" if depth else "./SOURCE_OF_TRUTH.md"
        _write(root, path, f"# {Path(path).stem}\n\nSubordinate to [SOURCE_OF_TRUTH.md]({source_target}).\n")
    _write(
        root,
        "MEMORY.md",
        "# Memory\n\nSubordinate to [SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md).\n\n"
        "[Authority section](./SOURCE_OF_TRUTH.md?view=docs#documentation-authority)\n",
    )
    _write(root, "memory/roadmap.md", "# Roadmap\n\nSubordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md).\n")
    _write(
        root,
        "SOPs/_index.md",
        "# SOP Index\n\nAuthority: [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md).\n\n"
        "- [Example procedure](./example_sop.md)\n",
    )
    _write(
        root,
        "SOPs/example_sop.md",
        "# Example\n\nAuthority: [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md).\n\n"
        "Registry: [SOP Index](./_index.md).\n",
    )
    _write(
        root,
        "projects/example_roadmap.md",
        "# Example roadmap\n\nSubordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) "
        "and [memory/roadmap.md](../memory/roadmap.md).\n",
    )
    for path in verifier.KEY_ARCHITECTURE_DOCS:
        _write(root, path, "# Architecture\n\nAuthority: [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md).\n")


class DocumentationTruthVerifierTests(unittest.TestCase):
    def test_valid_document_graph_emits_compact_json_and_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _build_valid_repository(root)

            report = verifier.verify_documentation_truth(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["defects"], [])

            output = io.StringIO()
            with redirect_stdout(output):
                status = verifier.main(["--root", str(root)])
            self.assertEqual(status, 0)
            self.assertEqual(output.getvalue().count("\n"), 1)
            self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_reports_required_order_backlink_claim_and_broken_link_defects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _build_valid_repository(root)
            (root / "USER.md").unlink()
            _write(
                root,
                "CODEX_STARTUP.md",
                "# Startup\n\n## First read order\n\n"
                "1. [CODEX_STARTUP.md](./CODEX_STARTUP.md), then [SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md).\n",
            )
            _write(
                root,
                "README.md",
                "# Project\n\n[SOURCE_OF_TRUTH.md](./SOURCE_OF_TRUTH.md) exists, "
                "but this README is the **canonical** source.\n",
            )
            _write(root, "SOPs/example_sop.md", "# Example\n\n[Missing](./does-not-exist.md)\n")

            report = verifier.verify_documentation_truth(root)
            codes = {defect["code"] for defect in report["defects"]}

            self.assertFalse(report["ok"])
            self.assertIn("missing_required_file", codes)
            self.assertIn("source_of_truth_not_first", codes)
            self.assertIn("missing_source_of_truth_backlink", codes)
            self.assertIn("missing_sop_index_backlink", codes)
            self.assertIn("readme_claims_canonical", codes)
            self.assertIn("broken_local_markdown_link", codes)

    def test_reports_project_roadmap_without_portfolio_backlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _build_valid_repository(root)
            _write(
                root,
                "projects/example_roadmap.md",
                "# Example roadmap\n\nSubordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md).\n",
            )

            report = verifier.verify_documentation_truth(root)

            self.assertIn("missing_portfolio_roadmap_backlink", {defect["code"] for defect in report["defects"]})

            output = io.StringIO()
            with redirect_stdout(output):
                status = verifier.main(["--root", str(root)])
            self.assertEqual(status, 1)
            self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_ignores_web_and_code_examples_but_rejects_absolute_and_traversal_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _build_valid_repository(root)
            _write(
                root,
                "MEMORY.md",
                "# Memory\n\n"
                "[Authority](./SOURCE_OF_TRUTH.md)\n"
                "[External](https://example.com/docs) [Anchor](#notes) [App route](/ops)\n"
                "`[Inline example](./missing-inline.md)`\n"
                "```markdown\n[Fenced example](./missing-fenced.md)\n```\n"
                "[Absolute](/Users/example/AI-Clone/MEMORY.md)\n"
                "[Traversal](../../outside.md)\n",
            )

            report = verifier.verify_documentation_truth(root)
            by_code = {defect["code"]: defect for defect in report["defects"]}

            self.assertIn("absolute_local_markdown_link", by_code)
            self.assertIn("local_markdown_link_outside_root", by_code)
            targets = {str(defect.get("target") or "") for defect in report["defects"]}
            self.assertNotIn("./missing-inline.md", targets)
            self.assertNotIn("./missing-fenced.md", targets)


if __name__ == "__main__":
    unittest.main()
