#!/usr/bin/env python3
"""Create or verify a private, local-only AI Clone state snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from secure_backup import create_state_snapshot, verify_state_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", help="Verify an existing state snapshot instead of creating one.")
    parser.add_argument("--state-root", help="Override AI_CLONE_STATE_ROOT for this snapshot.")
    parser.add_argument("--output-root", help="Override the private state-backup directory.")
    args = parser.parse_args()
    if args.verify:
        result = verify_state_snapshot(Path(args.verify))
    else:
        kwargs = {}
        if args.state_root:
            kwargs["state_root"] = Path(args.state_root)
        if args.output_root:
            kwargs["output_root"] = Path(args.output_root)
        result = create_state_snapshot(**kwargs)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
