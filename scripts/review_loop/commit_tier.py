"""The repository's per-commit checks, run by the loop itself after every
developer round: the developer saying "tests pass" is not evidence
(`ci-rule.md` §1, "Every Commit")."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: How much of a failing command's output the developer is handed.
REPORT_TAIL_LINES = 80


@dataclass(frozen=True)
class CheckOutcome:
    passed: bool
    report: str


class CommitTier:
    def __init__(
        self,
        commands: Sequence[Sequence[str]],
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        self._commands = tuple(tuple(command) for command in commands)
        self._cwd = cwd
        self._env = dict(env)

    def run(self, transcript: Path) -> CheckOutcome:
        """Runs every command in order, writes their output to `transcript`,
        and stops at the first that fails."""
        transcript.parent.mkdir(parents=True, exist_ok=True)
        with transcript.open("w", encoding="utf-8") as sink:
            for command in self._commands:
                # `S603` is suppressed, not worked around: the commands are the
                # CLI's own configured list, run without a shell.
                completed = subprocess.run(  # noqa: S603
                    command,
                    cwd=self._cwd,
                    env=self._env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                output = completed.stdout + completed.stderr
                sink.write(f"$ {' '.join(command)}\n{output}\n")
                if completed.returncode != 0:
                    tail = "\n".join(output.splitlines()[-REPORT_TAIL_LINES:])
                    return CheckOutcome(
                        passed=False,
                        report=(
                            f"`{' '.join(command)}` exited {completed.returncode}. "
                            f"Last lines:\n{tail}"
                        ),
                    )
        return CheckOutcome(passed=True, report="")
