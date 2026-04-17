from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import PersonaDelta  # noqa: E402
from app.services import persona_promotion_service  # noqa: E402


def _load_persona_bundle_sync_module():
    module_path = WORKSPACE_ROOT / "automations" / "persona_bundle_sync.py"
    spec = importlib.util.spec_from_file_location("persona_bundle_sync_test_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load persona_bundle_sync module for tests.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


persona_bundle_sync_module = _load_persona_bundle_sync_module()


class PersonaPromotionServiceTests(unittest.TestCase):
    def test_promote_delta_to_canon_marks_sync_pending_without_bundle_write_metadata(self) -> None:
        delta = PersonaDelta(
            id="delta-promote",
            capture_id=None,
            persona_target="feeze.core",
            trait="Promote this to canon",
            notes="Promotion note",
            status="approved",
            metadata={
                "pending_promotion": True,
                "target_file": "identity/claims.md",
                "selected_promotion_items": [
                    {
                        "id": "claim-1",
                        "kind": "talking_point",
                        "label": "Claim",
                        "content": "Operator clarity matters more than hype.",
                        "targetFile": "identity/claims.md",
                    }
                ],
            },
            created_at=datetime.now(timezone.utc),
            committed_at=None,
        )

        def fake_update(delta_id: str, payload):
            merged = dict(delta.metadata)
            merged.update(payload.metadata or {})
            return delta.model_copy(update={"status": payload.status or delta.status, "metadata": merged, "committed_at": datetime.now(timezone.utc)})

        with patch.object(persona_promotion_service.persona_delta_service, "get_delta", return_value=delta), patch.object(
            persona_promotion_service.persona_delta_service,
            "update_delta",
            side_effect=fake_update,
        ):
            updated = persona_promotion_service.promote_delta_to_canon("delta-promote")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "committed")
        self.assertEqual((updated.metadata or {}).get("committed_target_files"), ["identity/claims.md"])
        self.assertEqual((updated.metadata or {}).get("committed_item_count"), 1)
        self.assertNotIn("bundle_root", updated.metadata or {})
        self.assertNotIn("bundle_written_files", updated.metadata or {})
        self.assertNotIn("bundle_file_results", updated.metadata or {})
        self.assertEqual(((updated.metadata or {}).get("local_bundle_sync") or {}).get("state"), "pending")

    def test_update_local_sync_state_publishes_bundle_metadata_after_sync(self) -> None:
        bundle_write = {
            "bundle_root": "/tmp/persona",
            "written_files": ["identity/claims.md"],
            "file_results": {"identity/claims.md": {"added": 1, "skipped": 0}},
        }

        with patch.object(persona_bundle_sync_module, "_json_request", return_value={"ok": True}) as request_mock:
            persona_bundle_sync_module.update_local_sync_state(
                "https://example.test",
                "delta-123",
                state="synced",
                bundle_write=bundle_write,
            )

        payload = request_mock.call_args.kwargs["payload"]
        metadata = payload["metadata"]
        self.assertEqual(metadata["bundle_root"], "/tmp/persona")
        self.assertEqual(metadata["bundle_written_files"], ["identity/claims.md"])
        self.assertEqual(metadata["bundle_file_results"]["identity/claims.md"]["added"], 1)
        self.assertEqual(metadata["local_bundle_sync"]["state"], "synced")
        self.assertEqual(metadata["local_bundle_sync"]["written_files"], ["identity/claims.md"])


if __name__ == "__main__":
    unittest.main()
