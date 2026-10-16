"""A pull request that changes a documented module keeps its design in step (`EPIC-041J`).

`commit-rule.md` §1 ("Design in step") asks every pull request that changes code
under `src/modules/<m>/`, for a module whose design lives in `Docs/MODULES/<m>/`,
either to change that folder too or to say in its own `## Design` section why the
design is unchanged, with one line `No design change: <reason>`. CI runs this
script on every `pull_request` event (`.github/workflows/commit-lint.yml`), so the
question is asked by the gate on each change instead of by the author's memory.

A module without a design folder is not checked: the folder is what makes the
promise. Whether the reason is *true*, and whether the touched files say the right
thing, is a reviewer's call (rubric K10); this script holds only that the question
was answered.

The changed paths come from `git diff --name-only BASE_SHA...HEAD_SHA` (the
workflow checks out the full history); the body arrives through `PR_BODY`, never
interpolated into a shell command. Stdlib only, so it runs on the runner's Python;
it reads `## ` sections with `check_fix_pr_body.sections`.

Retire when: the repository adopts a pull-request body linter in the same workflow.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Collection, Iterable
from pathlib import Path

# Run bare on the runner (`python3 scripts/check_design_in_step.py`) nothing puts
# the checkout's parent on the path; it is added by landmark, as
# `check_skill_prompt_references.py` does, so the section parser is the one
# `check_fix_pr_body.py` owns rather than a second copy.
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

from Sagittarius_Elite_Warrior.scripts.check_fix_pr_body import sections

DESIGN = "Design"
MODULES_SOURCE = "src/modules/"
MODULES_DESIGN = "Docs/MODULES/"

_NO_DESIGN_CHANGE = re.compile(r"^No design change: \S", re.IGNORECASE)
_ROOT = Path(__file__).resolve().parents[1]


def documented_modules(root: Path) -> frozenset[str]:
    """The modules whose design is a folder `Docs/MODULES/<module>/` under `root`."""
    folder = root / MODULES_DESIGN
    if not folder.is_dir():
        return frozenset()
    return frozenset(entry.name for entry in folder.iterdir() if entry.is_dir())


def _module_of(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    return rest.split("/", 1)[0] if "/" in rest else None


def states_no_design_change(body: str) -> bool:
    """True when the `## Design` section holds a `No design change: <reason>` line."""
    lines = sections(body).get(DESIGN.lower(), [])
    return any(_NO_DESIGN_CHANGE.match(line.strip()) for line in lines)


def problems(
    changed: Iterable[str], body: str, documented: Collection[str]
) -> list[str]:
    """What the pull request owes `commit-rule.md` §1 "Design in step"; empty otherwise."""
    paths = list(changed)
    code = {_module_of(path, MODULES_SOURCE) for path in paths}
    design = {_module_of(path, MODULES_DESIGN) for path in paths}
    owing = sorted(
        m for m in code if m is not None and m in documented and m not in design
    )
    if not owing or states_no_design_change(body):
        return []
    return [
        f"changes `{MODULES_SOURCE}{module}/` but not `{MODULES_DESIGN}{module}/`; "
        "update the design, or write `No design change: <reason>` under `## Design`"
        for module in owing
    ]


def changed_paths(base: str, head: str, cwd: Path) -> list[str]:
    """The paths the pull request changes: `git diff --name-only base...head`."""
    completed = subprocess.run(  # noqa: S603 - fixed argv, shas from the event payload
        ["git", "diff", "--name-only", f"{base}...{head}"],  # noqa: S607 - git on PATH
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def main() -> int:
    base = os.environ.get("BASE_SHA", "")
    head = os.environ.get("HEAD_SHA", "")
    if not base or not head:
        sys.stderr.write(
            "BASE_SHA and HEAD_SHA must name the pull request's base and head.\n"
        )
        return 2
    found = problems(
        changed_paths(base, head, _ROOT),
        os.environ.get("PR_BODY", ""),
        documented_modules(_ROOT),
    )
    for problem in found:
        sys.stdout.write(f"design in step: {problem} (commit-rule.md §1)\n")
    if found:
        sys.stderr.write(
            f"\n{len(found)} module(s) owe their design; see .github/PULL_REQUEST_TEMPLATE.md.\n"
        )
        return 1
    sys.stdout.write(
        "OK: every documented module this pull request changes keeps its design in step.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
