"""`BOT-180` — drive `check_fix_pr_body.py` as CI does, through `PR_TITLE` and `PR_BODY`.

Runs the real script in a subprocess on a well-formed fix body, a body missing
each section, and a non-fix title, and reports the exit code of each. Exit code 0
means every case behaved as `fix-bug-rule.md` §6.1 requires; 1 means one did not.

    python -m Sagittarius_Elite_Warrior.scripts.bot180_fix_pr_body_probe
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).with_name("check_fix_pr_body.py")
_DIAGRAM = "```mermaid\nsequenceDiagram\n    Runner->>Exchange: place\n```"
_SECTIONS = {
    "Root cause": "The mechanism (`a.py:10`).",
    "Corrective action": "What changed.",
    "Sequence: before": _DIAGRAM,
    "Sequence: after": _DIAGRAM,
}


def _body(without: str = "") -> str:
    return "\n\n".join(f"## {h}\n\n{t}" for h, t in _SECTIONS.items() if h != without)


def _exit_code(title: str, body: str) -> int:
    env = {**os.environ, "PR_TITLE": title, "PR_BODY": body}
    return subprocess.run(  # noqa: S603 - our own script, fixed argv
        [sys.executable, str(_SCRIPT)], env=env, check=False
    ).returncode


def main() -> int:
    cases = [("fix: well formed", _body(), 0), ("feat: not a fix", "", 0)]
    cases += [(f"fix: no {h}", _body(without=h), 1) for h in _SECTIONS]
    wrong = 0
    for title, body, expected in cases:
        actual = _exit_code(title, body)
        verdict = "ok" if actual == expected else "WRONG"
        wrong += actual != expected
        sys.stdout.write(
            f"{verdict}: {title!r} exited {actual} (expected {expected})\n"
        )
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
