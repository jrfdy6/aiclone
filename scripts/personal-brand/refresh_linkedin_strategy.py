#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import subprocess
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the LinkedIn strategy artifacts.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def _cmd(script_name: str, workspace: str | None) -> list[str]:
    command = [sys.executable, str(SCRIPTS_ROOT / script_name)]
    if workspace:
        command.extend(["--workspace", workspace])
    return command


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    subprocess.run(_cmd("generate_linkedin_idea_qualification.py", workspace), check=True)
    subprocess.run(_cmd("generate_linkedin_latent_ideas.py", workspace), check=True)
    subprocess.run(_cmd("materialize_latent_transform_drafts.py", workspace), check=True)
    subprocess.run(_cmd("generate_linkedin_latent_ideas.py", workspace), check=True)
    subprocess.run(_cmd("generate_linkedin_reaction_queue.py", workspace), check=True)
    subprocess.run(_cmd("quarantine_stale_reaction_drafts.py", workspace), check=True)
    subprocess.run(_cmd("generate_linkedin_weekly_plan.py", workspace), check=True)
    subprocess.run(_cmd("generate_feezie_owner_review_drafts.py", workspace), check=True)
    subprocess.run(_cmd("generate_linkedin_weekly_plan.py", workspace), check=True)


if __name__ == "__main__":
    main()
