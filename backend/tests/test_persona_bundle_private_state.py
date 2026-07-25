from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import persona_bundle_context_service, persona_bundle_writer


CLAIMS_HEADER = """---
title: "Claims"
persona_id: "johnnie_fields"
target_file: "identity/claims.md"
---

| Claim | Type | Evidence | Usage rule |
| --- | --- | --- | --- |
"""


def _claims_file(claim: str) -> str:
    return (
        CLAIMS_HEADER
        + f"| {claim} | philosophical | Owner-approved evidence. | Safe for operator writing. |\n"
    )


def _promotion(content: str, item_id: str) -> dict[str, str]:
    return {
        "id": item_id,
        "kind": "talking_point",
        "label": "Claim",
        "content": content,
        "evidence": "Explicitly selected by the owner.",
        "target_file": "identity/claims.md",
        "trait": "Owner-approved canon",
    }


class PersonaBundlePrivateStateTests(unittest.TestCase):
    def test_seed_is_copied_once_and_future_writes_leave_project_bytes_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "private-state"
            seed_root = project_root / "knowledge" / "persona" / "feeze"
            claims_path = seed_root / "identity" / "claims.md"
            claims_path.parent.mkdir(parents=True)
            claims_path.write_text(
                _claims_file("The tracked seed remains immutable."),
                encoding="utf-8",
            )
            (seed_root / "manifest.json").write_text("{}", encoding="utf-8")
            before_bytes = claims_path.read_bytes()
            before_digest = hashlib.sha256(before_bytes).hexdigest()

            with (
                patch.dict("os.environ", {"AI_CLONE_STATE_ROOT": str(state_root)}),
                patch.object(
                    persona_bundle_writer,
                    "resolve_workspace_root",
                    return_value=project_root,
                ),
            ):
                first = persona_bundle_writer.write_promotion_items_to_bundle(
                    [_promotion("The first private promotion is durable.", "private-1")]
                )
                second = persona_bundle_writer.write_promotion_items_to_bundle(
                    [_promotion("The second private promotion is durable.", "private-2")]
                )

            overlay_path = state_root / "persona" / "canonical" / "identity" / "claims.md"
            overlay_text = overlay_path.read_text(encoding="utf-8")
            self.assertEqual(first["bundle_storage"], "private_local_state")
            self.assertEqual(second["bundle_storage"], "private_local_state")
            self.assertEqual(overlay_text.count("The tracked seed remains immutable."), 1)
            self.assertIn("The first private promotion is durable.", overlay_text)
            self.assertIn("The second private promotion is durable.", overlay_text)
            self.assertEqual(claims_path.read_bytes(), before_bytes)
            self.assertEqual(hashlib.sha256(claims_path.read_bytes()).hexdigest(), before_digest)

    def test_context_prefers_private_file_and_uses_tracked_seed_for_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            seed_root = root / "seed"
            state_root = root / "state" / "persona" / "canonical"
            (seed_root / "identity").mkdir(parents=True)
            (state_root / "identity").mkdir(parents=True)
            (seed_root / "identity" / "claims.md").write_text(
                _claims_file("The tracked claim should be shadowed."),
                encoding="utf-8",
            )
            (state_root / "identity" / "claims.md").write_text(
                _claims_file("The private overlay is the current canon."),
                encoding="utf-8",
            )
            (seed_root / "identity" / "philosophy.md").write_text(
                "# Philosophy\n\n## Core Beliefs\n- The tracked philosophy remains a public fallback.\n",
                encoding="utf-8",
            )

            with (
                patch.object(
                    persona_bundle_context_service,
                    "resolve_persona_bundle_root",
                    return_value=seed_root,
                ),
                patch.object(
                    persona_bundle_context_service,
                    "resolve_persona_bundle_state_root",
                    return_value=state_root,
                ),
            ):
                chunks = persona_bundle_context_service.load_bundle_persona_chunks()

            text = " ".join(str(chunk.get("chunk") or "") for chunk in chunks)
            self.assertIn("The private overlay is the current canon.", text)
            self.assertNotIn("The tracked claim should be shadowed.", text)
            self.assertIn("The tracked philosophy remains a public fallback.", text)

    def test_private_overlay_rejects_symlinked_path_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "private-state"
            outside = root / "outside"
            seed_root = project_root / "knowledge" / "persona" / "feeze"
            seed_root.mkdir(parents=True)
            (seed_root / "manifest.json").write_text("{}", encoding="utf-8")
            outside.mkdir()
            state_root.mkdir()
            (state_root / "persona").symlink_to(outside, target_is_directory=True)

            with (
                patch.dict("os.environ", {"AI_CLONE_STATE_ROOT": str(state_root)}),
                patch.object(
                    persona_bundle_writer,
                    "resolve_workspace_root",
                    return_value=project_root,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "cannot contain symlinks"):
                    persona_bundle_writer.write_promotion_items_to_bundle(
                        [_promotion("This must not escape private state.", "unsafe-1")]
                    )

            self.assertEqual(list(outside.iterdir()), [])

    def test_private_overlay_rejects_symlinked_configured_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "project"
            state_root = root / "private-state-link"
            outside = root / "outside"
            seed_root = project_root / "knowledge" / "persona" / "feeze"
            seed_root.mkdir(parents=True)
            (seed_root / "manifest.json").write_text("{}", encoding="utf-8")
            outside.mkdir()
            state_root.symlink_to(outside, target_is_directory=True)

            with (
                patch.dict("os.environ", {"AI_CLONE_STATE_ROOT": str(state_root)}),
                patch.object(
                    persona_bundle_writer,
                    "resolve_workspace_root",
                    return_value=project_root,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "cannot contain symlinks"):
                    persona_bundle_writer.write_promotion_items_to_bundle(
                        [_promotion("The configured root must not be followed.", "unsafe-root")]
                    )

            self.assertEqual(list(outside.iterdir()), [])

    def test_context_rejects_symlinked_parent_in_private_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            seed_root = root / "seed"
            state_root = root / "state" / "persona" / "canonical"
            outside = root / "outside"
            seed_root.mkdir()
            state_root.mkdir(parents=True)
            outside.mkdir()
            (outside / "claims.md").write_text(
                _claims_file("Escaped private content must never be read."),
                encoding="utf-8",
            )
            (state_root / "identity").symlink_to(outside, target_is_directory=True)

            with (
                patch.object(
                    persona_bundle_context_service,
                    "resolve_persona_bundle_root",
                    return_value=seed_root,
                ),
                patch.object(
                    persona_bundle_context_service,
                    "resolve_persona_bundle_state_root",
                    return_value=state_root,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "cannot contain symlinks"):
                    persona_bundle_context_service.load_bundle_persona_chunks()


if __name__ == "__main__":
    unittest.main()
