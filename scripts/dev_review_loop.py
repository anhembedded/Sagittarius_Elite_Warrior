"""Run a developer session and a reviewer session in a loop until the pull
request is ready to merge (`scripts/review_loop/`).

Usage:
    python3 scripts/dev_review_loop.py --task Tasks/backlog/BOT-nnn_slug.md
        [--base master-warrior] [--max-rounds 5] [--local-only]

The loop commits on the current feature branch, pushes it only after the
reviewer approves, opens the pull request, waits for the full gate, and has the
same reviewer session verify the gate and post the durable review comment. It
never merges. Every reply, diff and gate log it used is kept under
`.review-loop/<run>/`; `summary.json` there names the reviewer's session, which
`claude --resume <id>` reopens.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run bare, nothing puts the checkout's parent on the path, and the package is
# imported by its full name -- the name the guards and mypy resolve it by.
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

from Sagittarius_Elite_Warrior.scripts.review_loop.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
