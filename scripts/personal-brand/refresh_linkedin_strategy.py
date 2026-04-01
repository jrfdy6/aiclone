#!/usr/bin/env python3
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent


def main() -> None:
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / "generate_linkedin_weekly_plan.py")], check=True)
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / "generate_linkedin_reaction_queue.py")], check=True)
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / "generate_feezie_owner_review_drafts.py")], check=True)
    subprocess.run([sys.executable, str(SCRIPTS_ROOT / "generate_linkedin_weekly_plan.py")], check=True)


if __name__ == "__main__":
    main()
