#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import voice_fidelity_service as voice


def _read_text(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8").strip()


def _held_out_evaluation(entries: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, held_out in enumerate(entries):
        references = [
            str(entry.get("text") or "")
            for other_index, entry in enumerate(entries)
            if other_index != index
        ]
        result = voice.score_voice_fidelity(str(held_out.get("text") or ""), exemplars=references)
        rows.append(
            {
                "id": held_out.get("id"),
                "post_type": held_out.get("post_type"),
                "score": result.get("score"),
                "warnings": result.get("warnings"),
            }
        )
    numeric_scores = [float(row["score"]) for row in rows if isinstance(row.get("score"), (int, float))]
    return {
        "method": "leave_one_published_post_out",
        "sample_count": len(rows),
        "mean_score": round(sum(numeric_scores) / len(numeric_scores), 1) if numeric_scores else None,
        "minimum_score": round(min(numeric_scores), 1) if numeric_scores else None,
        "maximum_score": round(max(numeric_scores), 1) if numeric_scores else None,
        "rows": rows,
        "note": "This is a calibration baseline, not proof that a generated draft is authentic.",
    }


def _audit(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser() if args.path else None
    entries = voice.load_voice_corpus(path, execution_mode="cloud")
    context = voice.build_voice_context(
        query=args.query,
        path=path,
        execution_mode="cloud",
        limit=args.limit,
    )
    payload = {
        "audit": voice.audit_voice_corpus(path),
        "selected_reference_ids": context["reference_ids"],
        "selected_reference_modes": context["reference_modes"],
        "approved_external_influence_count": context["influence_count"],
        "selected_external_influence_ids": context["influence_ids"],
        "retrieval": context["retrieval"],
        "fingerprint": context["fingerprint"],
        "held_out_evaluation": _held_out_evaluation(entries),
        "next_target": {
            "minimum_full_examples": 15,
            "strong_full_example_range": "30-50",
            "preference_pairs_before_reranker_training": "50-100",
            "preference_pairs_before_style fine-tuning": "200-500",
            "external_influence_note": "Technique cards enrich framing but never count toward owner-authorship targets.",
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _add(args: argparse.Namespace) -> int:
    result = voice.append_voice_example(
        text=_read_text(args.text_file),
        provenance=args.provenance,
        approval_status=args.approval_status,
        privacy=args.privacy,
        channel=args.channel,
        post_type=args.post_type,
        topic_tags=args.topic_tag,
        source_url=args.source_url,
        entry_id=args.id,
        path=Path(args.path).expanduser() if args.path else None,
    )
    safe_result = {
        "created": result["created"],
        "path": result["path"],
        "id": result["entry"]["id"],
        "privacy": result["entry"]["privacy"],
        "provenance": result["entry"]["provenance"],
    }
    print(json.dumps(safe_result, indent=2))
    return 0


def _preference(args: argparse.Namespace) -> int:
    context = {
        "channel": args.channel,
        "post_type": args.post_type,
        "topic_tags": args.topic_tag,
        "topic": args.topic,
    }
    result = voice.record_voice_preference(
        generated_text=_read_text(args.generated_file),
        edited_text=_read_text(args.edited_file) if args.edited_file else None,
        rejected_texts=[_read_text(path) for path in args.rejected_file],
        context=context,
        privacy=args.privacy,
        promote_edited=args.promote_edited,
        corpus_path=Path(args.corpus_path).expanduser() if args.corpus_path else None,
        preference_path=Path(args.preference_path).expanduser() if args.preference_path else None,
    )
    print(
        json.dumps(
            {
                "created": result["created"],
                "path": result["path"],
                "preference_id": result["preference_id"],
                "promoted": bool(result["promoted"]),
            },
            indent=2,
        )
    )
    return 0


def _import_review(args: argparse.Namespace) -> int:
    result = voice.import_local_voice_review_packet(
        Path(args.packet_file).expanduser(),
        preference_path=Path(args.preference_path).expanduser() if args.preference_path else None,
    )
    print(json.dumps(result, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and maintain the private local owner-voice corpus.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Audit corpus eligibility, retrieval, fingerprint, and held-out calibration.")
    audit.add_argument("--path")
    audit.add_argument("--query", default="AI systems, education, leadership, and turning signal into value")
    audit.add_argument("--limit", type=int, default=4)
    audit.set_defaults(handler=_audit)

    add = subparsers.add_parser("add", help="Add one explicitly approved owner-written example.")
    add.add_argument("--text-file", required=True)
    add.add_argument("--provenance", choices=sorted(voice.APPROVED_PROVENANCE), required=True)
    add.add_argument("--approval-status", choices=sorted(voice.APPROVED_STATUSES), default="approved")
    add.add_argument("--privacy", choices=["public", "cloud_ok_excerpt", "local_only", "sensitive"], required=True)
    add.add_argument("--channel", default="linkedin")
    add.add_argument("--post-type", default="unspecified")
    add.add_argument("--topic-tag", action="append", default=[])
    add.add_argument("--source-url")
    add.add_argument("--id")
    add.add_argument("--path")
    add.set_defaults(handler=_add)

    preference = subparsers.add_parser("preference", help="Record a generated→edited preference pair locally.")
    preference.add_argument("--generated-file", required=True)
    preference.add_argument("--edited-file")
    preference.add_argument("--rejected-file", action="append", default=[])
    preference.add_argument("--privacy", choices=["public", "cloud_ok_excerpt", "local_only", "sensitive"], default="local_only")
    preference.add_argument("--promote-edited", action="store_true")
    preference.add_argument("--channel", default="linkedin")
    preference.add_argument("--post-type", default="owner_edited")
    preference.add_argument("--topic")
    preference.add_argument("--topic-tag", action="append", default=[])
    preference.add_argument("--corpus-path")
    preference.add_argument("--preference-path")
    preference.set_defaults(handler=_preference)

    import_review = subparsers.add_parser(
        "import-review",
        help="Import one browser-downloaded FEEZIE decision into the local-only preference log.",
    )
    import_review.add_argument("--packet-file", required=True)
    import_review.add_argument("--preference-path")
    import_review.set_defaults(handler=_import_review)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
