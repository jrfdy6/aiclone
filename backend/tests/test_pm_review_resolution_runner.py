from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PMReviewResolutionRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS_ROOT) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_ROOT))
        cls.runner = _load_module("run_pm_review_resolution", SCRIPTS_ROOT / "runners" / "run_pm_review_resolution.py")

    def test_run_progress_uses_service_helper_when_available(self) -> None:
        imports = {
            "mode": "service",
            "auto_progress_review_cards": lambda limit=0: {
                "processed_count": limit,
                "closed_count": 1,
                "continued_count": 0,
                "processed": [],
            },
        }

        mode_used, payload = self.runner._run_progress(imports, "https://example.test", limit=7)

        self.assertEqual(mode_used, "service")
        self.assertEqual(payload.get("processed_count"), 7)

    def test_run_progress_posts_to_pm_auto_progress_route(self) -> None:
        with patch.object(
            self.runner,
            "_fetch_json",
            return_value={"processed_count": 2, "closed_count": 1, "continued_count": 1, "processed": []},
        ) as fetch_mock:
            mode_used, payload = self.runner._run_progress({"mode": "api"}, "https://example.test", limit=11)

        self.assertEqual(mode_used, "api")
        self.assertEqual(payload.get("processed_count"), 2)
        fetch_mock.assert_called_once_with(
            "https://example.test/api/pm/review-hygiene/auto-progress?limit=11",
            method="POST",
        )


if __name__ == "__main__":
    unittest.main()
