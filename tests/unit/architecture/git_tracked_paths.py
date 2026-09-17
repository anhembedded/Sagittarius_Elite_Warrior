"""Git-backed answer to "does the repository hold this path" — shared by
every guard that would otherwise ask the filesystem and get an answer that
depends on whose disk it runs on (`BUG-129`, `CS-005`).

A directory a move emptied survives on disk holding nothing but
`__pycache__`; `Path.is_dir()`/`Path.exists()` cannot tell it from a real
one, only `git` can. Two guards had their own copy of this exact check before
this module existed — `tests/unit/architecture/test_scanned_roots_are_not_empty.py`
and `scripts/check_skill_prompt_references.py` (which keeps its own, since a
production script must not import from `tests/`) — and the third near-copy
this file's own review demanded is exactly the drift `CLAUDE.md`'s opening
warning is about.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path, PurePosixPath


class GitUnavailableError(RuntimeError):
    """Raised instead of returning a fallback answer, because a path-scanning
    guard that degraded to the filesystem here would be silently reproducing
    `BUG-129` — and a `warnings.warn()` that only shows up in a pytest
    warnings summary is invisible to both mechanisms this repository actually
    uses to fail a run (`CLAUDE.md`'s mandated grep for
    `FAILED|ERROR|Traceback|ResourceWarning`, and `ci-local.ps1`'s
    `Invoke-RunLogScan`, which greps the structured app-log format). A round-2
    review of the pull request that first tried the warning found it fired
    but proved nothing failed. Raising is the fix that cannot go quiet."""


def tracked_paths(root: Path) -> set[str]:
    """Every path `root`'s repository holds — files and every ancestor
    directory of a tracked file. Raises `GitUnavailableError` rather than
    degrading to the filesystem when git cannot answer.

    @details Reads the **index**, not `HEAD`: a move that has been `git
    add`ed but not yet committed is real work, and a guard runs before that
    commit. Every environment this test suite runs in — a developer's
    checkout, CI — is a git checkout by construction (`install-rule.md`), so
    there is no legitimate case where a caller should keep going without an
    answer; `BUG-129`'s whole lesson is that a guard which cannot tell a real
    file from a stale `__pycache__` shell must not report success.
    """
    git = shutil.which("git")
    if git is None:
        raise GitUnavailableError(
            "git is not on PATH, so this guard cannot tell a real file from "
            "a stale __pycache__-only leftover (`BUG-129`, `CS-005`)"
        )
    try:
        # `S603` is suppressed, not worked around: the argument vector is this
        # literal list plus `root`, there is no shell, and `git` is the
        # absolute path resolved above rather than a name looked up at spawn
        # time (`S607`).
        completed = subprocess.run(
            [git, "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GitUnavailableError(
            f"`git ls-files` failed ({exc}), so this guard cannot tell a real "
            "file from a stale __pycache__-only leftover (`BUG-129`, `CS-005`)"
        ) from exc

    tracked: set[str] = set()
    for entry in completed.stdout.split("\0"):
        if not entry:
            continue
        tracked.add(entry)
        parent = PurePosixPath(entry).parent
        while parent != PurePosixPath("."):
            tracked.add(parent.as_posix())
            parent = parent.parent
    return tracked
