#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.instagram_public_feedback_service import instagram_public_feedback_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-key", default="fusion-os")
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT / "workspaces" / "fusion-os"))
    parser.add_argument("--username", default="fusionacademydc")
    parser.add_argument("--sample-size", type=int, default=12)
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root)
    snapshot = instagram_public_feedback_service.build_snapshot(args.username, sample_size=max(args.sample_size, 1))
    persisted = instagram_public_feedback_service.persist_workspace_snapshot(args.workspace_key, workspace_root, snapshot)
    print(
        json.dumps(
            {
                "workspace_key": args.workspace_key,
                "username": args.username,
                "followers": ((snapshot.get("profile") or {}).get("followers") or 0),
                "average_visible_engagement": ((snapshot.get("recent_summary") or {}).get("average_visible_engagement") or 0),
                "sample_size": ((snapshot.get("recent_summary") or {}).get("sample_size") or 0),
                **persisted,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
