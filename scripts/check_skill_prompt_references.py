"""Fail when the rule tree (`CLAUDE.md`, `.claude/**`) is mechanically inconsistent.

The entry point `scripts/ci-local.ps1` runs; the checks themselves live in
`scripts/rule_integrity/`, one module per question (`cli.py` lists them). Run it
before committing any edit to a prompt document:

    python3 scripts/check_skill_prompt_references.py

Exit code 0 = no check found a problem (prints `OK: ...`); 1 = at least one did.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run bare (`python3 scripts/check_skill_prompt_references.py`) nothing puts the
# checkout's parent on the path, and the package is imported by its full name --
# the name the guards and mypy resolve it by -- so the parent of the repository
# root (the directory holding `pyproject.toml`) is added here, found by landmark
# rather than by hop count.
sys.path.insert(
    0,
    str(
        next(
            p
            for p in Path(__file__).resolve().parents
            if (p / "pyproject.toml").is_file()
        ).parent
    ),
)

from Sagittarius_Elite_Warrior.scripts.rule_integrity.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
