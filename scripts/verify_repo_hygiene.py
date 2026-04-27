#!/usr/bin/env python3
"""Verify that runtime outputs stay out of tracked canonical paths."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import RUNTIME_MEMORY_RELATIVE_PATHS


REQUIRED_GITIGNORE_LINES = (
    "memory/runtime/",
    "memory/reports/memory_health_*.md",
    "memory/oracle_ledger_prune_summary.md",
    "memory/progress_pulse_digest.md",
    "memory/progress_pulse_digests.md",
    "workspaces/*/analytics/",
    "workspaces/*/runtime/",
    "workspaces/*/reports/",
    "workspaces/*/standups/",
    "workspaces/linkedin-content-os/content_bank/",
    "workspaces/linkedin-content-os/docs/backlog_seed_status_20??-??-??.md",
    "workspaces/linkedin-content-os/docs/draft_batch_status_20??-??-??.md",
    "workspaces/linkedin-content-os/docs/next_lane_status_*.md",
    "workspaces/linkedin-content-os/docs/operating_rhythm_status_20??-??-??.md",
    "workspaces/linkedin-content-os/docs/publishing_schedule_20??-??-??.md",
    "workspaces/linkedin-content-os/docs/release_packets/",
    "workspaces/linkedin-content-os/docs/scheduling_lane_status_*.md",
    "workspaces/linkedin-content-os/drafts/feezie_owner_review_packet_20??????.md",
    "workspaces/shared-ops/docs/chronicle_standup_pm_flow_wire_20??-??-??.md",
    "workspaces/shared-ops/docs/codex_chronicle_durable_memory_promotion_20??-??-??.md",
    "workspaces/shared-ops/docs/fallback_watchdog_verification_20??-??-??.md",
    "workspaces/shared-ops/docs/workspace_pack_executive_review_20??-??-??.md",
    "workspaces/shared-ops/docs/heartbeat_verification_20??-??-??.md",
    "workspaces/shared-ops/docs/openclaw_codex_smoke_followup_20??-??-??.md",
    "workspaces/shared-ops/docs/workspace_identity_alignment_20??-??-??.md",
)

UNTRACKED_COMMIT_BUCKET_RULES: tuple[dict[str, Any], ...] = (
    {
        "key": "automation_guardrails_code",
        "label": "Automation guardrails code",
        "description": "New scripts and tests that define or verify automation/content-system behavior.",
        "patterns": (
            "backend/tests/test_build_dream_cycle_snapshot.py",
            "backend/tests/test_linkedin_content_bank.py",
            "backend/tests/test_materialize_latent_transform_drafts.py",
            "backend/tests/test_portfolio_standup_builder.py",
            "backend/tests/test_qmd_freshness_check.py",
            "backend/tests/test_social_signal_extraction.py",
            "scripts/personal-brand/backfill_article_signals.py",
            "scripts/personal-brand/bank_autonomous_posts.py",
            "scripts/personal-brand/linkedin_content_bank.py",
        ),
    },
    {
        "key": "fusion_client_knowledge_pack",
        "label": "Fusion client knowledge pack",
        "description": "Canonical Fusion client workspace knowledge and operating-system assets.",
        "patterns": ("knowledge/aiclone/clients/fusion/",),
    },
    {
        "key": "linkedin_content_assets",
        "label": "LinkedIn content assets",
        "description": "Canonical FEEZIE drafts and tracked market-signal archive material.",
        "patterns": (
            "workspaces/linkedin-content-os/drafts/",
            "workspaces/linkedin-content-os/research/market_signal_archive/",
        ),
    },
    {
        "key": "shared_ops_alignment_memo",
        "label": "Shared Ops alignment memo",
        "description": "Tracked shared_ops execution memo tied to the OpenClaw/Codex alignment lane.",
        "patterns": ("workspaces/shared-ops/docs/openclaw_codex_sync_alignment_",),
    },
)

TRACKED_COMMIT_BUCKET_RULES: tuple[dict[str, Any], ...] = (
    {
        "key": "runtime_hygiene_and_deploy",
        "label": "Runtime hygiene and deploy boundary",
        "description": "Canonical/runtime lane protection, deploy preflight, and related watchdog/memory contract updates.",
        "patterns": (
            ".gitignore",
            "backend/app/services/core_memory_snapshot_service.py",
            "backend/tests/test_core_memory_snapshot_service.py",
            "backend/tests/test_fallback_watchdog.py",
            "docs/cron_delivery_guidelines.md",
            "scripts/build_dream_cycle_snapshot.py",
            "scripts/deploy_railway_service.sh",
            "scripts/fallback_watchdog.py",
            "scripts/progress_pulse_gate.py",
            "scripts/verify_repo_hygiene.py",
            "skills/daily-memory-flush/SKILL.md",
        ),
    },
    {
        "key": "chronicle_pm_ops_routing",
        "label": "Chronicle, PM, and ops routing",
        "description": "Standup, PM, Chronicle, and workspace execution routing changes.",
        "patterns": (
            "backend/app/models/__init__.py",
            "backend/app/models/pm_board.py",
            "backend/app/routes/pm_board.py",
            "backend/app/services/automation_service.py",
            "backend/app/services/operator_story_signal_service.py",
            "backend/app/services/pm_card_service.py",
            "backend/tests/test_codex_chronicle_sync_memory_closeout.py",
            "backend/tests/test_codex_workspace_execution_runner.py",
            "backend/tests/test_operator_story_signal_service.py",
            "backend/tests/test_pm_card_service.py",
            "backend/tests/test_post_sync_dispatch.py",
            "backend/tests/test_workspace_signal_curation.py",
            "docs/chronicle_pm_promotion_boundary.md",
            "scripts/build_standup_prep.py",
            "scripts/ops/build_portfolio_standups.py",
            "scripts/post_sync_dispatch.py",
            "scripts/qmd_freshness_check.py",
            "scripts/runners/run_codex_workspace_execution.py",
            "scripts/sync_codex_chronicle.py",
        ),
    },
    {
        "key": "content_generation_and_social_pipeline",
        "label": "Content generation and social pipeline",
        "description": "Drafting/retrieval pipeline logic, source fetch, and content-system UI/test changes.",
        "patterns": (
            "backend/app/routes/content_generation.py",
            "backend/app/services/content_generation_context_service.py",
            "backend/app/services/content_generation_pipeline_audit_service.py",
            "backend/app/services/lab_experiment_service.py",
            "backend/app/services/local_content_generation_execution_service.py",
            "backend/app/services/social_signal_extraction.py",
            "backend/app/services/social_source_fetch_service.py",
            "backend/tests/test_content_generation_codex_jobs.py",
            "backend/tests/test_content_generation_context_service.py",
            "backend/tests/test_content_generation_pipeline_audit_service.py",
            "backend/tests/test_lab_experiment_service.py",
            "backend/tests/test_refresh_social_feed_pipeline.py",
            "backend/tests/test_social_source_fetch_service.py",
            "frontend/app/ops/OpsClient.tsx",
            "scripts/personal-brand/linkedin_idea_qualification.py",
            "scripts/personal-brand/materialize_latent_transform_drafts.py",
            "scripts/personal-brand/refresh_social_feed.py",
            "scripts/refresh_fusion_instagram_feedback.py",
            "workspaces/linkedin-content-os/docs/social_feed_architecture_plan.md",
            "workspaces/linkedin-content-os/docs/social_intelligence_architecture.md",
        ),
    },
    {
        "key": "persona_brain_and_memory_canon",
        "label": "Persona, Brain, and memory canon",
        "description": "Tracked persona/source-intelligence canon and memory-side source artifacts.",
        "patterns": (
            "README.md",
            "knowledge/persona/feeze/history/story_bank.md",
            "knowledge/persona/feeze/identity/VOICE_PATTERNS.md",
            "knowledge/persona/feeze/identity/claims.md",
            "knowledge/source-intelligence/index.json",
            "memory/backup-log.md",
            "memory/brain_signals.jsonl",
            "memory/weekly_hygiene_summary.md",
            "workspaces/fusion-os/agent-ledgers/fusion-systems-operator.jsonl",
        ),
    },
    {
        "key": "linkedin_workspace_canon",
        "label": "LinkedIn workspace canon",
        "description": "Tracked FEEZIE workspace state: backlog, queue, canonical drafts, plans, and archive updates.",
        "patterns": (
            "workspaces/linkedin-content-os/README.md",
            "workspaces/linkedin-content-os/backlog.md",
            "workspaces/linkedin-content-os/drafts/2026-04-10_claude-dispatch-and-the-power-of-interfaces-latent-transform.md",
            "workspaces/linkedin-content-os/drafts/2026-04-10_the-shape-of-the-thing-latent-transform.md",
            "workspaces/linkedin-content-os/drafts/archive/stale_reaction_manifest.md",
            "workspaces/linkedin-content-os/drafts/feezie-001_cheap-models-better-systems.md",
            "workspaces/linkedin-content-os/drafts/feezie-002_quiet-inefficiency-is-still-failure.md",
            "workspaces/linkedin-content-os/drafts/feezie-003_visibility-that-changes-behavior.md",
            "workspaces/linkedin-content-os/drafts/queue_01.md",
            "workspaces/linkedin-content-os/plans/idea_qualification.md",
            "workspaces/linkedin-content-os/plans/latent_ideas.md",
            "workspaces/linkedin-content-os/research/market_signal_archive/2026-03.jsonl",
            "workspaces/linkedin-content-os/research/market_signal_archive/2026-03.md",
            "workspaces/linkedin-content-os/research/market_signal_archive/2026-04.jsonl",
            "workspaces/linkedin-content-os/research/market_signal_archive/2026-04.md",
        ),
    },
    {
        "key": "shared_ops_docs",
        "label": "Shared Ops docs",
        "description": "Tracked shared_ops documentation updates that support the routing/execution lane.",
        "patterns": (
            "workspaces/shared-ops/docs/README.md",
            "workspaces/shared-ops/docs/openclaw_codex_sync.md",
        ),
    },
    {
        "key": "manual_gitlink_review",
        "label": "Manual gitlink review",
        "description": "Nested git checkout / gitlink that should be reviewed and committed in its own repo context.",
        "patterns": ("downloads/aiclone",),
    },
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(WORKSPACE_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _status_lines(*paths: str) -> list[str]:
    result = _git("status", "--short", "--", *paths)
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _all_status_lines() -> list[str]:
    result = _git("status", "--short", "--untracked-files=all")
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _is_tracked(relative_path: str) -> bool:
    return _git("ls-files", "--error-unmatch", "--", relative_path).returncode == 0


def _read_gitignore() -> str:
    return (WORKSPACE_ROOT / ".gitignore").read_text(encoding="utf-8")


def _group_paths(paths: list[str], rules: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    remaining = list(paths)
    groups: list[dict[str, Any]] = []
    for rule in rules:
        matched = [
            path
            for path in remaining
            if any(path == pattern or path.startswith(pattern) for pattern in rule["patterns"])
        ]
        if not matched:
            continue
        groups.append(
            {
                "key": rule["key"],
                "label": rule["label"],
                "description": rule["description"],
                "paths": sorted(matched),
                "suggested_git_add": ["git", "add", "--", *sorted(matched)],
            }
        )
        remaining = [path for path in remaining if path not in matched]

    if remaining:
        groups.append(
            {
                "key": "review_manually",
                "label": "Manual review",
                "description": "Paths that did not match a known commit bucket.",
                "paths": remaining,
                "suggested_git_add": ["git", "add", "--", *sorted(remaining)],
            }
        )
    return groups


def build_report() -> dict[str, object]:
    runtime_write_paths = sorted(RUNTIME_MEMORY_RELATIVE_PATHS.values())
    protected_canonical_paths = sorted(RUNTIME_MEMORY_RELATIVE_PATHS.keys())
    gitignore_text = _read_gitignore()
    missing_gitignore_lines = [line for line in REQUIRED_GITIGNORE_LINES if line not in gitignore_text]
    tracked_runtime_paths = [path for path in runtime_write_paths if _is_tracked(path)]
    dirty_protected_paths = _status_lines(*protected_canonical_paths)
    tracked_dirty_paths = [
        line[3:]
        for line in _all_status_lines()
        if not line.startswith("?? ")
    ]
    visible_untracked_paths = [
        line[3:]
        for line in _all_status_lines()
        if line.startswith("?? ")
    ]
    tracked_dirty_groups = _group_paths(tracked_dirty_paths, TRACKED_COMMIT_BUCKET_RULES)
    visible_untracked_groups = _group_paths(visible_untracked_paths, UNTRACKED_COMMIT_BUCKET_RULES)

    ok = not missing_gitignore_lines and not tracked_runtime_paths and not dirty_protected_paths
    return {
        "ok": ok,
        "runtime_write_paths": runtime_write_paths,
        "protected_canonical_paths": protected_canonical_paths,
        "missing_gitignore_lines": missing_gitignore_lines,
        "tracked_runtime_paths": tracked_runtime_paths,
        "dirty_protected_paths": dirty_protected_paths,
        "tracked_dirty_paths": tracked_dirty_paths,
        "tracked_dirty_groups": tracked_dirty_groups,
        "visible_untracked_paths": visible_untracked_paths,
        "visible_untracked_groups": visible_untracked_groups,
    }


def print_text(report: dict[str, object]) -> None:
    print("Repo hygiene")
    print(f"- ok: `{report['ok']}`")
    print(f"- runtime write paths: `{len(report['runtime_write_paths'])}`")
    if report["missing_gitignore_lines"]:
        print("- missing .gitignore lines:")
        for item in report["missing_gitignore_lines"]:
            print(f"  - {item}")
    if report["tracked_runtime_paths"]:
        print("- runtime paths unexpectedly tracked:")
        for item in report["tracked_runtime_paths"]:
            print(f"  - {item}")
    if report["dirty_protected_paths"]:
        print("- protected canonical paths are dirty:")
        for item in report["dirty_protected_paths"]:
            print(f"  - {item}")
    if report["tracked_dirty_paths"]:
        print(f"- tracked dirty paths remain: `{len(report['tracked_dirty_paths'])}`")
    if report["tracked_dirty_groups"]:
        print("- tracked commit buckets:")
        for group in report["tracked_dirty_groups"]:
            print(f"  - {group['label']}: {group['description']}")
            print(f"    add: {' '.join(group['suggested_git_add'])}")
            for item in group["paths"]:
                print(f"    path: {item}")
    if report["visible_untracked_paths"]:
        print("- visible untracked paths remain (review as source additions, not runtime hygiene failures):")
        for item in report["visible_untracked_paths"]:
            print(f"  - {item}")
    if report["visible_untracked_groups"]:
        print("- commit buckets:")
        for group in report["visible_untracked_groups"]:
            print(f"  - {group['label']}: {group['description']}")
            print(f"    add: {' '.join(group['suggested_git_add'])}")
            for item in group["paths"]:
                print(f"    path: {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
