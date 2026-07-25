from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


WORKSPACE_KEY = "linkedin-content-os"
WORKSPACE_STATE_KEY = "feezie-os"
WORKSPACE_RELATIVE = "workspaces/linkedin-content-os"

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.runtime_paths import (  # noqa: E402
    resolve_workspace_read_path,
    seed_workspace_state_file,
    workspace_read_candidates,
    workspace_state_path,
)

ROLE_ALIGNMENT_BY_LANE = {
    "ai": "ai_intrapreneur",
    "ops-pm": "role_anchored",
    "program-leadership": "role_anchored",
    "admissions": "role_anchored",
    "current-role": "role_anchored",
    "referral": "role_anchored",
    "therapy": "role_anchored",
    "personal-story": "role_anchored",
    "entrepreneurship": "initiative",
}

PRIORITY_LANE_BY_LANE = {
    "ai": "AI systems and operator clarity",
    "ops-pm": "Operator clarity and execution",
    "program-leadership": "Leadership and execution behavior",
    "admissions": "Admissions, outreach, and trust",
    "current-role": "Current-role execution and credibility",
    "referral": "Referral trust and partner confidence",
    "therapy": "Trust, clarity, and human-centered support",
    "personal-story": "Personal story and lived-work proof",
    "entrepreneurship": "Builder lessons and intrapreneurship",
}

DEFAULT_POSITIONING_MODEL = [
    "Lead as a practical operator whose lived work creates trustworthy public signal.",
    "Let leadership, process, trust, and systems stay more visible than hype.",
    "Use AI and builder lessons only when they stay grounded in real execution.",
    "Avoid generic posting and fake founder energy.",
]

DEFAULT_PRIORITY_LANES = [
    "AI systems and operator clarity",
    "Leadership and execution behavior",
    "Admissions, outreach, and trust",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    return repo_root() / "workspaces" / WORKSPACE_KEY


def _configured_state_root() -> Path:
    configured = str(os.getenv("AI_CLONE_STATE_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex" / "ai-clone" / "state").resolve()


def uses_private_generated_state(workspace_dir: Path | None = None) -> bool:
    """Return whether generated FEEZIE output belongs in private local state.

    Explicit temporary workspaces retain their historical self-contained
    behavior unless a test/operator supplies ``AI_CLONE_STATE_ROOT``.
    Production's canonical workspace always uses the private state root.
    """

    if str(os.getenv("AI_CLONE_STATE_ROOT") or "").strip():
        return True
    candidate = (workspace_dir or workspace_root()).expanduser().resolve()
    return candidate == workspace_root().expanduser().resolve()


def generated_workspace_write_path(
    workspace_dir: Path,
    relative_path: str | Path,
) -> Path:
    relative = Path(relative_path)
    if not uses_private_generated_state(workspace_dir):
        return workspace_dir / relative
    return workspace_state_path(
        WORKSPACE_STATE_KEY,
        relative,
        state_root=_configured_state_root(),
    )


def generated_workspace_read_candidates(
    workspace_dir: Path,
    relative_path: str | Path,
) -> tuple[Path, ...]:
    relative = Path(relative_path)
    if not uses_private_generated_state(workspace_dir):
        return (workspace_dir / relative,)
    return workspace_read_candidates(
        WORKSPACE_STATE_KEY,
        relative,
        source_root=workspace_dir,
        project_root=repo_root(),
        state_root=_configured_state_root(),
    )


def generated_workspace_read_path(
    workspace_dir: Path,
    relative_path: str | Path,
) -> Path:
    relative = Path(relative_path)
    if not uses_private_generated_state(workspace_dir):
        return workspace_dir / relative
    return resolve_workspace_read_path(
        WORKSPACE_STATE_KEY,
        relative,
        source_root=workspace_dir,
        project_root=repo_root(),
        state_root=_configured_state_root(),
    )


def seed_generated_workspace_file(
    workspace_dir: Path,
    relative_path: str | Path,
) -> Path:
    """Copy a legacy generated file into private state before first mutation."""

    relative = Path(relative_path)
    if not uses_private_generated_state(workspace_dir):
        return workspace_dir / relative
    return seed_workspace_state_file(
        WORKSPACE_STATE_KEY,
        relative,
        source_root=workspace_dir,
        project_root=repo_root(),
        state_root=_configured_state_root(),
    )


def generated_workspace_files(
    workspace_dir: Path,
    relative_directory: str | Path,
    pattern: str,
) -> list[Path]:
    """Return a state-first union, with state files shadowing legacy names."""

    relative_directory = Path(relative_directory)
    selected: dict[str, Path] = {}
    roots: list[Path] = []
    if uses_private_generated_state(workspace_dir):
        roots.append(generated_workspace_write_path(workspace_dir, relative_directory))
    roots.append(workspace_dir / relative_directory)
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                selected.setdefault(path.name, path)
    return [selected[name] for name in sorted(selected)]


def generated_workspace_logical_relative_path(
    workspace_dir: Path,
    path: Path,
) -> Path:
    """Map either physical state or legacy storage back to workspace semantics."""

    resolved = path.expanduser().resolve()
    candidates = [workspace_dir.expanduser().resolve()]
    if uses_private_generated_state(workspace_dir):
        candidates.insert(0, generated_workspace_write_path(workspace_dir, ".").resolve())
    for root in candidates:
        try:
            return resolved.relative_to(root)
        except ValueError:
            continue
    raise ValueError(f"Path is outside FEEZIE workspace storage: {path}")


def plans_root(workspace_dir: Path | None = None) -> Path:
    return (workspace_dir or workspace_root()) / "plans"


def drafts_root(workspace_dir: Path | None = None) -> Path:
    return (workspace_dir or workspace_root()) / "drafts"


def analytics_root(workspace_dir: Path | None = None) -> Path:
    return (workspace_dir or workspace_root()) / "analytics"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def slugify(value: str) -> str:
    lowered = clean_text(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "draft"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any] | None:
    import json

    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def parse_frontmatter_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = read_text(path)
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip()
    return frontmatter if isinstance(frontmatter, dict) else {}, body


def first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def workspace_source_path(value: str | None) -> str:
    raw = clean_text(value)
    if not raw:
        return ""
    if raw.startswith(WORKSPACE_RELATIVE):
        return raw
    if raw.startswith("research/") or raw.startswith("plans/") or raw.startswith("drafts/") or raw.startswith("docs/") or raw.startswith("analytics/"):
        return f"{WORKSPACE_RELATIVE}/{raw}"
    return raw


def source_identity_keys(
    *,
    item_id: str | None = None,
    title: str | None = None,
    source_url: str | None = None,
    source_path: str | None = None,
) -> set[str]:
    keys: set[str] = set()
    cleaned_id = clean_text(item_id)
    if cleaned_id:
        keys.add(f"id:{cleaned_id}")
    cleaned_url = clean_text(source_url).rstrip("/").lower()
    if cleaned_url:
        keys.add(f"url:{cleaned_url}")
    normalized_path = workspace_source_path(source_path)
    if normalized_path:
        keys.add(f"path:{normalized_path.lower()}")
        prefix = f"{WORKSPACE_RELATIVE}/"
        if normalized_path.startswith(prefix):
            keys.add(f"path:{normalized_path.removeprefix(prefix).lower()}")
    title_slug = slugify(clean_text(title))
    if title_slug != "draft":
        keys.add(f"title:{title_slug}")
    return keys


def load_rejected_source_index(workspace_dir: Path | None = None) -> tuple[set[str], dict[str, dict[str, Any]]]:
    import json

    feedback_path = analytics_root(workspace_dir) / "feed_feedback.jsonl"
    rejected_keys: set[str] = set()
    rejected_by_key: dict[str, dict[str, Any]] = {}
    if not feedback_path.exists():
        return rejected_keys, rejected_by_key
    for line in feedback_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or clean_text(event.get("decision")).lower() != "reject":
            continue
        record = {
            "recorded_at": clean_text(event.get("recorded_at")),
            "feed_item_id": clean_text(event.get("feed_item_id")),
            "title": clean_text(event.get("title")),
            "platform": clean_text(event.get("platform")),
            "source_url": clean_text(event.get("source_url")),
            "source_path": workspace_source_path(event.get("source_path")),
            "lens": clean_text(event.get("lens")),
            "notes": clean_text(event.get("notes")),
        }
        keys = source_identity_keys(
            item_id=record["feed_item_id"],
            title=record["title"],
            source_url=record["source_url"],
            source_path=record["source_path"],
        )
        for key in keys:
            rejected_keys.add(key)
            rejected_by_key[key] = record
    return rejected_keys, rejected_by_key


def infer_primary_lane(item: dict[str, Any]) -> str:
    raw_lane = clean_text(item.get("priority_lane"))
    if raw_lane in PRIORITY_LANE_BY_LANE:
        return raw_lane

    lenses = item.get("lenses")
    if isinstance(lenses, list):
        for lens in lenses:
            cleaned = clean_text(lens)
            if cleaned in PRIORITY_LANE_BY_LANE:
                return cleaned

    topic_tags = {clean_text(tag) for tag in item.get("topic_tags") or []}
    if any("ai" in tag for tag in topic_tags):
        return "ai"
    if any("leadership" in tag for tag in topic_tags):
        return "program-leadership"
    return "current-role"


def role_alignment_for_lane(lane: str) -> str:
    return ROLE_ALIGNMENT_BY_LANE.get(lane, "role_anchored")


def priority_lane_label(lane: str) -> str:
    return PRIORITY_LANE_BY_LANE.get(lane, "Operator clarity and execution")


def risk_level_for_item(item: dict[str, Any]) -> str:
    explicit = clean_text(item.get("risk_level"))
    if explicit:
        return explicit
    role_safety = clean_text(((item.get("belief_assessment") or {}).get("role_safety")))
    if role_safety == "review":
        return "medium"
    if role_safety == "blocked":
        return "high"
    return "low"


def publish_posture_for_item(item: dict[str, Any]) -> str:
    risk_level = risk_level_for_item(item)
    if risk_level == "high":
        return "hold_private"
    return "owner_review_required"


def ranking_total(item: dict[str, Any]) -> float:
    ranking = item.get("ranking") or {}
    try:
        return float(ranking.get("total") or 0.0)
    except Exception:
        return 0.0


def load_social_feed_items(workspace_dir: Path | None = None) -> list[dict[str, Any]]:
    resolved_workspace = workspace_dir or workspace_root()
    payload = read_json(generated_workspace_read_path(resolved_workspace, "plans/social_feed.json")) or {}
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def load_queue_items(workspace_dir: Path | None = None) -> list[dict[str, Any]]:
    queue_path = drafts_root(workspace_dir) / "queue_01.md"
    text = read_text(queue_path)
    if not text:
        return []

    pattern = re.compile(
        r"^###\s+(?P<id>FEEZIE-\d+)\s+-\s+(?P<title>.+?)\n"
        r"- Lane:\s+`(?P<lane>[^`]+)`\n"
        r"- Format:\s+(?P<format>.+?)\n"
        r"- Core angle:\s+(?P<core_angle>.+?)\n"
        r"- Proof anchors:\n(?P<proof_anchors>(?:  - .+\n)+)"
        r"- Why now:\s+(?P<why_now>.+?)\n"
        r"- Approval status:\s+`(?P<approval_status>[^`]+)`",
        flags=re.MULTILINE,
    )

    items: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        anchors = []
        for raw_line in match.group("proof_anchors").splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("- "):
                anchors.append(stripped[2:].strip())
        items.append(
            {
                "id": match.group("id").strip(),
                "title": clean_text(match.group("title")),
                "lane": clean_text(match.group("lane")),
                "format": clean_text(match.group("format")),
                "core_angle": clean_text(match.group("core_angle")),
                "proof_anchors": anchors,
                "why_now": clean_text(match.group("why_now")),
                "approval_status": clean_text(match.group("approval_status")),
                "source_path": workspace_source_path("drafts/queue_01.md"),
            }
        )
    return items
