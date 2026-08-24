#!/usr/bin/env python3
"""Refresh the LinkedIn workspace social feed (and optional safe sources)."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPTS_ROOT = REPO_ROOT / "scripts" / "personal-brand"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
MAX_COMPACT_DIAGNOSTICS = 20

for candidate in (REPO_ROOT / "backend", REPO_ROOT):
    if (candidate / "app").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.services.youtube_watchlist_service import sync_watchlist_auto_ingest
from runtime_http import control_plane_headers, open_control_plane_request, validate_control_plane_url


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _emit_compact_event(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, "at": _now_iso(), **fields}, sort_keys=True), flush=True)


def _safe_identifier(value: Any, *, fallback: str, limit: int = 64) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()).strip("_.-")
    return (cleaned or fallback)[:limit]


def _diagnostic_type(value: Any) -> str:
    normalized = str(value or "").lower()
    http_status = re.search(r"\b([1-5][0-9]{2})\b", normalized)
    if http_status:
        return f"http_{http_status.group(1)}"
    if "timeout" in normalized or "timed out" in normalized:
        return "timeout"
    if "permission" in normalized or "unauthorized" in normalized or "forbidden" in normalized:
        return "access_error"
    if "not found" in normalized or "no such file" in normalized:
        return "not_found"
    if "json" in normalized or "parse" in normalized or "decode" in normalized:
        return "parse_error"
    if "connection" in normalized or "network" in normalized or "dns" in normalized or "url" in normalized:
        return "network_error"
    return "runtime_error"


def run_script(
    script_path: Path,
    *extra_args: str,
    required: bool = True,
    compact_output: bool = False,
) -> bool:
    command = [sys.executable, str(script_path), *extra_args]
    relative_path = script_path.relative_to(REPO_ROOT)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        if compact_output:
            _emit_compact_event(
                "feezie_refresh_step",
                step=relative_path.as_posix(),
                status="error",
                exit_code=exc.returncode,
                required=required,
            )
        if required:
            raise
        print(f"warning: optional step failed ({relative_path}): exit={exc.returncode}", file=sys.stderr)
        return False
    if compact_output:
        _emit_compact_event(
            "feezie_refresh_step",
            step=relative_path.as_posix(),
            status="ok",
            exit_code=0,
            required=required,
        )
    return True


def run_fetcher(fetcher: Literal["reddit", "rss"], *, compact_output: bool = False) -> None:
    run_script(
        SCRIPTS_ROOT / f"fetch_{fetcher}_signals.py",
        compact_output=compact_output,
    )


def run_market_signal_archive_sync(*, compact_output: bool = False) -> None:
    run_script(SCRIPTS_ROOT / "sync_market_signal_archive.py", compact_output=compact_output)


def run_brain_source_flow(
    *,
    sync_context: bool,
    require_context_sync: bool,
    api_url: str,
    compact_output: bool = False,
) -> None:
    run_script(
        SCRIPTS_DIR / "source_intelligence_register_existing.py",
        "--write-legacy-projection",
        compact_output=compact_output,
    )
    intake_args = (
        "--include-legacy-source-intelligence",
        *(("--compact-output",) if compact_output else ()),
    )
    run_script(SCRIPTS_DIR / "brain_signal_intake.py", *intake_args, compact_output=compact_output)
    if sync_context:
        run_script(
            SCRIPTS_DIR / "brain_canonical_memory_sync.py",
            "--api-url",
            api_url,
            required=require_context_sync,
            compact_output=compact_output,
        )


def run_content_bank(*, compact_output: bool = False) -> None:
    run_script(
        SCRIPTS_ROOT / "bank_autonomous_posts.py",
        "--write-legacy-content-bank",
        compact_output=compact_output,
    )


def queue_feezie_workspace_refresh(
    *,
    api_url: str,
    compact_output: bool = False,
) -> dict[str, Any]:
    """Queue the deterministic sync through Railway so the card is gated and signed there."""

    endpoint = f"{validate_control_plane_url(api_url).rstrip('/')}/api/brain/refresh-feezie-workspace"
    request = urllib.request.Request(
        endpoint,
        data=b"",
        headers=control_plane_headers(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        ),
        method="POST",
    )
    try:
        with open_control_plane_request(request, timeout=30) as response:
            raw_bytes = response.read(256 * 1024 + 1)
            if len(raw_bytes) > 256 * 1024:
                raise RuntimeError("Railway returned an oversized FEEZIE workspace refresh queue receipt.")
            raw = raw_bytes.decode("utf-8")
    except urllib.error.HTTPError as exc:
        if compact_output:
            _emit_compact_event(
                "feezie_refresh_step",
                step="refresh_feezie_workspace",
                status="error",
                error_type=f"http_{exc.code}",
            )
        raise RuntimeError(f"Railway rejected the FEEZIE workspace refresh queue request (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        if compact_output:
            _emit_compact_event(
                "feezie_refresh_step",
                step="refresh_feezie_workspace",
                status="error",
                error_type=_diagnostic_type(exc),
            )
        raise RuntimeError("Railway FEEZIE workspace refresh queue is unavailable.") from exc

    try:
        card = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Railway returned an invalid FEEZIE workspace refresh queue receipt.") from exc
    card_id = str(card.get("card_id") or "").strip() if isinstance(card, dict) else ""
    if (
        not card_id
        or card.get("job_id") != card_id
        or card.get("queued") is not True
        or card.get("action") != "refresh_feezie_workspace"
        or card.get("disposition") not in {"queued", "already_active", "requeued"}
    ):
        raise RuntimeError("Railway returned an invalid signed-action queue receipt.")
    receipt = {"queued": True, "card_id": card_id}
    if compact_output:
        _emit_compact_event(
            "feezie_refresh_step",
            step="refresh_feezie_workspace",
            status="queued",
        )
    else:
        print(f"Queued signed FEEZIE workspace refresh card {card_id}.")
    return receipt


def run_watchlist_auto_ingest(*, compact_output: bool = False) -> dict[str, Any]:
    try:
        result = sync_watchlist_auto_ingest(run_refresh=False)
    except Exception:
        if compact_output:
            _emit_compact_event("feezie_refresh_step", step="youtube_watchlist_auto_ingest", status="error")
        raise

    if not compact_output:
        return result

    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    errors = result.get("errors") if isinstance(result.get("errors"), list) else []
    status = "degraded" if warnings or errors else "ok"
    _emit_compact_event(
        "feezie_refresh_step",
        step="youtube_watchlist_auto_ingest",
        status=status,
        enabled=bool(result.get("enabled")),
        counts=counts,
    )
    emitted_diagnostics = 0
    for level, items in (("warning", warnings), ("error", errors)):
        for item in items:
            if emitted_diagnostics >= MAX_COMPACT_DIAGNOSTICS:
                break
            detail = item if isinstance(item, dict) else {"reason": str(item)}
            _emit_compact_event(
                "feezie_refresh_diagnostic",
                step="youtube_watchlist_auto_ingest",
                level=level,
                kind=_safe_identifier(detail.get("kind"), fallback="unspecified"),
                source=_safe_identifier(detail.get("channel_name"), fallback="youtube_watchlist"),
                error_type=_diagnostic_type(detail.get("reason") or detail.get("error_type")),
            )
            emitted_diagnostics += 1
    diagnostic_count = len(warnings) + len(errors)
    if diagnostic_count > emitted_diagnostics:
        _emit_compact_event(
            "feezie_refresh_diagnostics_truncated",
            step="youtube_watchlist_auto_ingest",
            total=diagnostic_count,
            emitted=emitted_diagnostics,
            truncated=diagnostic_count - emitted_diagnostics,
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the LinkedIn social feed.")
    parser.add_argument("--skip-fetch", action="store_true", help="Build from existing signals only.")
    parser.add_argument("--sources", choices=["safe", "all"], default="safe", help="Which fetchers to run.")
    parser.add_argument(
        "--include-youtube-watchlist-compatibility",
        action="store_true",
        help=(
            "Explicit rollback-only switch for invoking YouTube intake from this pipeline. "
            "The dedicated YouTube launchd job is the canonical scheduler."
        ),
    )
    parser.add_argument(
        "--skip-market-archive",
        action="store_true",
        help="Deprecated compatibility alias; the legacy market-signal archive is skipped by default.",
    )
    parser.add_argument(
        "--include-legacy-market-archive-sync",
        action="store_true",
        help="Rollback only: resync the historical market-signal Markdown/JSONL archive.",
    )
    parser.add_argument(
        "--skip-brain-flow",
        action="store_true",
        help="Deprecated compatibility alias; the legacy Brain source flow is skipped by default.",
    )
    parser.add_argument(
        "--include-legacy-brain-source-flow",
        action="store_true",
        help="Rollback only: run the historical source-index to BrainSignal flow.",
    )
    parser.add_argument(
        "--skip-brain-context-sync",
        action="store_true",
        help="Update source intelligence and BrainSignals, but leave canonical context sync to its launchd cadence.",
    )
    parser.add_argument(
        "--require-brain-context-sync",
        action="store_true",
        help="Fail the refresh if the optional immediate Brain context sync cannot publish.",
    )
    parser.add_argument(
        "--brain-api-url",
        default=os.getenv("AICLONE_API_URL", DEFAULT_API_URL),
        help="Backend API URL used by the optional immediate Brain context sync.",
    )
    parser.add_argument(
        "--skip-content-bank",
        action="store_true",
        help="Deprecated compatibility alias; the legacy content bank is skipped by default.",
    )
    parser.add_argument(
        "--include-legacy-content-bank",
        action="store_true",
        help="Rollback only: append to the historical JSONL content bank.",
    )
    parser.add_argument(
        "--skip-strategy-refresh",
        action="store_true",
        help="Skip weekly-strategy regeneration when the runtime intentionally has only privacy-safe inputs.",
    )
    parser.add_argument(
        "--skip-feezie-workspace-sync",
        action="store_true",
        help="Skip queueing the signed local FEEZIE workspace sync (required in the Railway cloud runtime).",
    )
    parser.add_argument(
        "--compact-output",
        action="store_true",
        help="Emit bounded scheduled-run summaries while preserving child warnings and errors.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    legacy_brain_flow = bool(args.include_legacy_brain_source_flow and not args.skip_brain_flow)
    legacy_content_bank = bool(args.include_legacy_content_bank and not args.skip_content_bank)
    if args.compact_output:
        _emit_compact_event(
            "feezie_refresh_started",
            sources=args.sources,
            fresh_fetch=not args.skip_fetch,
            youtube_watchlist_compatibility=bool(args.include_youtube_watchlist_compatibility),
            brain_flow=legacy_brain_flow,
            brain_context_sync=not args.skip_brain_context_sync,
            content_bank=legacy_content_bank,
            feezie_workspace_sync=not args.skip_feezie_workspace_sync,
        )
    if not args.skip_fetch:
        if args.include_youtube_watchlist_compatibility:
            run_watchlist_auto_ingest(compact_output=args.compact_output)
        run_fetcher("reddit", compact_output=args.compact_output)
        run_fetcher("rss", compact_output=args.compact_output)
    if args.include_legacy_market_archive_sync and not args.skip_market_archive:
        run_market_signal_archive_sync(compact_output=args.compact_output)
    run_script(SCRIPTS_ROOT / "build_social_feed.py", compact_output=args.compact_output)
    if not args.skip_strategy_refresh:
        run_script(SCRIPTS_ROOT / "refresh_linkedin_strategy.py", compact_output=args.compact_output)
    if not args.skip_feezie_workspace_sync:
        queue_feezie_workspace_refresh(
            api_url=args.brain_api_url,
            compact_output=args.compact_output,
        )
    if legacy_brain_flow:
        run_brain_source_flow(
            sync_context=not args.skip_brain_context_sync,
            require_context_sync=args.require_brain_context_sync,
            api_url=args.brain_api_url,
            compact_output=args.compact_output,
        )
    if legacy_content_bank:
        run_content_bank(compact_output=args.compact_output)
    if args.compact_output:
        _emit_compact_event("feezie_refresh_completed", status="ok")


if __name__ == "__main__":
    main()
