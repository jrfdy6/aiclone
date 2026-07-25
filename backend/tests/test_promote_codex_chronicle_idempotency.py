from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SCRIPT_PATH = SCRIPTS_ROOT / "promote_codex_chronicle.py"


def load_script_module():
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location(
        "promote_codex_chronicle_idempotency_script",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_prep(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "standup_prep/v1",
                "memory_promotions": [
                    {
                        "target": "learnings",
                        "content": "Concurrent promotions should produce one durable learning.",
                    }
                ],
                "pm_updates": [
                    {
                        "workspace_key": "future-capability",
                        "title": "Verify the future workspace promotion.",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


class PromoteCodexChronicleIdempotencyTests(unittest.TestCase):
    def test_replay_after_append_before_marker_checkpoint_does_not_duplicate_block(self) -> None:
        module = load_script_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            memory_root = root / "state" / "memory"
            prep_path = root / "prep.json"
            project_root.mkdir()
            write_prep(prep_path)
            argv = [
                "promote_codex_chronicle.py",
                "--prep-json",
                str(prep_path),
                "--workspace-key",
                "future-capability",
                "--write-learnings",
                "--write-pm-recommendations",
            ]
            real_mark_stage = module._mark_promotion_stage

            def fail_daily_checkpoint(
                marker_path: Path,
                marker: dict[str, object],
                stage: str,
                **kwargs: object,
            ) -> None:
                if stage == "daily_memory":
                    raise RuntimeError("simulated crash before promotion marker checkpoint")
                real_mark_stage(marker_path, marker, stage, **kwargs)

            with mock.patch.object(module, "MEMORY_ROOT", memory_root), mock.patch.object(
                module,
                "WORKSPACE_ROOT",
                project_root,
            ), mock.patch.object(sys, "argv", argv), mock.patch.object(
                module,
                "_mark_promotion_stage",
                side_effect=fail_daily_checkpoint,
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                    module.main()

            with mock.patch.object(module, "MEMORY_ROOT", memory_root), mock.patch.object(
                module,
                "WORKSPACE_ROOT",
                project_root,
            ), mock.patch.object(sys, "argv", argv):
                self.assertEqual(module.main(), 0)

            daily_paths = sorted(memory_root.glob("20??-??-??.md"))
            self.assertEqual(len(daily_paths), 1)
            daily_text = daily_paths[0].read_text(encoding="utf-8")
            self.assertEqual(daily_text.count("### Durable Memory Candidates"), 1)
            self.assertEqual(daily_text.count(":daily-memory -->"), 1)
            learnings_text = (memory_root / "LEARNINGS.md").read_text(encoding="utf-8")
            self.assertEqual(
                learnings_text.count(
                    "Concurrent promotions should produce one durable learning."
                ),
                1,
            )
            recommendation_paths = list((memory_root / "pm-recommendations").glob("*.json"))
            self.assertEqual(len(recommendation_paths), 1)
            marker_paths = list((memory_root / "promotion-markers").glob("*.json"))
            self.assertEqual(len(marker_paths), 1)
            marker = json.loads(marker_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(marker["stages"]["daily_memory"]["status"], "complete")
            self.assertFalse(marker["stages"]["daily_memory"]["created"])
            self.assertEqual(marker["stages"]["learnings"]["status"], "complete")
            self.assertEqual(marker["stages"]["pm_recommendations"]["status"], "complete")

    def test_concurrent_promotions_create_one_daily_block_and_one_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            state_root = root / "state"
            prep_path = root / "prep.json"
            project_root.mkdir()
            write_prep(prep_path)
            command = [
                sys.executable,
                str(SCRIPT_PATH),
                "--prep-json",
                str(prep_path),
                "--workspace-key",
                "future-capability",
                "--write-learnings",
                "--write-pm-recommendations",
            ]
            environment = os.environ.copy()
            environment["AI_CLONE_ROOT"] = str(project_root)
            environment["AI_CLONE_STATE_ROOT"] = str(state_root)
            processes = [
                subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=environment,
                )
                for _ in range(2)
            ]
            results = [process.communicate(timeout=20) for process in processes]

            for process, (stdout, stderr) in zip(processes, results):
                self.assertEqual(process.returncode, 0, msg=f"stdout={stdout}\nstderr={stderr}")
            memory_root = state_root / "memory"
            daily_paths = sorted(memory_root.glob("20??-??-??.md"))
            self.assertEqual(len(daily_paths), 1)
            daily_text = daily_paths[0].read_text(encoding="utf-8")
            self.assertEqual(daily_text.count("### Durable Memory Candidates"), 1)
            self.assertEqual(daily_text.count(":daily-memory -->"), 1)
            learnings_text = (memory_root / "LEARNINGS.md").read_text(encoding="utf-8")
            self.assertEqual(
                learnings_text.count(
                    "Concurrent promotions should produce one durable learning."
                ),
                1,
            )
            self.assertEqual(
                len(list((memory_root / "pm-recommendations").glob("*.json"))),
                1,
            )
            self.assertEqual(
                len(list((memory_root / "promotion-markers").glob("*.json"))),
                1,
            )


if __name__ == "__main__":
    unittest.main()
