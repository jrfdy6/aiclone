from __future__ import annotations

import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from app.models import PMExecutionResultCommitRequest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "runners" / "write_execution_result.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WriteExecutionResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_module("write_execution_result_test_module", SCRIPT_PATH)

    def test_auto_progress_review_card_prefers_service_helper(self) -> None:
        calls: list[tuple[str, bool]] = []

        def fake_auto_progress(card_id: str, *, record_audit: bool = False):
            calls.append((card_id, record_audit))
            return {"processed": True, "rule": "workspace_policy_accept_and_close"}

        result = self.script._auto_progress_review_card(
            {"mode": "service", "auto_progress_card": fake_auto_progress},
            "https://example.test",
            "card-service-1",
        )

        self.assertEqual(result, {"processed": True, "rule": "workspace_policy_accept_and_close"})
        self.assertEqual(calls, [("card-service-1", False)])

    def test_auto_progress_review_card_uses_targeted_api_endpoint(self) -> None:
        with patch.object(self.script, "_fetch_json", return_value={"processed": True}) as fetch_mock:
            result = self.script._auto_progress_review_card(
                {"mode": "api"},
                "https://example.test",
                "card-api-1",
            )

        self.assertEqual(result, {"processed": True})
        fetch_mock.assert_called_once_with(
            "https://example.test/api/pm/cards/card-api-1/auto-progress",
            method="POST",
        )

    def test_legacy_fetch_rejects_untrusted_host_before_loading_authorization(self) -> None:
        with patch.object(self.script, "control_plane_headers") as headers:
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                self.script._fetch_json("https://evil.example/api/pm/cards")

        headers.assert_not_called()

    def test_stable_result_id_is_deterministic_per_claim(self) -> None:
        card_id, claim_id = str(uuid4()), str(uuid4())

        first = self.script._stable_result_id(card_id, claim_id, None)
        second = self.script._stable_result_id(card_id, claim_id, None)

        self.assertEqual(first, second)
        self.assertNotEqual(first, self.script._stable_result_id(card_id, str(uuid4()), None))

    def test_local_materialization_is_idempotent_across_replay(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_raw:
            workspace_root = Path(temp_raw).resolve()
            memory_root = workspace_root / "memory"
            state_root = workspace_root / ".runtime-state"
            chronicle_path = memory_root / "codex_session_handoff.jsonl"
            work_order_path = workspace_root / "dispatch" / "work-order.json"
            workspace_result_path = workspace_root / "projects" / "sample" / "memory" / "execution_log.md"
            work_order_path.parent.mkdir(parents=True)
            work_order_path.write_text("{}\n", encoding="utf-8")

            result_id = str(uuid4())
            operation = PMExecutionResultCommitRequest(
                card_id=str(uuid4()),
                claim_id=str(uuid4()),
                worker_id="mac-runner",
                result_id=result_id,
                runner_id="brain-local-action",
                author_agent="Brain Local Action",
                created_at=datetime.now(timezone.utc),
                workspace_key="shared_ops",
                title="Finish a deterministic action",
                status="done",
                summary="The deterministic action completed.",
                decisions=["Keep the signed narrow contract."],
                learnings=["Replay must not duplicate durable memory."],
                outcomes=["The effect is present."],
                memory_promotions=["Preserve the result id as the replay key."],
                persistent_state_updates=["Execution reconciliation is enabled."],
                artifacts=[str(work_order_path)],
                result_path=str(memory_root / "runner-results" / "brain-local-action" / f"{result_id}.json"),
                memo_path=str(
                    memory_root / "runner-memos" / "brain-local-action" / f"{result_id}_execution_result.md"
                ),
                work_order_path=str(work_order_path),
                workspace_result_path=str(workspace_result_path),
            )

            with (
                patch.object(self.script, "WORKSPACE_ROOT", workspace_root),
                patch.object(self.script, "MEMORY_ROOT", memory_root),
                patch.object(self.script, "STATE_ROOT", state_root),
                patch.object(self.script, "CODEX_HANDOFF_PATH", chronicle_path),
                patch.object(
                    self.script,
                    "_runtime_memory_path",
                    side_effect=lambda relative: workspace_root / relative,
                ),
            ):
                self.script._materialize_execution_result(operation)
                self.script._materialize_execution_result(operation)

            result_path = Path(operation.result_path)
            self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["result_id"], result_id)
            chronicle = [
                json.loads(line)
                for line in chronicle_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual([item["result_id"] for item in chronicle], [result_id])
            marker = f"<!-- execution-result:{result_id} -->"
            daily_path = memory_root / f"{operation.created_at.astimezone().date().isoformat()}.md"
            self.assertEqual(daily_path.read_text(encoding="utf-8").count(marker), 1)
            self.assertEqual(workspace_result_path.read_text(encoding="utf-8").count(marker), 1)
            self.assertEqual((workspace_root / "memory/LEARNINGS.md").read_text(encoding="utf-8").count(marker), 1)
            self.assertEqual(
                (workspace_root / "memory/persistent_state.md").read_text(encoding="utf-8").count(marker),
                1,
            )

    def test_chronicle_append_rejects_symlink_target(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            target = root / "target.jsonl"
            target.write_text('{"preserve": true}\n', encoding="utf-8")
            link = root / "chronicle.jsonl"
            link.symlink_to(target)

            with self.assertRaisesRegex(RuntimeError, "must not be a symlink"):
                self.script._append_jsonl_once(
                    link,
                    {"result_id": str(uuid4()), "summary": "Should not append"},
                    result_id=str(uuid4()),
                )

            self.assertEqual(target.read_text(encoding="utf-8"), '{"preserve": true}\n')


if __name__ == "__main__":
    unittest.main()
