#!/usr/bin/env python3
"""Claude Code PreToolUse hook for Bash: two rules become barriers (`EPIC-031C`).

* `ci-rule.md` §1 "never judge a run by `| tail`": a command that pipes
  `ci-local.ps1` into `tail` is refused; the verdict lives in the LOG_FILE.
* `commit-rule.md` §1 "never commit when a check is red": `git commit` first
  runs the fast half of the commit tier (ruff check, ruff format --check, the
  rule-integrity checker) and is refused with their output when one fails.
  The architecture guards and touched tests stay with the agent: they take
  tens of seconds, too long to run on every commit attempt.

Claude Code passes the tool call as JSON on stdin; exit code 2 refuses it and
shows stderr to the agent. Stdlib only.

Retire when: the repository adopts a git pre-commit framework that runs the
same checks for every committer, agent or human.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

#: An invocation (pwsh/powershell running ci-local.ps1) piped, on the same line,
#: into `tail`. Requiring the invocation keeps prose that merely names the
#: script — a heredoc, a commit message — from being refused.
_TAIL_PIPE = re.compile(
    r"\b(?:pwsh|powershell)(?:\.exe)?\b[^\n|]*ci-local\.ps1[^\n|]*(?:\|[^\n|]*)*\|\s*tail\b"
)
_GIT_COMMIT = re.compile(r"(?:^|[;&|(]\s*|\s)git\s+(?:-[^\s]+\s+\S+\s+)*commit\b")
_REFUSE = 2

#: One check: a name and the argument vector, relative to the repository root.
Check = tuple[str, list[str]]
Runner = Callable[[list[str], Path], tuple[int, str]]


def refusal_for_tail(command: str) -> str | None:
    if _TAIL_PIPE.search(command):
        return (
            "Refused: `ci-local.ps1 ... | tail` judges a run by its console tail. "
            "Redirect the output to a file and grep the LOG_FILE it prints for "
            "FAILED|ERROR|Traceback|ResourceWarning (ci-rule.md §1)."
        )
    return None


def is_commit(command: str) -> bool:
    return _GIT_COMMIT.search(command) is not None


def commit_checks(root: Path) -> list[Check]:
    venv_ruff = root / ".venv" / "bin" / "ruff"
    ruff = str(venv_ruff) if venv_ruff.is_file() else shutil.which("ruff")
    python = sys.executable
    checks: list[Check] = []
    if ruff is not None:
        checks.append(
            ("ruff check", [ruff, "check", "src", "tests", "tools", "scripts"])
        )
        checks.append(
            (
                "ruff format",
                [ruff, "format", "--check", "src", "tests", "tools", "scripts"],
            )
        )
    checks.append(
        (
            "reference check",
            [python, str(root / "scripts" / "check_skill_prompt_references.py")],
        )
    )
    return checks


def run(argv: list[str], root: Path) -> tuple[int, str]:
    completed = subprocess.run(  # noqa: S603 -- the argument vectors are built above from absolute paths
        argv, cwd=root, capture_output=True, text=True, check=False
    )
    return completed.returncode, completed.stdout + completed.stderr


def refusal_for_commit(root: Path, runner: Runner = run) -> str | None:
    failures = []
    for name, argv in commit_checks(root):
        code, output = runner(argv, root)
        if code != 0:
            failures.append(f"--- {name} failed ---\n{output.strip()[-2000:]}")
    if not failures:
        return None
    return (
        "Refused: a commit-tier check is red (commit-rule.md §1). Fix it, then commit.\n"
        + "\n".join(failures)
    )


def decide(event: dict[str, object], root: Path, runner: Runner = run) -> str | None:
    """The refusal message for one tool call, or None to let it run."""
    if event.get("tool_name") != "Bash":
        return None
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return None
    refusal = refusal_for_tail(command)
    if refusal is None and is_commit(command):
        refusal = refusal_for_commit(root, runner)
    return refusal


def main() -> int:
    event = json.load(sys.stdin)
    root = Path(
        os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2]
    )
    refusal = decide(event if isinstance(event, dict) else {}, root)
    if refusal is None:
        return 0
    print(refusal, file=sys.stderr)
    return _REFUSE


if __name__ == "__main__":
    sys.exit(main())
