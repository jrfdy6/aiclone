from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.persona_promotion_targets import (
    DEFAULT_PERSONA_BUNDLE_FILES,
    TARGET_CLAIMS,
    TARGET_CONTENT_PILLARS,
    TARGET_DECISION_PRINCIPLES,
    TARGET_INITIATIVES,
    TARGET_STORIES,
    TARGET_VOICE,
    validate_persona_bundle_file,
    validate_persona_promotion_target,
)

DEFAULT_BUNDLE_FILES = list(DEFAULT_PERSONA_BUNDLE_FILES)

GENERIC_LABELS = {
    "talking point",
    "claim",
    "proof point",
    "reusable phrase",
    "framework",
    "anecdote",
    "promoted item",
}

SEED_CLAIMS = [
    {
        "claim": "Johnnie values people, process, and culture as the main levers of leadership.",
        "type": "philosophical",
        "evidence": "Recurring philosophy across persona docs and operating decisions.",
        "usage_rule": "Use as a leadership framing line when the topic is execution, adoption, or change management.",
    },
    {
        "claim": "Johnnie is an AI practitioner, not just a passive user.",
        "type": "positioning",
        "evidence": "Active AI Clone / Brain system build work and public operator framing.",
        "usage_rule": "Use when describing his relationship to AI as hands-on and operational.",
    },
    {
        "claim": "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.",
        "type": "positioning",
        "evidence": "Current-role work, AI Clone, and broader public thought-leadership direction.",
        "usage_rule": "Use as broad positioning, but avoid making every lane sound equally mature.",
    },
]

SEED_STORIES = [
    {
        "title": "Coffee and Convo",
        "story_type": "event leadership, community building, mission alignment",
        "use_when": "Use when talking about relationship-first leadership, neurodivergent advocacy, or community trust.",
        "core_point": "Johnnie creates rooms where dialogue matters, not just promotional moments.",
    },
    {
        "title": "Best Practices Initiative",
        "story_type": "team enablement",
        "use_when": "Use when talking about coaching, systems, or performance improvement.",
        "core_point": "The system improved metrics and also improved team participation.",
    },
]

SEED_INITIATIVES = [
    {
        "title": "AI Clone / Brain System",
        "status": "active",
        "purpose": "Build a durable system for restart-safe memory, evidence capture, persona development, and content assistance.",
        "value": "Proves Johnnie can turn messy AI/operator work into durable operating surfaces that support memory, planning, review, and content generation.",
        "proof": "Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
        "use_when": "Use for posts about AI systems, operator clarity, prompt-plus-agent orchestration, restart-safe memory, and shipping durable internal tools.",
    },
    {
        "title": "Fusion Academy Market Development",
        "status": "active",
        "purpose": "Strengthen referral relationships, enrollment outcomes, and family trust.",
        "value": "Keeps leadership, trust-building, and community-facing execution grounded in a live operating role rather than abstract commentary.",
        "proof": "Coffee and Convo events, outreach planning, referral-network development, and concierge family experience all make the work externally legible.",
        "use_when": "Use for posts about relationship-first leadership, referral systems, trust-building, neurodivergent advocacy, and role-grounded market development.",
    },
]

SEED_WINS = [
    "Unified Brain, Ops, daily briefs, and planner around one shared snapshot contract so operator context travels across the system instead of living in isolated tools. Use when: AI systems, workflow clarity, operating cadence, restart-safe execution.",
    "Best Practices work improved front row utilization 300% and MC Follow-up 30% while also increasing team participation. Use when: coaching, performance systems, adoption, and team enablement.",
    "Spearheaded a $1M Salesforce migration across 3 instances in a portfolio context tied to $34M in annual revenue. Use when: systems migration, change management, technical operations, and cross-functional execution.",
]


def _persona_bundle_is_usable(root: Path) -> bool:
    bundle_root = root / "knowledge" / "persona" / "feeze"
    return all(
        (bundle_root / relative_path).is_file()
        for relative_path in (
            TARGET_VOICE,
            TARGET_STORIES,
            "identity/audience_communication.md",
        )
    )


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    explicit_candidates = [
        Path(value).expanduser()
        for value in (
            os.getenv("AI_CLONE_DATA_ROOT"),
            os.getenv("AI_CLONE_ROOT"),
        )
        if value
    ]
    candidates = [*explicit_candidates, *current.parents, Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/")]
    seen: set[Path] = set()
    for parent in candidates:
        for root in (parent, parent / "app", parent / "backend"):
            if root in seen:
                continue
            seen.add(root)
            if _persona_bundle_is_usable(root):
                return root
    for parent in candidates:
        for root in (parent, parent / "app", parent / "backend"):
            if (root / "knowledge" / "persona" / "feeze" / "manifest.json").exists():
                return root
    return current.parents[2] if len(current.parents) > 2 else current.parent


def resolve_persona_bundle_root() -> Path:
    return resolve_workspace_root() / "knowledge" / "persona" / "feeze"


def _validate_bundle_root_anchor(bundle_root: Path, *, require_bundle: bool) -> tuple[Path, Path]:
    workspace_root = resolve_workspace_root()
    if workspace_root.is_symlink() or not workspace_root.is_dir():
        raise ValueError("Persona workspace root must be a non-symlink directory.")
    workspace_path = workspace_root.absolute()
    workspace_resolved = workspace_root.resolve(strict=True)
    bundle_path = bundle_root.absolute()
    try:
        relative_bundle = bundle_path.relative_to(workspace_path)
    except ValueError as exc:
        raise ValueError("Persona bundle root must be inside the configured workspace root.") from exc
    if relative_bundle == Path("."):
        raise ValueError("Persona bundle root must be below the configured workspace root.")

    current = workspace_path
    if current.is_symlink():
        raise ValueError("Persona bundle path cannot contain symlinks.")
    for part in relative_bundle.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Persona bundle path cannot contain symlinks.")

    if require_bundle:
        if not bundle_path.is_dir():
            raise ValueError("Persona bundle root must be a directory.")
        try:
            bundle_path.resolve(strict=True).relative_to(workspace_resolved)
        except ValueError as exc:
            raise ValueError("Persona bundle root escaped the configured workspace root.") from exc
    return workspace_resolved, bundle_path


def _ensure_safe_bundle_root(bundle_root: Path) -> Path:
    workspace_resolved, bundle_path = _validate_bundle_root_anchor(
        bundle_root,
        require_bundle=False,
    )
    if bundle_path.exists():
        if not bundle_path.is_dir():
            raise ValueError("Persona bundle root must be a directory.")
        _validate_bundle_root_anchor(bundle_path, require_bundle=True)
        return bundle_path.resolve(strict=True)

    missing: list[Path] = []
    cursor = bundle_path
    while not cursor.exists():
        if cursor.is_symlink():
            raise ValueError("Persona bundle path cannot contain symlinks.")
        missing.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            raise ValueError("Persona bundle root has no safe existing parent.")
        cursor = parent

    if cursor.is_symlink() or not cursor.is_dir():
        raise ValueError("Persona bundle root must have a safe directory parent.")
    for directory in reversed(missing):
        if directory.is_symlink():
            raise ValueError("Persona bundle path cannot contain symlinks.")
        directory.mkdir(exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Persona bundle path cannot contain symlinks.")
        try:
            directory.resolve(strict=True).relative_to(workspace_resolved)
        except ValueError as exc:
            raise ValueError("Persona bundle root escaped the configured workspace root.") from exc

    _validate_bundle_root_anchor(bundle_path, require_bundle=True)
    return bundle_path.resolve(strict=True)


def _resolve_safe_bundle_target(
    bundle_root: Path,
    rel_path: str,
    *,
    promotion_target: bool,
) -> Path:
    validated_path = (
        validate_persona_promotion_target(rel_path)
        if promotion_target
        else validate_persona_bundle_file(rel_path)
    )
    if validated_path is None:  # pragma: no cover - required targets never return None
        raise ValueError("Provide a canonical persona bundle file.")
    root_resolved, bundle_path = _validate_bundle_root_anchor(
        bundle_root,
        require_bundle=True,
    )
    bundle_resolved = bundle_path.resolve(strict=True)
    parts = Path(validated_path).parts
    candidate = bundle_path
    for index, part in enumerate(parts):
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Persona bundle target cannot contain symlinks.")
        if index < len(parts) - 1 and candidate.exists() and not candidate.is_dir():
            raise ValueError("Persona bundle target parent must be a directory.")

    try:
        candidate.resolve(strict=False).relative_to(bundle_resolved)
    except ValueError as exc:
        raise ValueError("Persona bundle target escaped the canonical bundle root.") from exc
    try:
        candidate.resolve(strict=False).relative_to(root_resolved)
    except ValueError as exc:  # pragma: no cover - bundle containment already enforces this
        raise ValueError("Persona bundle target escaped the configured workspace root.") from exc
    return candidate


def _ensure_safe_bundle_parent(
    bundle_root: Path,
    rel_path: str,
    *,
    promotion_target: bool,
) -> Path:
    target_path = _resolve_safe_bundle_target(
        bundle_root,
        rel_path,
        promotion_target=promotion_target,
    )
    current = bundle_root
    for part in Path(rel_path).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("Persona bundle target cannot contain symlinks.")
        current.mkdir(exist_ok=True)
        if current.is_symlink() or not current.is_dir():
            raise ValueError("Persona bundle target parent must be a non-symlink directory.")
    return _resolve_safe_bundle_target(
        bundle_root,
        rel_path,
        promotion_target=promotion_target,
    )


def _write_bundle_text(
    bundle_root: Path,
    rel_path: str,
    content: str,
    *,
    promotion_target: bool,
) -> None:
    target_path = _resolve_safe_bundle_target(
        bundle_root,
        rel_path,
        promotion_target=promotion_target,
    )
    if target_path.exists() and not target_path.is_file():
        raise ValueError("Persona bundle target must be a regular file.")
    target_path.write_text(content, encoding="utf-8")


def _frontmatter(title: str, rel_path: str) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return (
        "---\n"
        f'title: "{title}"\n'
        'persona_id: "johnnie_fields"\n'
        f'target_file: "{rel_path}"\n'
        f'generated_at: "{generated_at}"\n'
        "---\n\n"
    )


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def _normalize_inline(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).replace("\xa0", " ").split()).strip()


def _ensure_period(text: str | None) -> str:
    normalized = _normalize_inline(text)
    if not normalized:
        return ""
    return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."


def _clean_sentence(text: str | None) -> str:
    normalized = _normalize_inline(text)
    if normalized.endswith("."):
        return normalized[:-1]
    return normalized


def _metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = _normalize_inline(str(value))
    return text or None


def _read_manifest(bundle_root: Path) -> dict[str, Any]:
    manifest_path = bundle_root / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _render_claims(rows: list[dict[str, str]]) -> str:
    lines = [
        "| Claim | Type | Evidence | Usage rule |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['claim']} | {row['type']} | {row['evidence']} | {row['usage_rule']} |"
        )
    return "\n".join(lines) + "\n"


def _render_story_bank(rows: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for row in rows:
        blocks.append(
            "\n".join(
                [
                    f"## {row['title']}",
                    f"- Story type: {row['story_type']}",
                    f"- Use when: {row['use_when']}",
                    f"- Core point: {row['core_point']}",
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def _render_initiatives(rows: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for row in rows:
        use_when = row.get("use_when", "")
        blocks.append(
            "\n".join(
                [
                    f"## {row['title']}",
                    f"- Status: {row['status']}",
                    f"- Purpose: {row['purpose']}",
                    f"- Value to persona: {row['value']}",
                    f"- Public-facing proof: {row['proof']}",
                    *( [f"- Use when: {use_when}"] if use_when else [] ),
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def _render_sectioned_list(title: str, intro: str, sections: dict[str, list[str]]) -> str:
    lines = [f"# {title}", "", intro.strip(), ""]
    for section, items in sections.items():
        lines.append(f"## {section}")
        if items:
            lines.extend([f"- {item}" for item in items])
        else:
            lines.append("-")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _default_file_content(rel_path: str) -> str:
    title = rel_path.split("/")[-1].replace(".md", "").replace("_", " ")
    title = title.replace("VOICE PATTERNS", "Voice Patterns").title()
    if rel_path == TARGET_CLAIMS:
        return _frontmatter("Claims", rel_path) + _render_claims(SEED_CLAIMS)
    if rel_path == TARGET_STORIES:
        return _frontmatter("Story Bank", rel_path) + _render_story_bank(SEED_STORIES)
    if rel_path == TARGET_INITIATIVES:
        return _frontmatter("Initiatives", rel_path) + _render_initiatives(SEED_INITIATIVES)
    if rel_path == TARGET_VOICE:
        return _frontmatter("Voice Patterns", rel_path) + _render_sectioned_list(
            "Voice Patterns",
            "Reusable language patterns and stylistic constraints for public writing and responses.",
            {
                "Core Tone": [
                    "Lead with clarity, not hype.",
                    "Use direct, specific language and avoid vague corporate filler.",
                ],
                "Reusable Phrases": [
                    "people, process, and culture",
                    "operator clarity",
                    "durable systems",
                ],
                "Promoted Fragments": [],
            },
        )
    if rel_path == TARGET_DECISION_PRINCIPLES:
        return _frontmatter("Decision Principles", rel_path) + _render_sectioned_list(
            "Decision Principles",
            "Operating principles that shape judgment, prioritization, and leadership decisions.",
            {
                "Core Principles": [
                    "Favor durable systems over one-off hacks.",
                    "Protect trust, clarity, and long-term usefulness.",
                ],
                "Promoted Principles": [],
            },
        )
    if rel_path == TARGET_CONTENT_PILLARS:
        return _frontmatter("Content Pillars", rel_path) + _render_sectioned_list(
            "Content Pillars",
            "Topics and recurring angles that should shape public-facing content.",
            {
                "Core Pillars": [
                    "AI-native intrapreneurship in education",
                    "Leadership and operator clarity",
                    "Family, referral, and trust-building systems",
                ],
                "Promoted Pillars": [],
            },
        )
    if rel_path == "identity/bio_facts.md":
        return _frontmatter("Bio Facts", rel_path) + _render_sectioned_list(
            "Bio Facts",
            "Core biographical facts used across positioning and outreach.",
            {"Facts": ["Director of Admissions at Fusion Academy DC.", "10+ years in education admissions and enrollment management."]},
        )
    if rel_path == "identity/philosophy.md":
        return _frontmatter("Philosophy", rel_path) + _render_sectioned_list(
            "Philosophy",
            "Working philosophy and worldview anchors.",
            {"Core Beliefs": ["People, process, and culture are the main levers of leadership."]},
        )
    if rel_path == "identity/audience_communication.md":
        return _frontmatter("Audience Communication", rel_path) + _render_sectioned_list(
            "Audience Communication",
            "Audience-specific framing guidance.",
            {"Patterns": ["Use grounded, trust-building language with families, partners, and education operators."]},
        )
    if rel_path == "prompts/content_guardrails.md":
        return _frontmatter("Content Guardrails", rel_path) + _render_sectioned_list(
            "Content Guardrails",
            "Constraints for public content and generated writing.",
            {"Guardrails": ["Avoid hype, generic inspiration, and claims that create avoidable 'I am leaving' energy."]},
        )
    if rel_path == "prompts/outreach_playbook.md":
        return _frontmatter("Outreach Playbook", rel_path) + _render_sectioned_list(
            "Outreach Playbook",
            "Outreach positioning and communication guidance.",
            {"Patterns": ["Lead with relevance, specificity, and real context."]},
        )
    if rel_path == "prompts/channel_playbooks.md":
        return _frontmatter("Channel Playbooks", rel_path) + _render_sectioned_list(
            "Channel Playbooks",
            "Channel-specific usage notes and constraints.",
            {"Channels": ["LinkedIn should read like a real operator with lived experience, not generic advice."]},
        )
    if rel_path == "history/resume.md":
        return _frontmatter("Resume", rel_path) + _render_sectioned_list(
            "Resume",
            "Resume-aligned facts and experience summaries.",
            {"Experience": ["Oversaw 34M in annual revenue at 2U.", "Spearheaded a 1M Salesforce migration across 3 instances."]},
        )
    if rel_path == "history/timeline.md":
        return _frontmatter("Timeline", rel_path) + _render_sectioned_list(
            "Timeline",
            "Key events and professional milestones.",
            {"Milestones": ["Joined Fusion Academy DC as Director of Admissions."]},
        )
    if rel_path == "history/wins.md":
        return _frontmatter("Wins", rel_path) + _render_sectioned_list(
            "Wins",
            "Proof points and notable outcomes.",
            {"Wins": SEED_WINS},
        )
    if rel_path == "inbox/pending_deltas.md":
        return _frontmatter("Pending Deltas", rel_path) + "# Pending Persona Deltas\n\nThis inbox is reserved for future bundle-oriented review workflows.\n"
    return _frontmatter(title, rel_path) + f"# {title}\n\nThis file is part of the canonical persona bundle.\n"


def ensure_persona_bundle_scaffold() -> list[str]:
    bundle_root = resolve_persona_bundle_root()
    _ensure_safe_bundle_root(bundle_root)
    manifest = _read_manifest(bundle_root)
    requested_paths = list(
        dict.fromkeys(
            [
                *(manifest.get("identity_files") or []),
                *(manifest.get("prompt_files") or []),
                *(manifest.get("history_files") or []),
                *(manifest.get("inbox_files") or []),
                *DEFAULT_BUNDLE_FILES,
            ]
        )
    )
    rel_paths = [validate_persona_bundle_file(rel_path) for rel_path in requested_paths]

    created: list[str] = []
    for rel_path in rel_paths:
        full_path = _resolve_safe_bundle_target(
            bundle_root,
            rel_path,
            promotion_target=False,
        )
        if full_path.exists():
            continue
        _ensure_safe_bundle_parent(
            bundle_root,
            rel_path,
            promotion_target=False,
        )
        _write_bundle_text(
            bundle_root,
            rel_path,
            _default_file_content(rel_path),
            promotion_target=False,
        )
        created.append(rel_path)
    return created


def _read_existing_table_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4 or cells[0].lower() == "claim":
            continue
        rows.append({"claim": cells[0], "type": cells[1], "evidence": cells[2], "usage_rule": cells[3]})
    return rows


def _read_existing_sections(path: Path) -> tuple[str, dict[str, list[str]]]:
    title = path.stem.replace("_", " ").title()
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines():
        line = raw_line.rstrip()
        if line.startswith("# ") and title == path.stem.replace("_", " ").title():
            title = line.replace("# ", "", 1).strip()
            continue
        if line.startswith("## "):
            current_section = line.replace("## ", "", 1).strip()
            sections[current_section] = []
            continue
        if current_section and line.startswith("- "):
            sections[current_section].append(line.replace("- ", "", 1).strip())
    return title, sections


def _claim_type_for_kind(kind: str) -> str:
    normalized = _normalize_inline(kind).lower()
    if normalized == "framework":
        return "philosophical"
    if normalized == "anecdote":
        return "identity"
    if normalized == "stat":
        return "factual"
    if normalized == "phrase_candidate":
        return "positioning"
    return "philosophical"


def preferred_promotion_title(item: dict[str, Any]) -> str:
    label = _normalize_inline(str(item.get("label") or ""))
    if label and label.lower() not in GENERIC_LABELS:
        return label
    trait = _normalize_inline(str(item.get("trait") or ""))
    if trait:
        return trait[:120]
    content = _clean_sentence(str(item.get("content") or ""))
    return content[:120] or "Promoted insight"


def _write_claims(bundle_root: Path, path: Path, items: list[dict[str, Any]]) -> tuple[int, int]:
    rows = _read_existing_table_rows(path)
    seen = {_normalize_inline(row["claim"]).lower() for row in rows}
    added = 0
    for item in items:
        claim = _ensure_period(str(item.get("content") or ""))
        if not claim:
            continue
        key = _normalize_inline(claim).lower()
        if key in seen:
            continue
        rows.append(
            {
                "claim": claim,
                "type": _claim_type_for_kind(str(item.get("kind") or "")),
                "evidence": _ensure_period(str(item.get("evidence") or item.get("trait") or "")),
                "usage_rule": "Promoted from Brain review and committed into the canonical persona bundle.",
            }
        )
        seen.add(key)
        added += 1
    _write_bundle_text(
        bundle_root,
        TARGET_CLAIMS,
        _frontmatter("Claims", TARGET_CLAIMS) + _render_claims(rows),
        promotion_target=True,
    )
    return added, len(items) - added


def _write_story_bank(bundle_root: Path, path: Path, items: list[dict[str, Any]]) -> tuple[int, int]:
    sections_text = _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines()
    existing: list[dict[str, str]] = []
    title = ""
    story_type = ""
    use_when = ""
    core_point = ""
    for line in sections_text:
        if line.startswith("## "):
            if title:
                existing.append({"title": title, "story_type": story_type, "use_when": use_when, "core_point": core_point})
            title = line.replace("## ", "", 1).strip()
            story_type = ""
            use_when = ""
            core_point = ""
        elif line.startswith("- Story type:"):
            story_type = line.replace("- Story type:", "", 1).strip()
        elif line.startswith("- Use when:"):
            use_when = line.replace("- Use when:", "", 1).strip()
        elif line.startswith("- Core point:"):
            core_point = line.replace("- Core point:", "", 1).strip()
    if title:
        existing.append({"title": title, "story_type": story_type, "use_when": use_when, "core_point": core_point})

    seen = {_normalize_inline(entry["title"]).lower() for entry in existing}
    added = 0
    for item in items:
        story_title = preferred_promotion_title(item)
        key = story_title.lower()
        if key in seen:
            continue
        existing.append(
            {
                "title": story_title,
                "story_type": _normalize_inline(str(item.get("label") or "Promoted story")),
                "use_when": _ensure_period(str(item.get("owner_response_excerpt") or item.get("evidence") or "Promoted from Brain review.")),
                "core_point": _ensure_period(str(item.get("content") or "")),
            }
        )
        seen.add(key)
        added += 1
    _write_bundle_text(
        bundle_root,
        TARGET_STORIES,
        _frontmatter("Story Bank", TARGET_STORIES) + _render_story_bank(existing),
        promotion_target=True,
    )
    return added, len(items) - added


def _write_initiatives(bundle_root: Path, path: Path, items: list[dict[str, Any]]) -> tuple[int, int]:
    lines = _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines()
    existing: list[dict[str, str]] = []
    title = ""
    status = ""
    purpose = ""
    value = ""
    proof = ""
    use_when = ""
    for line in lines:
        if line.startswith("## "):
            if title:
                existing.append({"title": title, "status": status, "purpose": purpose, "value": value, "proof": proof, "use_when": use_when})
            title = line.replace("## ", "", 1).strip()
            status = ""
            purpose = ""
            value = ""
            proof = ""
            use_when = ""
        elif line.startswith("- Status:"):
            status = line.replace("- Status:", "", 1).strip()
        elif line.startswith("- Purpose:"):
            purpose = line.replace("- Purpose:", "", 1).strip()
        elif line.startswith("- Value to persona:"):
            value = line.replace("- Value to persona:", "", 1).strip()
        elif line.startswith("- Public-facing proof:"):
            proof = line.replace("- Public-facing proof:", "", 1).strip()
        elif line.startswith("- Use when:"):
            use_when = line.replace("- Use when:", "", 1).strip()
    if title:
        existing.append({"title": title, "status": status, "purpose": purpose, "value": value, "proof": proof, "use_when": use_when})

    seen = {_normalize_inline(entry["title"]).lower() for entry in existing}
    added = 0
    for item in items:
        initiative_title = preferred_promotion_title(item)
        key = initiative_title.lower()
        if key in seen:
            continue
        existing.append(
            {
                "title": initiative_title,
                "status": "active",
                "purpose": _ensure_period(str(item.get("canon_purpose") or item.get("artifact_summary") or item.get("content") or "")),
                "value": _ensure_period(
                    str(
                        item.get("canon_value")
                        or item.get("leverage_signal")
                        or item.get("capability_signal")
                        or item.get("positioning_signal")
                        or "Promoted from Brain review."
                    )
                ),
                "proof": _ensure_period(
                    str(item.get("canon_proof") or item.get("proof_signal") or item.get("artifact_summary") or item.get("evidence") or "")
                ),
                "use_when": _ensure_period(
                    str(
                        item.get("usage_rule")
                        or item.get("use_when")
                        or item.get("owner_response_excerpt")
                        or "Use when writing about this initiative's operating lesson or proof."
                    )
                ),
            }
        )
        seen.add(key)
        added += 1
    _write_bundle_text(
        bundle_root,
        TARGET_INITIATIVES,
        _frontmatter("Initiatives", TARGET_INITIATIVES) + _render_initiatives(existing),
        promotion_target=True,
    )
    return added, len(items) - added


def _write_sectioned(bundle_root: Path, path: Path, rel_path: str, items: list[dict[str, Any]]) -> tuple[int, int]:
    title, sections = _read_existing_sections(path)
    if rel_path == TARGET_VOICE:
        section_name = "Promoted Fragments"
    elif rel_path == TARGET_DECISION_PRINCIPLES:
        section_name = "Promoted Principles"
    elif rel_path == TARGET_CONTENT_PILLARS:
        section_name = "Promoted Pillars"
    else:
        section_name = "Promoted Notes"
    bucket = sections.setdefault(section_name, [])
    seen = {_normalize_inline(entry).lower() for entry in bucket}
    added = 0
    for item in items:
        content = _normalize_inline(str(item.get("content") or ""))
        if not content:
            continue
        key = content.lower()
        if key in seen:
            continue
        evidence = _normalize_inline(str(item.get("evidence") or ""))
        note = content if not evidence else f"{content} (Evidence: {evidence})"
        bucket.append(note)
        seen.add(key)
        added += 1
    intro = {
        TARGET_VOICE: "Reusable language patterns and stylistic constraints for public writing and responses.",
        TARGET_DECISION_PRINCIPLES: "Operating principles that shape judgment, prioritization, and leadership decisions.",
        TARGET_CONTENT_PILLARS: "Topics and recurring angles that should shape public-facing content.",
    }.get(rel_path, "Canonical persona notes.")
    _write_bundle_text(
        bundle_root,
        rel_path,
        _frontmatter(title, rel_path) + _render_sectioned_list(title, intro, sections),
        promotion_target=True,
    )
    return added, len(items) - added


def _story_bank_rows(path: Path) -> list[dict[str, str]]:
    sections_text = _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines()
    existing: list[dict[str, str]] = []
    title = ""
    story_type = ""
    use_when = ""
    core_point = ""
    for line in sections_text:
        if line.startswith("## "):
            if title:
                existing.append({"title": title, "story_type": story_type, "use_when": use_when, "core_point": core_point})
            title = line.replace("## ", "", 1).strip()
            story_type = ""
            use_when = ""
            core_point = ""
        elif line.startswith("- Story type:"):
            story_type = line.replace("- Story type:", "", 1).strip()
        elif line.startswith("- Use when:"):
            use_when = line.replace("- Use when:", "", 1).strip()
        elif line.startswith("- Core point:"):
            core_point = line.replace("- Core point:", "", 1).strip()
    if title:
        existing.append({"title": title, "story_type": story_type, "use_when": use_when, "core_point": core_point})
    return existing


def _section_name_for_target(rel_path: str) -> str:
    if rel_path == TARGET_VOICE:
        return "Promoted Fragments"
    if rel_path == TARGET_DECISION_PRINCIPLES:
        return "Promoted Principles"
    if rel_path == TARGET_CONTENT_PILLARS:
        return "Promoted Pillars"
    return "Promoted Notes"


def _sectioned_note_for_item(item: dict[str, Any]) -> str:
    content = _normalize_inline(str(item.get("content") or ""))
    evidence = _normalize_inline(str(item.get("evidence") or ""))
    if not content:
        return ""
    return content if not evidence else f"{content} (Evidence: {evidence})"


def promotion_item_identity(item: dict[str, Any]) -> tuple[str, str]:
    target_file = _normalize_inline(str(item.get("target_file") or item.get("targetFile") or ""))
    if not target_file:
        return "", ""
    if target_file == TARGET_CLAIMS:
        return target_file, _ensure_period(str(item.get("content") or "")).lower()
    if target_file in {TARGET_STORIES, TARGET_INITIATIVES}:
        return target_file, preferred_promotion_title(item).lower()
    return target_file, _sectioned_note_for_item(item).lower()


def _remove_claims(bundle_root: Path, path: Path, items: list[dict[str, Any]]) -> tuple[int, int]:
    rows = _read_existing_table_rows(path)
    remove_keys = {
        _ensure_period(str(item.get("content") or "")).lower()
        for item in items
        if _ensure_period(str(item.get("content") or ""))
    }
    kept = [row for row in rows if _normalize_inline(row["claim"]).lower() not in remove_keys]
    removed = len(rows) - len(kept)
    _write_bundle_text(
        bundle_root,
        TARGET_CLAIMS,
        _frontmatter("Claims", TARGET_CLAIMS) + _render_claims(kept),
        promotion_target=True,
    )
    return removed, len(items) - removed


def _remove_story_bank(bundle_root: Path, path: Path, items: list[dict[str, Any]]) -> tuple[int, int]:
    existing = _story_bank_rows(path)
    remove_titles = {
        preferred_promotion_title(item).lower()
        for item in items
        if preferred_promotion_title(item)
    }
    kept = [entry for entry in existing if _normalize_inline(entry["title"]).lower() not in remove_titles]
    removed = len(existing) - len(kept)
    _write_bundle_text(
        bundle_root,
        TARGET_STORIES,
        _frontmatter("Story Bank", TARGET_STORIES) + _render_story_bank(kept),
        promotion_target=True,
    )
    return removed, len(items) - removed


def _remove_initiatives(bundle_root: Path, path: Path, items: list[dict[str, Any]]) -> tuple[int, int]:
    lines = _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines()
    existing: list[dict[str, str]] = []
    title = ""
    status = ""
    purpose = ""
    value = ""
    proof = ""
    use_when = ""
    for line in lines:
        if line.startswith("## "):
            if title:
                existing.append({"title": title, "status": status, "purpose": purpose, "value": value, "proof": proof, "use_when": use_when})
            title = line.replace("## ", "", 1).strip()
            status = ""
            purpose = ""
            value = ""
            proof = ""
            use_when = ""
        elif line.startswith("- Status:"):
            status = line.replace("- Status:", "", 1).strip()
        elif line.startswith("- Purpose:"):
            purpose = line.replace("- Purpose:", "", 1).strip()
        elif line.startswith("- Value to persona:"):
            value = line.replace("- Value to persona:", "", 1).strip()
        elif line.startswith("- Public-facing proof:"):
            proof = line.replace("- Public-facing proof:", "", 1).strip()
        elif line.startswith("- Use when:"):
            use_when = line.replace("- Use when:", "", 1).strip()
    if title:
        existing.append({"title": title, "status": status, "purpose": purpose, "value": value, "proof": proof, "use_when": use_when})

    remove_titles = {
        preferred_promotion_title(item).lower()
        for item in items
        if preferred_promotion_title(item)
    }
    kept = [entry for entry in existing if _normalize_inline(entry["title"]).lower() not in remove_titles]
    removed = len(existing) - len(kept)
    _write_bundle_text(
        bundle_root,
        TARGET_INITIATIVES,
        _frontmatter("Initiatives", TARGET_INITIATIVES) + _render_initiatives(kept),
        promotion_target=True,
    )
    return removed, len(items) - removed


def _remove_sectioned(bundle_root: Path, path: Path, rel_path: str, items: list[dict[str, Any]]) -> tuple[int, int]:
    title, sections = _read_existing_sections(path)
    section_name = _section_name_for_target(rel_path)
    bucket = sections.setdefault(section_name, [])
    remove_notes = {
        _sectioned_note_for_item(item).lower()
        for item in items
        if _sectioned_note_for_item(item)
    }
    kept = [entry for entry in bucket if _normalize_inline(entry).lower() not in remove_notes]
    removed = len(bucket) - len(kept)
    sections[section_name] = kept
    intro = {
        TARGET_VOICE: "Reusable language patterns and stylistic constraints for public writing and responses.",
        TARGET_DECISION_PRINCIPLES: "Operating principles that shape judgment, prioritization, and leadership decisions.",
        TARGET_CONTENT_PILLARS: "Topics and recurring angles that should shape public-facing content.",
    }.get(rel_path, "Canonical persona notes.")
    _write_bundle_text(
        bundle_root,
        rel_path,
        _frontmatter(title, rel_path) + _render_sectioned_list(title, intro, sections),
        promotion_target=True,
    )
    return removed, len(items) - removed


def _group_promotion_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        raw_target = _normalize_inline(str(item.get("target_file") or item.get("targetFile") or ""))
        if not raw_target:
            continue
        target_file = validate_persona_promotion_target(raw_target)
        if target_file is None:  # pragma: no cover - required targets never return None
            raise ValueError("Provide a canonical persona promotion target file.")
        grouped.setdefault(target_file, []).append(item)
    return grouped


def write_promotion_items_to_bundle(items: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = _group_promotion_items(items)
    ensure_persona_bundle_scaffold()
    bundle_root = resolve_persona_bundle_root()
    _ensure_safe_bundle_root(bundle_root)

    written_files: list[str] = []
    file_results: dict[str, dict[str, int]] = {}
    for rel_path, target_items in grouped.items():
        full_path = _resolve_safe_bundle_target(
            bundle_root,
            rel_path,
            promotion_target=True,
        )
        if not full_path.exists():
            _ensure_safe_bundle_parent(
                bundle_root,
                rel_path,
                promotion_target=True,
            )
            _write_bundle_text(
                bundle_root,
                rel_path,
                _default_file_content(rel_path),
                promotion_target=True,
            )
        full_path = _resolve_safe_bundle_target(
            bundle_root,
            rel_path,
            promotion_target=True,
        )

        if rel_path == TARGET_CLAIMS:
            added, skipped = _write_claims(bundle_root, full_path, target_items)
        elif rel_path == TARGET_STORIES:
            added, skipped = _write_story_bank(bundle_root, full_path, target_items)
        elif rel_path == TARGET_INITIATIVES:
            added, skipped = _write_initiatives(bundle_root, full_path, target_items)
        else:
            added, skipped = _write_sectioned(bundle_root, full_path, rel_path, target_items)

        if added > 0:
            written_files.append(rel_path)
        file_results[rel_path] = {"added": added, "skipped": skipped}

    return {
        "bundle_root": str(bundle_root),
        "written_files": written_files,
        "file_results": file_results,
    }


def remove_promotion_items_from_bundle(items: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = _group_promotion_items(items)
    ensure_persona_bundle_scaffold()
    bundle_root = resolve_persona_bundle_root()
    _ensure_safe_bundle_root(bundle_root)

    written_files: list[str] = []
    file_results: dict[str, dict[str, int]] = {}
    for rel_path, target_items in grouped.items():
        full_path = _resolve_safe_bundle_target(
            bundle_root,
            rel_path,
            promotion_target=True,
        )
        if not full_path.exists():
            file_results[rel_path] = {"removed": 0, "skipped": len(target_items)}
            continue

        if rel_path == TARGET_CLAIMS:
            removed, skipped = _remove_claims(bundle_root, full_path, target_items)
        elif rel_path == TARGET_STORIES:
            removed, skipped = _remove_story_bank(bundle_root, full_path, target_items)
        elif rel_path == TARGET_INITIATIVES:
            removed, skipped = _remove_initiatives(bundle_root, full_path, target_items)
        else:
            removed, skipped = _remove_sectioned(bundle_root, full_path, rel_path, target_items)

        if removed > 0:
            written_files.append(rel_path)
        file_results[rel_path] = {"removed": removed, "skipped": skipped}

    return {
        "bundle_root": str(bundle_root),
        "written_files": written_files,
        "file_results": file_results,
    }
