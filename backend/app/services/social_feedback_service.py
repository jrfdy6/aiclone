from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.workspace_snapshot_store import upsert_snapshot

def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/")]
    seen: set[Path] = set()
    for parent in candidates:
        if parent in seen:
            continue
        seen.add(parent)
        if (parent / "workspaces" / "linkedin-content-os").exists():
            return parent
    return current.parents[3]


ROOT = resolve_workspace_root()
WORKSPACE_ROOT = ROOT / "workspaces" / "linkedin-content-os"
FEEDBACK_DIR = WORKSPACE_ROOT / "analytics"
FEEDBACK_PATH = FEEDBACK_DIR / "feed_feedback.md"
FEEDBACK_JSONL_PATH = FEEDBACK_DIR / "feed_feedback.jsonl"
FEEDBACK_SUMMARY_PATH = FEEDBACK_DIR / "feed_feedback_summary.json"
WORKSPACE_KEY = "linkedin-content-os"
SNAPSHOT_TYPE = "feedback_summary"


class SocialFeedbackService:
    def ensure_feedback_dir(self) -> None:
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

    def _persist_summary_snapshot(self, summary: dict[str, Any]) -> None:
        upsert_snapshot(
            WORKSPACE_KEY,
            SNAPSHOT_TYPE,
            summary,
            metadata={"source": "social_feedback_service"},
        )

    def _rebuild_summary(self) -> dict[str, Any]:
        if not FEEDBACK_JSONL_PATH.exists():
            summary = {"total_events": 0, "generated_at": datetime.now(timezone.utc).isoformat()}
            FEEDBACK_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            self._persist_summary_snapshot(summary)
            return summary

        events: list[dict[str, Any]] = []
        with FEEDBACK_JSONL_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        decision_counts: dict[str, int] = {}
        lens_counts: dict[str, int] = {}
        stance_counts: dict[str, int] = {}
        technique_counts: dict[str, int] = {}
        scored_events: list[float] = []
        expression_output_scores: list[float] = []
        expression_deltas: list[float] = []
        low_score_events: list[dict[str, Any]] = []
        rejected_sources: list[dict[str, Any]] = []

        for event in events:
            decision = str(event.get("decision") or "unknown")
            lens = str(event.get("lens") or "unknown")
            stance = str(event.get("stance") or "unknown")
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            lens_counts[lens] = lens_counts.get(lens, 0) + 1
            stance_counts[stance] = stance_counts.get(stance, 0) + 1

            if decision == "reject":
                rejected_sources.append(
                    {
                        "recorded_at": event.get("recorded_at"),
                        "feed_item_id": event.get("feed_item_id"),
                        "title": event.get("title"),
                        "platform": event.get("platform"),
                        "lens": event.get("lens"),
                        "source_url": event.get("source_url"),
                        "source_path": event.get("source_path"),
                        "notes": event.get("notes"),
                        "evaluation_overall": event.get("evaluation_overall"),
                        "source_expression_quality": event.get("source_expression_quality"),
                    }
                )

            for technique in event.get("techniques") or []:
                technique_key = str(technique)
                technique_counts[technique_key] = technique_counts.get(technique_key, 0) + 1

            evaluation = event.get("evaluation_overall")
            if isinstance(evaluation, (float, int)):
                score = float(evaluation)
                scored_events.append(score)
                if score < 6.8:
                    low_score_events.append(
                        {
                            "recorded_at": event.get("recorded_at"),
                            "feed_item_id": event.get("feed_item_id"),
                            "title": event.get("title"),
                            "lens": event.get("lens"),
                            "stance": event.get("stance"),
                            "evaluation_overall": score,
                        }
                    )

            expression_output = event.get("output_expression_quality")
            if isinstance(expression_output, (float, int)):
                expression_output_scores.append(float(expression_output))

            expression_delta = event.get("expression_delta")
            if isinstance(expression_delta, (float, int)):
                expression_deltas.append(float(expression_delta))

        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(events),
            "decision_counts": decision_counts,
            "lens_counts": lens_counts,
            "stance_counts": stance_counts,
            "technique_counts": technique_counts,
            "average_evaluation_overall": round(sum(scored_events) / len(scored_events), 2) if scored_events else None,
            "average_output_expression_quality": (
                round(sum(expression_output_scores) / len(expression_output_scores), 2) if expression_output_scores else None
            ),
            "average_expression_delta": (
                round(sum(expression_deltas) / len(expression_deltas), 2) if expression_deltas else None
            ),
            "low_score_events": low_score_events[-10:],
            "rejected_source_count": len(rejected_sources),
            "rejected_sources": rejected_sources[-20:],
            "recent_events": events[-10:],
        }
        FEEDBACK_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self._persist_summary_snapshot(summary)
        return summary

    def append_feedback(self, entry: dict[str, Any]) -> Path:
        self.ensure_feedback_dir()
        timestamp = datetime.now(timezone.utc).isoformat()
        line = (
            f"- {timestamp} | {entry['decision']} | {entry['feed_item_id']} | "
            f"{entry['platform']} | lens={entry.get('lens')} | stance={entry.get('stance')} | "
            f"score={entry.get('evaluation_overall')} | {entry.get('title')}\n"
        )
        with FEEDBACK_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line)
        json_entry = {"recorded_at": timestamp, **entry}
        with FEEDBACK_JSONL_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(json_entry, ensure_ascii=True) + "\n")
        self._rebuild_summary()
        return FEEDBACK_PATH

    def load_summary(self) -> dict[str, Any]:
        self.ensure_feedback_dir()
        if FEEDBACK_SUMMARY_PATH.exists():
            try:
                return json.loads(FEEDBACK_SUMMARY_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return self._rebuild_summary()


social_feedback_service = SocialFeedbackService()
