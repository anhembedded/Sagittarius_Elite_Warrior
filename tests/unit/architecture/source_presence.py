"""Whether a directory holds Python source, as opposed to merely existing on disk.

A package a move or a deletion removed survives on a developer's disk holding nothing but
`__pycache__` (Python's bytecode caches are untracked, so `git pull` leaves them behind).
`Path.is_dir()` cannot tell that shell from a package; a guard that discovers its subjects
by listing directories must ask this instead (`BUG-198`; the git-backed sibling for guards
that must also ignore stray source is `git_tracked_paths.py`, `BUG-129`).

Stdlib only: no Qt, no Engine.
"""

from __future__ import annotations

from pathlib import Path

_CACHE_DIR = "__pycache__"


def holds_python_source(directory: Path) -> bool:
    """True when `directory` contains at least one `.py` file, directly or in a package
    below it. A tree of `__pycache__` directories and empty folders holds none."""
    return any(
        _CACHE_DIR not in path.relative_to(directory).parts
        for path in directory.rglob("*.py")
    )
