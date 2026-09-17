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
import warnings
from pathlib import Path, PurePosixPath


def tracked_paths(root: Path) -> set[str] | None:
    """Every path `root`'s repository holds — files and every ancestor
    directory of a tracked file — or `None` when git cannot answer.

    @details Reads the **index**, not `HEAD`: a move that has been `git
    add`ed but not yet committed is real work, and a guard runs before that
    commit. `None` rather than an empty set when git is unavailable or `root`
    is not a repository — an empty set would read as "the repository holds
    nothing" and fail every caller — and a warning names `BUG-129`, because
    silently trusting the filesystem here is the exact bug this function
    exists to close.
    """
    git = shutil.which("git")
    if git is None:
        _warn_falling_back("git is not on PATH")
        return None
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
        _warn_falling_back(f"`git ls-files` failed ({exc})")
        return None

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


def _warn_falling_back(reason: str) -> None:
    warnings.warn(
        f"{reason}, so a path-scanning guard cannot tell a real file from a "
        "stale __pycache__-only leftover and is falling back to the "
        "filesystem — the exact false green `BUG-129` exists to close "
        "(`CS-005`).",
        stacklevel=3,
    )
