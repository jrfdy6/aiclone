#!/usr/bin/env python3
"""Check OpenClaw cron jobs for stale or missing file/script references."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from openclaw_cron_utils import (
    JOBS_JSON,
    WORKSPACE_ROOT,
    extract_references,
    load_jobs,
    reference_exists,
    reference_is_template,
    resolve_reference,
    schedule_label,
    suggestion_candidates,
)


def _check_reference(reference: str, *, source_kind: str, source_path: Path | None = None) -> dict:
    resolved = resolve_reference(reference, source_path=source_path)
    is_template = reference_is_template(reference)
    exists = is_template or reference_exists(resolved)
    result = {
        "reference": reference,
        "resolved_path": str(resolved),
        "source_kind": source_kind,
        "exists": exists,
    }
    if is_template:
        result["template_reference"] = True
    if not exists:
        result["suggestions"] = suggestion_candidates(resolved)
    return result


def build_report(jobs_file: Path) -> dict:
    jobs = load_jobs(jobs_file)
    report_jobs = []
    missing_items = []
    direct_ref_count = 0
    skill_ref_count = 0
    skills_scanned = 0

    for job in jobs:
        payload = job.get("payload") or {}
        message = payload.get("message", "")
        direct_refs = []
        skill_refs = []
        missing_for_job = []

        for reference in extract_references(message):
            direct_ref_count += 1
            check = _check_reference(reference, source_kind="job_message")
            direct_refs.append(check)
            if not check["exists"]:
                missing_for_job.append(check)
                missing_items.append({"job_name": job.get("name"), **check})

            if reference.endswith("SKILL.md") and check["exists"]:
                skill_path = Path(check["resolved_path"])
                skills_scanned += 1
                skill_text = skill_path.read_text(errors="replace")
                for skill_reference in extract_references(skill_text):
                    skill_ref_count += 1
                    skill_check = _check_reference(skill_reference, source_kind="skill_file", source_path=skill_path)
                    skill_refs.append(skill_check)
                    if not skill_check["exists"]:
                        missing_for_job.append(skill_check)
                        missing_items.append(
                            {
                                "job_name": job.get("name"),
                                "skill_path": str(skill_path),
                                **skill_check,
                            }
                        )

        report_jobs.append(
            {
                "name": job.get("name"),
                "id": job.get("id"),
                "schedule": schedule_label(job),
                "direct_references": direct_refs,
                "skill_references": skill_refs,
                "missing_reference_count": len(missing_for_job),
            }
        )

    jobs_with_missing_refs = sum(1 for item in report_jobs if item["missing_reference_count"] > 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs_file": str(jobs_file),
        "workspace_root": str(WORKSPACE_ROOT),
        "summary": {
            "job_count": len(report_jobs),
            "direct_reference_count": direct_ref_count,
            "skills_scanned": skills_scanned,
            "skill_reference_count": skill_ref_count,
            "missing_reference_count": len(missing_items),
            "jobs_with_missing_references": jobs_with_missing_refs,
        },
        "missing_references": missing_items,
        "jobs": report_jobs,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# OpenClaw Cron Contract Check",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Jobs file: `{report['jobs_file']}`",
        "",
        "## Summary",
        f"- Jobs checked: `{report['summary']['job_count']}`",
        f"- Direct references: `{report['summary']['direct_reference_count']}`",
        f"- Skills scanned: `{report['summary']['skills_scanned']}`",
        f"- Skill references: `{report['summary']['skill_reference_count']}`",
        f"- Missing references: `{report['summary']['missing_reference_count']}`",
        f"- Jobs with missing references: `{report['summary']['jobs_with_missing_references']}`",
    ]

    missing_refs = report.get("missing_references", [])
    if missing_refs:
        lines.extend(["", "## Missing References", ""])
        for item in missing_refs:
            source = item["source_kind"]
            suggestion_text = ""
            suggestions = item.get("suggestions") or []
            if suggestions:
                suggestion_text = f" Suggestions: {', '.join(f'`{value}`' for value in suggestions)}"
            skill_text = f" skill=`{item['skill_path']}`" if item.get("skill_path") else ""
            lines.append(
                f"- job=`{item['job_name']}` source={source}{skill_text} ref=`{item['reference']}` resolved=`{item['resolved_path']}`.{suggestion_text}"
            )
    else:
        lines.extend(["", "## Missing References", "", "- None"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OpenClaw cron jobs for stale file/script references.")
    parser.add_argument("--jobs-file", type=Path, default=JOBS_JSON)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    report = build_report(args.jobs_file)
    markdown = render_markdown(report)

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    else:
        print(json.dumps(report, indent=2))

    if args.md_out:
        args.md_out.write_text(markdown)
    elif not args.json_out:
        print("\n" + markdown)

    if args.fail_on_missing and report["summary"]["missing_reference_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
