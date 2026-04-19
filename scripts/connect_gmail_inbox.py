#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.gmail_inbox_service import authorize_gmail_account, gmail_connection_status  # noqa: E402
from app.utils import env_loader  # noqa: F401, E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize Gmail API access for the shared inbox.")
    parser.add_argument("--status", action="store_true", help="Print current Gmail connection status and exit.")
    parser.add_argument("--no-browser", action="store_true", help="Do not attempt to open a browser automatically.")
    parser.add_argument("--port", type=int, default=0, help="Local OAuth callback port. Default: 0 (auto)")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(gmail_connection_status(), indent=2))
        return 0

    status = authorize_gmail_account(open_browser=not args.no_browser, port=args.port)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
