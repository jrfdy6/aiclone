#!/usr/bin/env python3
"""Deterministic task bodies used by Codex-native launchd wrappers."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from runtime_http import control_plane_headers, control_plane_token
from runtime_paths import PROJECT_ROOT, STATE_ROOT
from scheduled_automation_runtime import (
    ScheduledTaskError,
    TaskOutcome,
    atomic_write_text,
    parse_json_output,
    run_project_python,
)


LOCAL_TZ = ZoneInfo("America/New_York")
DEFAULT_FRONTEND_URL = os.getenv(
    "AICLONE_FRONTEND_URL",
    "https://aiclone-frontend-production.up.railway.app",
)
DATE_FILE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:-[A-Za-z0-9._-]+)?\.md$")
CONFLICT_MARKERS = ("<<<<<<< ", "=======", ">>>>>>> ")
CRITICAL_MEMORY_FILES = ("SOUL.md", "AGENTS.md", "USER.md", "TOOLS.md", "MEMORY.md")
CRITICAL_SIZE_LIMIT = 20_000
HOT_MEMORY_SIZE_LIMIT = 50_000
ARCHIVE_AFTER_DAYS = 30
RECENT_WRITE_GUARD_HOURS = 48
PURGE_REVIEW_AFTER_DAYS = 180


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _first_line(value: Any, fallback: str) -> str:
    for line in str(value or "").splitlines():
        cleaned = " ".join(line.split()).strip()
        if cleaned:
            return cleaned[:300]
    return fallback


def _relative_project_path(path: Path, *, project_root: Path = PROJECT_ROOT) -> str:
    resolved_root = project_root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ScheduledTaskError("Task artifact escaped the project root.") from exc


def _require_contained_path(root: Path, candidate: Path, *, label: str) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ScheduledTaskError(f"{label} escaped its allowed root.") from exc
    return resolved_candidate


def build_morning_daily_brief(*, timeout_seconds: int = 180) -> TaskOutcome:
    command = run_project_python(
        "build_morning_daily_brief.py",
        ("--append", "--json"),
        timeout_seconds=timeout_seconds,
    )
    payload = parse_json_output(command.stdout)
    markdown = str(payload.get("markdown") or "").strip()
    brief_date = str(payload.get("date") or "").strip()
    if not markdown or not brief_date:
        raise ScheduledTaskError("Morning daily brief builder returned an incomplete payload.")
    expected_date = datetime.now(LOCAL_TZ).date().isoformat()
    if brief_date != expected_date:
        raise ScheduledTaskError(
            f"Morning daily brief builder returned {brief_date}; expected current local date {expected_date}."
        )
    artifact = PROJECT_ROOT / "memory" / "daily-briefs.md"
    if not artifact.is_file():
        raise ScheduledTaskError("Morning daily brief artifact was not written.")
    sync_command = run_project_python(
        "sync_daily_briefs.py",
        ("--expected-latest-date", brief_date),
        timeout_seconds=min(timeout_seconds, 60),
    )
    sync_payload = parse_json_output(sync_command.stdout)
    if sync_payload.get("success") is not True:
        raise ScheduledTaskError("Morning daily brief Railway sync did not confirm success.")
    synced_date = str(sync_payload.get("latest_brief_date") or "").strip()
    if synced_date and synced_date != brief_date:
        raise ScheduledTaskError(
            f"Morning daily brief Railway sync confirmed {synced_date}; expected {brief_date}."
        )
    return TaskOutcome(
        ok=True,
        summary=_first_line(markdown, "Morning daily brief updated."),
        metadata={
            "brief_date": brief_date,
            "artifact": _relative_project_path(artifact),
            "content_sha256": _sha256_text(markdown),
            "content_chars": len(markdown),
            "railway_sync": "ok",
            "railway_sync_count": int(sync_payload.get("count") or 0),
        },
    )


def build_progress_pulse(*, timeout_seconds: int = 150) -> TaskOutcome:
    command = run_project_python(
        "build_progress_pulse_digest.py",
        timeout_seconds=timeout_seconds,
    )
    digest = command.stdout.strip()
    if not digest:
        raise ScheduledTaskError("Progress pulse builder returned empty output.")
    if digest == "NO_REPLY":
        return TaskOutcome(
            ok=True,
            summary="Progress pulse found no material change.",
            metadata={"material_change": False, "artifact": None},
        )

    artifact = STATE_ROOT / "automations" / "reports" / "progress_pulse_latest.md"
    atomic_write_text(artifact, digest.rstrip() + "\n", mode=0o600)
    return TaskOutcome(
        ok=True,
        summary=_first_line(digest, "Progress pulse updated."),
        metadata={
            "material_change": True,
            "artifact": str(artifact),
            "content_sha256": _sha256_text(digest),
            "content_chars": len(digest),
        },
    )


def build_dream_cycle(*, timeout_seconds: int = 240) -> TaskOutcome:
    command = run_project_python(
        "build_dream_cycle_snapshot.py",
        ("--write", "--json"),
        timeout_seconds=timeout_seconds,
    )
    payload = parse_json_output(command.stdout)
    summary = str(payload.get("summary_markdown") or "").strip()
    cycle_date = str(payload.get("date") or "").strip()
    if not summary or not cycle_date:
        raise ScheduledTaskError("Dream cycle builder returned an incomplete payload.")
    artifact = PROJECT_ROOT / "memory" / "dream_cycle_log.md"
    if not artifact.is_file():
        raise ScheduledTaskError("Dream cycle log was not written.")
    return TaskOutcome(
        ok=True,
        summary=_first_line(summary, "Dream cycle snapshot updated."),
        metadata={
            "cycle_date": cycle_date,
            "artifact": _relative_project_path(artifact),
            "summary_sha256": _sha256_text(summary),
        },
    )


def _memory_files(project_root: Path) -> list[Path]:
    memory_root = (project_root / "memory").resolve()
    if not memory_root.is_dir():
        raise ScheduledTaskError("Project memory directory is unavailable.")
    return sorted(
        path
        for path in memory_root.glob("*.md")
        if path.is_file() and not path.is_symlink()
    )


def _contains_conflict_marker(path: Path) -> bool:
    if path.stat().st_size > 5_000_000:
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    return any(marker in content for marker in CONFLICT_MARKERS)


def _render_memory_health_report(report: dict[str, Any]) -> str:
    lines = [
        f"# Codex Memory Health — {report['date']}",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        f"- Memory backend: `{report['index'].get('backend') or 'sqlite_fts5'}`",
        f"- Indexed files: `{report['index'].get('files') or 0}`",
        f"- Index age (hours): `{report['index'].get('hours_since_update')}`",
        f"- Recall probe results: `{report['index'].get('probe_result_count') or 0}`",
        "",
        "## Critical Files",
        "",
        "| File | Bytes | Lines | Status |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in report["critical_files"]:
        lines.append(
            f"| `{item['path']}` | {item.get('bytes', 0)} | {item.get('lines', 0)} | `{item['status']}` |"
        )
    lines.extend(["", "## Findings", ""])
    if report["findings"]:
        lines.extend(f"- {item}" for item in report["findings"])
    else:
        lines.append("- No memory integrity issue requires action.")
    return "\n".join(lines).rstrip() + "\n"


def inspect_memory_health(
    index_report: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
    now: datetime | None = None,
) -> tuple[dict[str, Any], Path]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    local_date = current.astimezone(LOCAL_TZ).date().isoformat()
    critical_rows: list[dict[str, Any]] = []
    missing_critical: list[str] = []
    oversized_critical: list[str] = []
    for name in CRITICAL_MEMORY_FILES:
        path = project_root / name
        if path.is_symlink():
            missing_critical.append(name)
            critical_rows.append({"path": name, "bytes": 0, "lines": 0, "status": "unsafe_symlink"})
            continue
        if not path.is_file():
            missing_critical.append(name)
            critical_rows.append({"path": name, "bytes": 0, "lines": 0, "status": "missing"})
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        size = path.stat().st_size
        status = "warn" if size > CRITICAL_SIZE_LIMIT else "ok"
        if status == "warn":
            oversized_critical.append(name)
        critical_rows.append(
            {
                "path": name,
                "bytes": size,
                "lines": len(content.splitlines()),
                "status": status,
            }
        )

    memory_files = _memory_files(project_root)
    large_hot = [
        _relative_project_path(path, project_root=project_root)
        for path in memory_files
        if path.parent == project_root / "memory" and path.stat().st_size > HOT_MEMORY_SIZE_LIMIT
    ]
    conflicts = [
        _relative_project_path(path, project_root=project_root)
        for path in memory_files
        if _contains_conflict_marker(path)
    ]
    daily_path = project_root / "memory" / f"{local_date}.md"
    daily_exists = daily_path.is_file() and not daily_path.is_symlink()
    findings: list[str] = []
    alert = False
    warn = False
    if str(index_report.get("status") or "") != "ok" or not index_report.get("ready"):
        findings.append("The local SQLite memory index or its recall probe needs repair.")
        alert = True
    if missing_critical:
        findings.append(f"Missing critical files: {', '.join(missing_critical)}.")
        alert = True
    if conflicts:
        findings.append(f"Merge-conflict markers found in: {', '.join(conflicts[:10])}.")
        alert = True
    if oversized_critical:
        findings.append(f"Critical files above {CRITICAL_SIZE_LIMIT} bytes: {', '.join(oversized_critical)}.")
        warn = True
    if large_hot:
        findings.append(f"Hot memory files above {HOT_MEMORY_SIZE_LIMIT} bytes: {', '.join(large_hot[:10])}.")
        warn = True
    if not daily_exists:
        findings.append(f"Today's daily memory log is missing: memory/{local_date}.md.")
        warn = True

    status = "alert" if alert else "warn" if warn else "ok"
    report = {
        "schema_version": "codex_memory_health/v1",
        "status": status,
        "date": local_date,
        "generated_at_utc": current.isoformat().replace("+00:00", "Z"),
        "index": index_report,
        "critical_files": critical_rows,
        "large_hot_files": large_hot,
        "conflict_files": conflicts,
        "daily_log_exists": daily_exists,
        "findings": findings,
    }
    report_path = project_root / "memory" / "reports" / f"memory_health_{local_date}.md"
    atomic_write_text(report_path, _render_memory_health_report(report), mode=0o600)
    return report, report_path


def build_memory_health(*, timeout_seconds: int = 300) -> TaskOutcome:
    command = run_project_python(
        "codex_memory_freshness_check.py",
        ("--sync",),
        timeout_seconds=timeout_seconds,
        allowed_exit_codes={0, 4},
    )
    index_report = parse_json_output(command.stdout)
    report, report_path = inspect_memory_health(index_report)
    status = str(report["status"])
    return TaskOutcome(
        ok=status != "alert",
        action_required=status != "ok",
        error="Memory health has blocking findings." if status == "alert" else None,
        summary=f"Memory health is {status}; {len(report['findings'])} finding(s).",
        metadata={
            "health_status": status,
            "artifact": _relative_project_path(report_path),
            "indexed_files": index_report.get("files"),
            "probe_result_count": index_report.get("probe_result_count"),
            "finding_count": len(report["findings"]),
        },
    )


def _parse_memory_date(path: Path) -> date | None:
    match = DATE_FILE_RE.fullmatch(path.name)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _upsert_sweep_line(text: str, *, run_date: str, line: str) -> str:
    heading = "## Codex-native sweeps"
    if heading not in text:
        return text.rstrip() + f"\n\n{heading}\n{line}\n"
    pattern = re.compile(rf"(?m)^- {re.escape(run_date)}:.*$")
    if pattern.search(text):
        return pattern.sub(line, text).rstrip() + "\n"
    return text.rstrip() + f"\n{line}\n"


def _manifest_after_archive(
    existing: str,
    *,
    manifest_month: str,
    run_date: str,
    moved: list[dict[str, str]],
    purge_candidates: int,
    anomalies: list[str],
) -> str:
    text = existing.strip() or f"# Memory Archive Manifest — {manifest_month}"
    archive_heading = "## Codex-native archived files"
    if archive_heading not in text:
        text = text.rstrip() + f"\n\n{archive_heading}\n"
    for item in moved:
        marker = f"`{item['destination']}` sha256=`{item['sha256']}`"
        if marker in text:
            continue
        text = text.rstrip() + (
            f"\n- `{item['source']}` -> `{item['destination']}` "
            f"sha256=`{item['sha256']}` archived_at=`{item['archived_at']}`\n"
        )
    sweep_line = (
        f"- {run_date}: archived={len(moved)}; purge_review_candidates={purge_candidates}; "
        f"anomalies={len(anomalies)}"
    )
    return _upsert_sweep_line(text, run_date=run_date, line=sweep_line)


def archive_memory(
    *,
    project_root: Path = PROJECT_ROOT,
    now: datetime | None = None,
) -> TaskOutcome:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = current.astimezone(LOCAL_TZ).date()
    memory_root = (project_root / "memory").resolve()
    archive_root = _require_contained_path(
        memory_root,
        memory_root / "archive",
        label="Memory archive path",
    )

    candidates: list[tuple[Path, date]] = []
    recently_modified: list[str] = []
    anomalies: list[str] = []
    for source in sorted(memory_root.glob("*.md")):
        if source.is_symlink():
            if _parse_memory_date(source) is not None:
                anomalies.append(f"Unsafe symbolic-link daily file was retained: {source.name}.")
            continue
        if not source.is_file():
            continue
        file_date = _parse_memory_date(source)
        if file_date is None or (today - file_date).days <= ARCHIVE_AFTER_DAYS:
            continue
        modified_at = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
        if current - modified_at < timedelta(hours=RECENT_WRITE_GUARD_HOURS):
            recently_modified.append(source.name)
            continue
        destination = _require_contained_path(
            archive_root,
            archive_root / f"{file_date.year:04d}" / f"{file_date.month:02d}" / source.name,
            label="Memory archive destination",
        )
        if destination.exists():
            if _sha256_file(destination) == _sha256_file(source):
                anomalies.append(f"Duplicate archive target already exists for {source.name}; source retained.")
            else:
                anomalies.append(f"Conflicting archive target already exists for {source.name}; source retained.")
            continue
        candidates.append((source, file_date))

    moved_pairs: list[tuple[Path, Path]] = []
    moved_rows: list[dict[str, str]] = []
    manifest_month = today.strftime("%Y-%m")
    manifest_path = _require_contained_path(
        archive_root,
        archive_root / "manifests" / f"{manifest_month}.md",
        label="Memory archive manifest",
    )
    existing_manifest = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""
    try:
        for source, file_date in candidates:
            destination = _require_contained_path(
                archive_root,
                archive_root / f"{file_date.year:04d}" / f"{file_date.month:02d}" / source.name,
                label="Memory archive destination",
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            checksum = _sha256_file(source)
            source.replace(destination)
            if _sha256_file(destination) != checksum:
                raise ScheduledTaskError(f"Archive checksum verification failed for {source.name}.")
            moved_pairs.append((source, destination))
            moved_rows.append(
                {
                    "source": f"memory/{source.name}",
                    "destination": _relative_project_path(destination, project_root=project_root),
                    "sha256": checksum,
                    "archived_at": current.isoformat().replace("+00:00", "Z"),
                }
            )

        purge_candidates = 0
        for archived in archive_root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*.md"):
            file_date = _parse_memory_date(archived)
            if file_date is not None and (today - file_date).days > PURGE_REVIEW_AFTER_DAYS:
                purge_candidates += 1
        manifest = _manifest_after_archive(
            existing_manifest,
            manifest_month=manifest_month,
            run_date=today.isoformat(),
            moved=moved_rows,
            purge_candidates=purge_candidates,
            anomalies=anomalies,
        )
        atomic_write_text(manifest_path, manifest, mode=0o600)
    except Exception:
        for source, destination in reversed(moved_pairs):
            if destination.exists() and not source.exists():
                destination.replace(source)
        raise

    retained_dates = [
        parsed
        for path in memory_root.glob("*.md")
        if (parsed := _parse_memory_date(path)) is not None
    ]
    oldest_retained = min(retained_dates).isoformat() if retained_dates else None
    action_required = bool(anomalies or purge_candidates)
    return TaskOutcome(
        ok=True,
        action_required=action_required,
        summary=(
            f"Memory archive sweep moved {len(moved_rows)} file(s); "
            f"{purge_candidates} old archive file(s) require review."
        ),
        metadata={
            "archived_count": len(moved_rows),
            "purged_count": 0,
            "purge_review_candidates": purge_candidates,
            "recent_write_guard_count": len(recently_modified),
            "anomaly_count": len(anomalies),
            "oldest_retained_hot_date": oldest_retained,
            "manifest": _relative_project_path(manifest_path, project_root=project_root),
        },
    )


def _validated_service_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip())
    local = parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.scheme not in ({"http", "https"} if local else {"https"}):
        raise ScheduledTaskError("Service health URL must use HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ScheduledTaskError("Service health URL is invalid.")
    return value.rstrip("/")


def _http_check(
    *,
    name: str,
    url: str,
    authenticated: bool,
    timeout_seconds: int,
    attempts: int = 2,
) -> dict[str, Any]:
    if authenticated and not control_plane_token():
        return {
            "name": name,
            "ok": False,
            "authenticated": True,
            "error": "Control-plane service token is unavailable.",
        }
    headers = {"Accept": "application/json"}
    if authenticated:
        headers = control_plane_headers(headers)
    last_error: str | None = None
    for attempt in range(attempts):
        started = time.monotonic()
        try:
            request = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response.read(4096)
                status_code = int(getattr(response, "status", 200))
            return {
                "name": name,
                "ok": 200 <= status_code < 400,
                "authenticated": authenticated,
                "status_code": status_code,
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = " ".join(str(exc).split())[:240]
            if attempt + 1 < attempts:
                time.sleep(1)
    return {
        "name": name,
        "ok": False,
        "authenticated": authenticated,
        "error": last_error or "Health request failed.",
    }


def check_external_services(
    *,
    api_url: str,
    frontend_url: str = DEFAULT_FRONTEND_URL,
    timeout_seconds: int = 15,
    now: datetime | None = None,
) -> TaskOutcome:
    if timeout_seconds < 1 or timeout_seconds > 60:
        raise ScheduledTaskError("Service health timeout must be between 1 and 60 seconds.")
    backend = _validated_service_url(api_url)
    frontend = _validated_service_url(frontend_url)
    checks = [
        _http_check(
            name="backend_public_health",
            url=f"{backend}/health",
            authenticated=False,
            timeout_seconds=timeout_seconds,
        ),
        _http_check(
            name="backend_authenticated_health",
            url=f"{backend}/api/open-brain/health",
            authenticated=True,
            timeout_seconds=timeout_seconds,
        ),
        _http_check(
            name="frontend_login",
            url=f"{frontend}/login",
            authenticated=False,
            timeout_seconds=timeout_seconds,
        ),
    ]
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    failed = [item for item in checks if not item.get("ok")]
    report = {
        "schema_version": "codex_external_service_health/v1",
        "generated_at_utc": generated_at.isoformat().replace("+00:00", "Z"),
        "status": "ok" if not failed else "failed",
        "checks": checks,
    }
    report_path = STATE_ROOT / "automations" / "reports" / "external_service_health_latest.json"
    atomic_write_text(report_path, json.dumps(report, indent=2) + "\n", mode=0o600)
    return TaskOutcome(
        ok=not failed,
        action_required=bool(failed),
        error=(f"{len(failed)} service health check(s) failed." if failed else None),
        summary=f"External service health: {len(checks) - len(failed)}/{len(checks)} checks passed.",
        metadata={
            "artifact": str(report_path),
            "check_count": len(checks),
            "failed_count": len(failed),
            "failed_checks": [str(item.get("name")) for item in failed],
        },
    )
