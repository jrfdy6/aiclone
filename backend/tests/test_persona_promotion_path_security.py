from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import PersonaDelta  # noqa: E402
from app.models.brain import BrainPersonaRerouteRequest, PromotionItemPayload  # noqa: E402
from app.services import persona_bundle_writer, persona_promotion_service  # noqa: E402


def _promotion_item(target_file: str, *, item_id: str = "promotion-1") -> dict[str, str]:
    return {
        "id": item_id,
        "kind": "talking_point",
        "label": "Promotion",
        "content": f"Canonical content for {item_id}.",
        "target_file": target_file,
    }


class PersonaPromotionPathSecurityTests(unittest.TestCase):
    def test_request_models_accept_canonical_target(self) -> None:
        item = PromotionItemPayload(
            id="promotion-valid",
            kind="talking_point",
            label="Valid promotion",
            content="This belongs in canonical claims.",
            targetFile=" identity/claims.md ",
        )
        reroute = BrainPersonaRerouteRequest(target_file="identity/claims.md")

        self.assertEqual(item.targetFile, "identity/claims.md")
        self.assertEqual(reroute.target_file, "identity/claims.md")

    def test_request_models_reject_absolute_traversal_and_unsupported_targets(self) -> None:
        invalid_targets = (
            "/tmp/persona-escape.md",
            "../identity/claims.md",
            "identity/not-a-canonical-target.md",
        )
        for target_file in invalid_targets:
            with self.subTest(target_file=target_file):
                with self.assertRaises(ValidationError):
                    PromotionItemPayload(
                        id="promotion-invalid",
                        kind="talking_point",
                        label="Invalid promotion",
                        content="This target must be rejected.",
                        targetFile=target_file,
                    )
                with self.assertRaises(ValidationError):
                    BrainPersonaRerouteRequest(target_file=target_file)

    def test_commit_service_rejects_unsupported_target_before_update(self) -> None:
        delta = PersonaDelta(
            id="delta-unsafe-target",
            capture_id=None,
            persona_target="feeze.core",
            trait="Unsafe promotion target",
            status="approved",
            metadata={
                "pending_promotion": True,
                "selected_promotion_items": [
                    {
                        "id": "promotion-unsafe",
                        "kind": "talking_point",
                        "label": "Unsafe promotion",
                        "content": "This must not commit.",
                        "targetFile": "../outside.md",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
        )

        with (
            patch.object(persona_promotion_service.persona_delta_service, "get_delta", return_value=delta),
            patch.object(persona_promotion_service.persona_delta_service, "update_delta") as update_delta,
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported persona promotion target"):
                persona_promotion_service.promote_delta_to_canon(delta.id)

        update_delta.assert_not_called()

    def test_writer_rejects_absolute_traversal_and_unsupported_targets_before_scaffolding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            bundle_root = temp_root / "knowledge" / "persona" / "feeze"
            absolute_target = temp_root / "absolute-escape.md"
            invalid_targets = (
                str(absolute_target),
                "../traversal-escape.md",
                "identity/not-a-canonical-target.md",
            )

            with (
                patch.object(persona_bundle_writer, "resolve_workspace_root", return_value=temp_root),
                patch.object(persona_bundle_writer, "resolve_persona_bundle_write_root", return_value=bundle_root),
            ):
                for target_file in invalid_targets:
                    with self.subTest(target_file=target_file):
                        with self.assertRaisesRegex(ValueError, "Unsupported persona promotion target"):
                            persona_bundle_writer.write_promotion_items_to_bundle(
                                [_promotion_item(target_file)]
                            )

            self.assertFalse(bundle_root.exists())
            self.assertFalse(absolute_target.exists())
            self.assertFalse((temp_root / "traversal-escape.md").exists())

    def test_writer_rejects_symlink_escape_without_touching_outside_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            bundle_root = temp_root / "knowledge" / "persona" / "feeze"
            outside_root = temp_root / "outside"
            bundle_root.mkdir(parents=True)
            outside_root.mkdir()
            (bundle_root / "identity").symlink_to(outside_root, target_is_directory=True)

            with (
                patch.object(persona_bundle_writer, "resolve_workspace_root", return_value=temp_root),
                patch.object(persona_bundle_writer, "resolve_persona_bundle_write_root", return_value=bundle_root),
            ):
                with self.assertRaisesRegex(ValueError, "cannot contain symlinks"):
                    persona_bundle_writer.write_promotion_items_to_bundle(
                        [_promotion_item("identity/claims.md")]
                    )

            self.assertEqual(list(outside_root.iterdir()), [])

    def test_writer_rejects_symlink_in_bundle_root_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            workspace_root = temp_root / "workspace"
            outside_root = temp_root / "outside"
            workspace_root.mkdir()
            (outside_root / "persona" / "feeze").mkdir(parents=True)
            (workspace_root / "knowledge").symlink_to(outside_root, target_is_directory=True)
            bundle_root = workspace_root / "knowledge" / "persona" / "feeze"

            with (
                patch.object(persona_bundle_writer, "resolve_workspace_root", return_value=workspace_root),
                patch.object(persona_bundle_writer, "resolve_persona_bundle_write_root", return_value=bundle_root),
            ):
                with self.assertRaisesRegex(ValueError, "cannot contain symlinks"):
                    persona_bundle_writer.write_promotion_items_to_bundle(
                        [_promotion_item("identity/claims.md")]
                    )

            self.assertFalse((outside_root / "persona" / "feeze" / "identity" / "claims.md").exists())

    def test_writer_preserves_valid_multi_target_promotions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            bundle_root = workspace_root / "knowledge" / "persona" / "feeze"
            with (
                patch.object(persona_bundle_writer, "resolve_workspace_root", return_value=workspace_root),
                patch.object(persona_bundle_writer, "resolve_persona_bundle_write_root", return_value=bundle_root),
            ):
                result = persona_bundle_writer.write_promotion_items_to_bundle(
                    [
                        _promotion_item("identity/claims.md", item_id="claim-valid"),
                        _promotion_item("identity/philosophy.md", item_id="philosophy-valid"),
                    ]
                )

            self.assertEqual(
                result["written_files"],
                ["identity/claims.md", "identity/philosophy.md"],
            )
            self.assertIn(
                "Canonical content for claim-valid.",
                (bundle_root / "identity" / "claims.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Canonical content for philosophy-valid.",
                (bundle_root / "identity" / "philosophy.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
