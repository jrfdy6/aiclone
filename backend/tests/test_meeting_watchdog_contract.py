from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _load_watchdog():
    path = SCRIPTS_ROOT / "meeting_watchdog.py"
    spec = importlib.util.spec_from_file_location("meeting_watchdog_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_required_rooms_include_every_portfolio_workspace() -> None:
    watchdog = _load_watchdog()
    room_pairs = {(room.workspace_key, room.key) for room in watchdog.ROOM_SPECS}

    assert ("work-life-tools", "workspace_sync") in room_pairs
    assert len(room_pairs) == 10
