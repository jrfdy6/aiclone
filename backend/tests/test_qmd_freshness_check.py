from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "qmd_freshness_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("qmd_freshness_check", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QmdFreshnessCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_qmd_env_prepends_bun_aware_path(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": "/example/bin"}, clear=False):
            env = self.module.qmd_env()

        path_parts = env["PATH"].split(":")
        self.assertEqual(path_parts[:3], ["/Users/neo/.bun/bin", "/usr/local/bin", "/opt/homebrew/bin"])
        self.assertIn("/example/bin", path_parts)
        self.assertEqual(env["XDG_CONFIG_HOME"], str(self.module.QMD_CONFIG_HOME))
        self.assertEqual(env["XDG_CACHE_HOME"], str(self.module.QMD_CACHE_HOME))

    def test_resolve_qmd_binary_uses_bun_aware_path(self) -> None:
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/local/bin/qmd") as which:
            resolved = self.module.resolve_qmd_binary()

        self.assertEqual(resolved, "/usr/local/bin/qmd")
        _, kwargs = which.call_args
        self.assertIn("/Users/neo/.bun/bin", kwargs["path"].split(":"))


if __name__ == "__main__":
    unittest.main()
