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

from app.services.content_generation_pipeline_audit_service import build_content_generation_pipeline_audit  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the content-generation pipeline phase by phase.")
    parser.add_argument("--user-id", default="johnnie_fields")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--context", default="")
    parser.add_argument("--content-type", default="linkedin_post")
    parser.add_argument("--category", default="value")
    parser.add_argument("--tone", default="expert_direct")
    parser.add_argument("--audience", default="general")
    parser.add_argument("--no-snapshot-rebuild", action="store_true")
    parser.add_argument("--output", help="Optional output file path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_content_generation_pipeline_audit(
        user_id=args.user_id,
        topic=args.topic,
        context=args.context,
        content_type=args.content_type,
        category=args.category,
        tone=args.tone,
        audience=args.audience,
        allow_snapshot_rebuild=not args.no_snapshot_rebuild,
    )
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
