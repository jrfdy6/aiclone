#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "workspaces" / "linkedin-content-os").exists():
            return parent
    raise RuntimeError("Unable to locate workspace root.")


WORKSPACE_ROOT = resolve_workspace_root()
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.social_signal_archive_service import sync_market_signal_archive  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill the tracked market signal archive from live runtime files.")
    parser.add_argument(
        "--workspace",
        default=str(WORKSPACE_ROOT / "workspaces" / "linkedin-content-os"),
        help="Path to the linkedin-content-os workspace root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(args.workspace).resolve()
    result = sync_market_signal_archive(workspace_root)
    print(f"archived={result['count']} months={','.join(result['months'])}")


if __name__ == "__main__":
    main()
