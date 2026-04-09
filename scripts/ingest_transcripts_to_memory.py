#!/usr/bin/env python3
"""Compatibility ingest worker for legacy transcript drops."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from update_roadmap import append_transcript_intake_entry


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOXES = [
    WORKSPACE_ROOT / "knowledge" / "transcripts",
    WORKSPACE_ROOT / "downloads" / "transcripts",
]
DEFAULT_INGESTIONS_ROOT = WORKSPACE_ROOT / "knowledge" / "ingestions"
DEFAULT_LEGACY_INDEX = WORKSPACE_ROOT / "knowledge" / "transcripts" / "ingestions.md"
DEFAULT_LIBRARY_ROOT = WORKSPACE_ROOT / "knowledge" / "aiclone" / "transcripts"
DEFAULT_ROADMAP_PATH = WORKSPACE_ROOT / "memory" / "roadmap.md"
DEFAULT_STATE_PATH = WORKSPACE_ROOT / "logs" / "watch_transcripts_state.json"
PROCESSABLE_EXTENSIONS = {".txt", ".md"}
IGNORED_FILENAMES = {"ingestions.md", "index.md", "readme.md", "template.md"}
IGNORED_SUFFIXES = ("_summary.md",)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Continuously poll the transcript inboxes.")
    parser.add_argument("--once", action="store_true", help="Process pending drops once and exit.")
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--force", action="store_true", help="Process sources even if they match the saved state signature.")
    parser.add_argument("--path", action="append", default=[], help="Explicit transcript file to ingest.")
    parser.add_argument("--inbox", action="append", default=[], help="Inbox directory to scan for transcript drops.")
    parser.add_argument("--ingestions-root", default=str(DEFAULT_INGESTIONS_ROOT))
    parser.add_argument("--transcript-index", default=str(DEFAULT_LEGACY_INDEX))
    parser.add_argument("--library-root", default=str(DEFAULT_LIBRARY_ROOT))
    parser.add_argument("--roadmap-path", default=str(DEFAULT_ROADMAP_PATH))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    return parser.parse_args(argv)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _load_state(path: Path) -> dict[str, dict[str, int]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, dict[str, int]] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            try:
                cleaned[key] = {
                    "mtime_ns": int(value.get("mtime_ns") or 0),
                    "size": int(value.get("size") or 0),
                }
            except (TypeError, ValueError):
                continue
    return cleaned


def _save_state(path: Path, state: dict[str, dict[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _signature(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"mtime_ns": int(stat.st_mtime_ns), "size": int(stat.st_size)}


def _processable(path: Path) -> bool:
    if not path.is_file():
        return False
    name = path.name.lower()
    if name.startswith(".") or name in IGNORED_FILENAMES:
        return False
    if any(name.endswith(suffix) for suffix in IGNORED_SUFFIXES):
        return False
    return path.suffix.lower() in PROCESSABLE_EXTENSIONS


def _strip_frontmatter(raw: str) -> str:
    if not raw.startswith("---\n"):
        return raw
    marker = "\n---\n"
    if marker not in raw:
        return raw
    return raw.split(marker, 1)[1]


def _sanitize_transcript(raw: str) -> str:
    text = _strip_frontmatter(raw).replace("\r\n", "\n")
    lines = []
    blank = False
    for line in text.splitlines():
        clean = re.sub(r"[ \t]+", " ", line).strip()
        if not clean:
            if lines and not blank:
                lines.append("")
            blank = True
            continue
        lines.append(clean)
        blank = False
    return "\n".join(lines).strip()


def _extract_sentences(text: str, limit: int = 2) -> list[str]:
    compact = " ".join(text.split())
    if not compact:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", compact)
    results = [piece.strip() for piece in pieces if piece.strip()]
    if results:
        return results[:limit]
    words = compact.split()
    return [" ".join(words[: min(len(words), 40)])]


def _summary_path_for(source_path: Path) -> Path | None:
    if source_path.suffix.lower() != ".txt":
        return None
    candidate = source_path.with_name(f"{source_path.stem}_summary.md")
    if candidate.exists():
        return candidate
    return None


def _extract_title(summary_text: str, source_path: Path) -> str:
    for line in summary_text.splitlines():
        clean = line.strip()
        if clean.startswith("# "):
            return clean[2:].strip()
    stem = source_path.stem.replace("_summary", "")
    human = re.sub(r"[_-]+", " ", stem).strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", stem):
        return f"YouTube Transcript {stem}"
    return human or source_path.name


def _extract_url(summary_text: str, source_path: Path) -> str:
    match = re.search(r"https?://\S+", summary_text)
    if match:
        return match.group(0).rstrip(").,")
    stem = source_path.stem.replace("_summary", "")
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", stem):
        return f"https://www.youtube.com/watch?v={stem}"
    return "unknown"


def _derive_summary(summary_text: str, transcript_text: str) -> str:
    summary_lines = []
    for line in summary_text.splitlines():
        clean = line.strip()
        normalized = clean.lstrip("- ").strip()
        lowered = normalized.lower()
        if lowered.startswith("**link:**") or lowered.startswith("**uploaded:**"):
            continue
        if clean.startswith("- **") or clean.startswith("- "):
            summary_lines.append(normalized)
        elif clean and not clean.startswith("#") and not clean.startswith("##") and not clean.startswith("**Uploaded:**") and not clean.startswith("**Link:**"):
            summary_lines.append(clean)
        if len(summary_lines) >= 2:
            break
    if summary_lines:
        return " ".join(summary_lines)
    sentences = _extract_sentences(transcript_text, limit=2)
    return " ".join(sentences).strip()


def _slugify(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    return lowered or "transcript"


def _stable_slug(title: str, source_path: Path, root: Path) -> str:
    rel = _relative(source_path, root)
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
    return f"{_slugify(title)[:72]}_{digest}"


def _yaml_lines_for_list(items: list[str]) -> list[str]:
    if not items:
        return ["[]"]
    return [f"- {json.dumps(item)}" for item in items]


def _write_normalized_markdown(
    *,
    source_path: Path,
    transcript_text: str,
    summary_text: str,
    title: str,
    source_url: str,
    slug: str,
    asset_dir: Path,
    repo_root: Path,
    captured_at: datetime,
    raw_files: list[Path],
) -> Path:
    normalized_path = asset_dir / "normalized.md"
    rel_raw_files = [_relative(path, asset_dir) for path in raw_files]
    summary_origin = "provided" if summary_text else "generated"
    summary = " ".join(summary_text.split()).strip()
    word_count = len(transcript_text.split())
    frontmatter = [
        "---",
        f"id: {json.dumps(slug)}",
        f"title: {json.dumps(title)}",
        'source_type: "transcript"',
        f"captured_at: {json.dumps(captured_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'))}",
        "topics:",
        "- transcript",
        "tags:",
        "- auto_ingested",
        "- needs_review",
        f"source_url: {json.dumps(source_url)}",
        "author: \"unknown\"",
        "raw_files:",
        *[f"- {json.dumps(path)}" for path in rel_raw_files],
        f"word_count: {word_count}",
        f"summary: {json.dumps(summary)}",
        f"summary_origin: {json.dumps(summary_origin)}",
        f"structured_summary: {json.dumps(summary)}",
        "---",
        "",
        "# Structured Extraction",
        "",
        "## Summary",
        summary or "Pending summary.",
        "",
        "# Clean Transcript / Document",
        transcript_text or "Pending transcript.",
        "",
        "## Source Paths",
        f"- Transcript source: `{_relative(source_path, repo_root)}`",
        f"- Canonical ingestion: `{_relative(normalized_path, repo_root)}`",
    ]
    normalized_path.write_text("\n".join(frontmatter).rstrip() + "\n", encoding="utf-8")
    return normalized_path


def _write_library_note(
    *,
    library_root: Path,
    title: str,
    source_path: Path,
    source_url: str,
    captured_at: datetime,
    summary: str,
    note_slug: str,
    repo_root: Path,
) -> Path:
    library_root.mkdir(parents=True, exist_ok=True)
    note_name = f"{captured_at.astimezone(timezone.utc).date().isoformat()}_{note_slug}.md"
    note_path = library_root / note_name
    lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"source: {json.dumps('legacy transcript watcher compatibility ingest')}",
        f"received: {captured_at.astimezone(timezone.utc).date().isoformat()}",
        f"raw_path: {json.dumps(_relative(source_path, repo_root))}",
        "tags: [transcript, auto_ingested, needs_review]",
        "---",
        "",
        "## Summary",
        f"- {summary or 'Pending summary.'}",
        "",
        "## Key Requirements / Directives",
        "1. Review the canonical ingestion before routing tasks or promotions.",
        "2. Confirm whether this source should affect roadmap, backlog, or persona lanes.",
        "",
        "## Follow-ups / Tasks",
        "- [ ] Review build implications in OpenClaw.",
        "- [ ] Review persona implications in Railway.",
        "",
        "## Notes",
        f"- Source URL: {source_url}",
    ]
    note_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return note_path


def _append_table_row(path: Path, header: str, divider: str, row: str, dedupe_term: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if dedupe_term and dedupe_term in existing:
        return
    if not existing.strip():
        path.write_text(f"{header}\n{divider}\n{row}\n", encoding="utf-8")
        return
    suffix = "" if existing.endswith("\n") else "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{suffix}{row}\n")


def _update_legacy_index(
    *,
    transcript_index: Path,
    captured_at: datetime,
    title: str,
    source_url: str,
    transcript_path: Path,
    summary_path: Path | None,
    repo_root: Path,
) -> None:
    row = " | ".join(
        [
            captured_at.astimezone(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
            title,
            source_url if source_url != "unknown" else "n/a",
            _relative(transcript_path, repo_root),
            _relative(summary_path, repo_root) if summary_path else "n/a",
            "auto_ingested",
        ]
    )
    _append_table_row(
        transcript_index,
        "# YouTube Transcript Ingestions\n\n| Date (ET) | Video | URL | Transcript | Summary | Tags |",
        "|-----------|-------|-----|------------|---------|------|",
        f"| {row} |",
        _relative(transcript_path, repo_root),
    )


def _update_library_index(
    *,
    library_root: Path,
    captured_at: datetime,
    title: str,
    summary: str,
    note_path: Path,
) -> None:
    index_path = library_root / "INDEX.md"
    row = " | ".join(
        [
            captured_at.astimezone(timezone.utc).date().isoformat(),
            title,
            "transcript, auto_ingested",
            summary[:120] or "Pending summary",
            f"[notes]({note_path.name})",
        ]
    )
    _append_table_row(
        index_path,
        "# Transcript Index\n\n| Date       | Title / Source                         | Tags                 | Summary | Link |",
        "|------------|----------------------------------------|----------------------|---------|------|",
        f"| {row} |",
        note_path.name,
    )


def ingest_source(
    *,
    source_path: Path,
    ingestions_root: Path,
    transcript_index: Path,
    library_root: Path,
    roadmap_path: Path,
    repo_root: Path,
) -> Path:
    raw_text = source_path.read_text(encoding="utf-8", errors="replace")
    transcript_text = _sanitize_transcript(raw_text)
    summary_path = _summary_path_for(source_path)
    summary_text = summary_path.read_text(encoding="utf-8", errors="replace") if summary_path else ""
    title = _extract_title(summary_text, source_path)
    source_url = _extract_url(summary_text, source_path)
    summary = _derive_summary(summary_text, transcript_text)
    captured_at = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)
    slug = _stable_slug(title, source_path, repo_root)

    asset_dir = ingestions_root / captured_at.strftime("%Y") / captured_at.strftime("%m") / slug
    raw_dir = asset_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_transcript_name = "transcript" + source_path.suffix.lower()
    raw_transcript_path = raw_dir / raw_transcript_name
    shutil.copy2(source_path, raw_transcript_path)

    copied_files = [raw_transcript_path]
    if summary_path:
        raw_summary_path = raw_dir / summary_path.name
        shutil.copy2(summary_path, raw_summary_path)
        copied_files.append(raw_summary_path)

    normalized_path = _write_normalized_markdown(
        source_path=source_path,
        transcript_text=transcript_text,
        summary_text=summary,
        title=title,
        source_url=source_url,
        slug=slug,
        asset_dir=asset_dir,
        repo_root=repo_root,
        captured_at=captured_at,
        raw_files=copied_files,
    )
    note_path = _write_library_note(
        library_root=library_root,
        title=title,
        source_path=source_path,
        source_url=source_url,
        captured_at=captured_at,
        summary=summary,
        note_slug=slug,
        repo_root=repo_root,
    )
    _update_library_index(
        library_root=library_root,
        captured_at=captured_at,
        title=title,
        summary=summary,
        note_path=note_path,
    )
    _update_legacy_index(
        transcript_index=transcript_index,
        captured_at=captured_at,
        title=title,
        source_url=source_url,
        transcript_path=source_path,
        summary_path=summary_path,
        repo_root=repo_root,
    )
    append_transcript_intake_entry(
        roadmap_path=roadmap_path,
        title=title,
        summary=summary,
        source_path=_relative(source_path, repo_root),
        normalized_path=_relative(normalized_path, repo_root),
    )
    print(f"Ingested transcript: {_relative(source_path, repo_root)} -> {_relative(normalized_path, repo_root)}")
    return normalized_path


def _candidate_paths(inboxes: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for inbox in inboxes:
        if not inbox.exists():
            continue
        for path in sorted(inbox.iterdir()):
            if _processable(path):
                candidates.append(path)
    return candidates


def _process_batch(
    *,
    paths: list[Path],
    state: dict[str, dict[str, int]],
    force: bool,
    ingestions_root: Path,
    transcript_index: Path,
    library_root: Path,
    roadmap_path: Path,
    repo_root: Path,
) -> int:
    processed = 0
    for source_path in paths:
        if not _processable(source_path):
            continue
        key = str(source_path.resolve())
        signature = _signature(source_path)
        if not force and state.get(key) == signature:
            continue
        ingest_source(
            source_path=source_path,
            ingestions_root=ingestions_root,
            transcript_index=transcript_index,
            library_root=library_root,
            roadmap_path=roadmap_path,
            repo_root=repo_root,
        )
        state[key] = signature
        processed += 1
    return processed


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = WORKSPACE_ROOT
    ingestions_root = Path(args.ingestions_root).expanduser()
    transcript_index = Path(args.transcript_index).expanduser()
    library_root = Path(args.library_root).expanduser()
    roadmap_path = Path(args.roadmap_path).expanduser()
    state_path = Path(args.state_path).expanduser()
    inboxes = [Path(item).expanduser() for item in (args.inbox or [])] or list(DEFAULT_INBOXES)
    state = _load_state(state_path)

    def run_batch(explicit_paths: list[Path] | None = None) -> int:
        paths = explicit_paths if explicit_paths is not None else _candidate_paths(inboxes)
        return _process_batch(
            paths=paths,
            state=state,
            force=args.force,
            ingestions_root=ingestions_root,
            transcript_index=transcript_index,
            library_root=library_root,
            roadmap_path=roadmap_path,
            repo_root=repo_root,
        )

    explicit_paths = [Path(item).expanduser() for item in args.path]
    if explicit_paths:
        run_batch(explicit_paths)
        _save_state(state_path, state)
        return 0

    if args.watch and not args.once:
        while True:
            processed = run_batch()
            if processed:
                _save_state(state_path, state)
            time.sleep(args.poll_seconds)

    run_batch()
    _save_state(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
