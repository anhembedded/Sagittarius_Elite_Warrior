"""The git checkout the loop works in: what HEAD is, what changed, and the push.

The reviewer has no shell (`claude_runner` explains why), so every diff and
log it reads is produced here and written to a file it can `Read`.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Branches the loop refuses to work on: every change reaches them through a
#: pull request (`ONBOARDING.md` §7).
PROTECTED_BRANCHES: frozenset[str] = frozenset({"master-warrior", "main", "master"})


class GitError(RuntimeError):
    """A git command failed; the message carries its stderr."""


@dataclass(frozen=True)
class ReviewEvidence:
    """The files one review reads, relative to the checkout root."""

    delta_patch: str
    full_patch: str
    commit_log: str
    head: str
    since: str


class Workspace:
    def __init__(self, root: Path, git: str) -> None:
        self._root = root
        self._git = git

    @property
    def root(self) -> Path:
        return self._root

    def head(self) -> str:
        return self._run("rev-parse", "HEAD")

    def branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def merge_base(self, base_ref: str) -> str:
        return self._run("merge-base", base_ref, "HEAD")

    def is_clean(self) -> bool:
        return self._run("status", "--porcelain") == ""

    def write_evidence(self, since: str, base: str, directory: Path) -> ReviewEvidence:
        """Writes what changed since `since` and since `base` into `directory`
        (inside the checkout) and names the files."""
        directory.mkdir(parents=True, exist_ok=True)
        head = self.head()
        files = {
            "delta.patch": self._run("diff", f"{since}..{head}"),
            "full.patch": self._run("diff", f"{base}...{head}"),
            "commits.txt": self._run(
                "log", "--format=%H%n%B%n----", f"{since}..{head}"
            ),
        }
        for name, content in files.items():
            (directory / name).write_text(content + "\n", encoding="utf-8")
        relative = directory.relative_to(self._root)
        return ReviewEvidence(
            delta_patch=str(relative / "delta.patch"),
            full_patch=str(relative / "full.patch"),
            commit_log=str(relative / "commits.txt"),
            head=head,
            since=since,
        )

    def remote_url(self) -> str:
        return self._run("remote", "get-url", "origin")

    def fetch(self, branch: str) -> None:
        self._run("fetch", "-q", "origin", branch)

    def push(self, branch: str) -> None:
        self._run("push", "-u", "origin", branch)

    def _run(self, *args: str) -> str:
        # `S603` is suppressed, not worked around: `git` is an absolute path
        # resolved by `open_workspace`, the arguments are this module's own
        # literals plus refs git itself returned, and there is no shell.
        completed = subprocess.run(  # noqa: S603
            [self._git, "-C", str(self._root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {completed.stderr.strip()}")
        return completed.stdout.rstrip("\n")


def open_workspace(root: Path) -> Workspace:
    git = shutil.which("git")
    if git is None:
        raise GitError("git is not on PATH")
    return Workspace(root, git)
