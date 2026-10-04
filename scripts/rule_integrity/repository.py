"""What the repository holds, asked of git rather than of whoever's disk runs the check.

@par Why git and not the filesystem (`BUG-129`)
The checker resolved every reference with `Path.exists()` once, which answers
about the disk it runs on rather than about the repository. A working tree
carries more than the repository does -- a directory emptied by a move survives
as a `__pycache__` shell -- so a prompt citing a deleted path passed on every
developer machine and failed in CI, which clones fresh. `git ls-files` gives
local and CI the same answer.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePosixPath


def _with_ancestors(files: frozenset[str]) -> frozenset[str]:
    """`files` plus every directory above each one: git tracks files, prompts cite both."""
    entries: set[str] = set(files)
    for entry in files:
        parent = PurePosixPath(entry).parent
        while parent != PurePosixPath("."):
            entries.add(parent.as_posix())
            parent = parent.parent
    return frozenset(entries)


@dataclass(frozen=True)
class Repository:
    """One checkout: its root and, when git could answer, the files it tracks.

    `tracked` is `None` when git is unavailable or `root` is not a repository;
    every query then falls back to the working directory. `None` rather than an
    empty set, because an empty set would read as "the repository holds nothing".
    """

    root: Path
    tracked: frozenset[str] | None

    @cached_property
    def _entries(self) -> frozenset[str]:
        return (
            _with_ancestors(self.tracked) if self.tracked is not None else frozenset()
        )

    @cached_property
    def _files(self) -> tuple[str, ...]:
        if self.tracked is not None:
            return tuple(sorted(self.tracked))
        return tuple(
            sorted(
                path.relative_to(self.root).as_posix()
                for path in self.root.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(self.root).parts
            )
        )

    def holds(self, path: str) -> bool:
        """Whether the repository holds `path`, a file or a directory, with or without `/`."""
        if self.tracked is None:
            return (self.root / path).exists()
        return path.rstrip("/") in self._entries

    def files(self) -> tuple[str, ...]:
        """Every file, repository-relative and sorted."""
        return self._files

    def find_by_suffix(self, name: str) -> tuple[str, ...]:
        """Every file whose path is `name` or ends with `/name` -- one entry when unique."""
        return tuple(
            path for path in self.files() if path == name or path.endswith("/" + name)
        )

    def text(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")


def _git_files(root: Path) -> frozenset[str] | None:
    """The index's file list, or `None` when git cannot answer.

    The index is read rather than a commit, because a move that has been staged
    but not yet committed is real work and this checker runs before that commit.
    """
    git = shutil.which("git")
    if git is None:
        return None
    try:
        # `S603` is suppressed, not worked around: the argument vector is this
        # literal list plus `root`, which is this checkout's own path, there is
        # no shell, and `git` is an absolute path resolved above rather than a
        # name looked up at spawn time.
        completed = subprocess.run(  # noqa: S603
            [git, "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return frozenset(entry for entry in completed.stdout.split("\0") if entry)


def open_repository(root: Path) -> Repository:
    """The repository at `root`, asked of git when git can answer."""
    return Repository(root, _git_files(root))
