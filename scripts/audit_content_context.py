#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_generation_context_service import build_content_generation_context  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect the upstream content-context pipeline before generation.")
    parser.add_argument("--user-id", default="johnnie_fields", help="Knowledge base user id.")
    parser.add_argument("--topic", required=True, help="Topic to audit.")
    parser.add_argument("--context", default="", help="Optional extra context.")
    parser.add_argument("--content-type", default="linkedin_post", help="Channel/content type.")
    parser.add_argument("--category", default="value", help="Content category.")
    parser.add_argument("--tone", default="expert_direct", help="Requested tone.")
    parser.add_argument("--audience", default="general", help="Audience lane.")
    parser.add_argument(
        "--source-mode",
        default="persona_only",
        help="Context source mode: persona_only, selected_source, recent_signals.",
    )
    parser.add_argument("--output", help="Optional file path for the JSON audit payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    captured_stdout = io.StringIO()
    with contextlib.redirect_stdout(captured_stdout):
        context = build_content_generation_context(
            user_id=args.user_id,
            topic=args.topic,
            context=args.context,
            content_type=args.content_type,
            category=args.category,
            tone=args.tone,
            audience=args.audience,
            source_mode=args.source_mode,
            include_audit=True,
            allow_snapshot_rebuild=False,
        )
    payload = {
        "success": True,
        "persona_context": context.persona_context_summary,
        "grounding_mode": context.grounding_mode,
        "grounding_reason": context.grounding_reason,
        "framing_modes": context.framing_modes,
        "primary_claims": context.primary_claims,
        "proof_packets": context.proof_packets,
        "story_beats": context.story_beats,
        "audit": context.audit,
    }
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    captured_logs = captured_stdout.getvalue().strip()
    if captured_logs:
        sys.stderr.write(captured_logs + "\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
