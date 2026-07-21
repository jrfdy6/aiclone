from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.persona_bundle_context_service import load_bundle_persona_chunks


class PersonaBundleContextServiceTests(unittest.TestCase):
    def test_loads_external_reference_chunks_with_style_reference_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "knowledge" / "persona" / "feeze"
            (bundle_root / "references").mkdir(parents=True, exist_ok=True)
            (bundle_root / "manifest.json").write_text("{}", encoding="utf-8")
            (bundle_root / "references" / "external_reference_packets.md").write_text(
                "\n".join(
                    [
                        "---",
                        'title: "External Reference Packets"',
                        'persona_id: "johnnie_fields"',
                        'target_file: "references/external_reference_packets.md"',
                        "---",
                        "",
                        "## External Belief Packets",
                        "- AI is becoming infrastructure, not just a tool.",
                    ]
                ),
                encoding="utf-8",
            )

            with patch(
                "app.services.persona_bundle_context_service.resolve_persona_bundle_root",
                return_value=bundle_root,
            ):
                chunks = load_bundle_persona_chunks()

        external_chunks = [
            chunk
            for chunk in chunks
            if (chunk.get("metadata") or {}).get("source_kind") == "external_reference"
        ]
        self.assertTrue(external_chunks)
        metadata = external_chunks[0]["metadata"]
        self.assertEqual(metadata.get("memory_role"), "example")
        self.assertEqual(metadata.get("proof_kind"), "external_reference")
        self.assertEqual(metadata.get("reference_policy"), "style_reference_only")
        self.assertIn("style_reference", metadata.get("usage_modes") or [])


if __name__ == "__main__":
    unittest.main()
