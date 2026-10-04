"""`EPIC-030I` — no runtime artifact is tracked by git.

`commit-rule.md` §3 forbids committing `.venv`, `*.db`, `logs/` and `state/`,
and `.gitignore` hides them from `git add .` — but `git add -f`, a rename, or a
`.gitignore` edit gets one past both, and nothing failed afterwards. The app's
own state (`state/ui_state.json`, `state/bots/` — bots restore as RUNNING) and
SQLite shards are per-machine data: tracked, they leak one machine's state into
every checkout.

@details Reads the git **index** (`git_tracked_paths.tracked_paths()`), not a
directory, so it needs no row in `scanned_roots_registry.py`:
`test_scanned_roots_are_not_empty.py` registers guards that walk a tree from
`Path(__file__).resolve().parents[...]` with `glob`/`rglob`/`iterdir`, and this
file does neither — its subject is the whole index, which the size floor below
proves is not empty.

Directory prefixes are anchored to the repository root, the way `.gitignore`
anchors them (`BUG-077`): `src/support/ui_kit/state/` and a
`.../application/database/` package are source, not data.

Retire when: the app keeps its runtime data outside the repository (a packaged
build's per-user data directory), so no runtime artifact can land in the tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.architecture.git_tracked_paths import (
    tracked_paths,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Root-anchored directories that only ever hold runtime data or tooling.
_FORBIDDEN_ROOT_DIRS = ("state", "logs", "database", ".venv", ".obsidian")
#: SQLite files and their sidecars, at any depth.
_FORBIDDEN_SUFFIXES = (
    ".db",
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".sqlite",
    ".sqlite3",
)
#: Far below the real count (~2 000); fewer means `git ls-files` answered for
#: the wrong tree or not at all.
_MINIMUM_TRACKED_PATHS = 500


def forbidden_reason(path: str) -> str | None:
    """Why `path` (repository-relative, POSIX) must not be tracked, or `None`."""
    first = path.split("/", 1)[0]
    if first in _FORBIDDEN_ROOT_DIRS and first != path:
        return f"under the root-level runtime directory {first}/"
    for suffix in _FORBIDDEN_SUFFIXES:
        if path.endswith(suffix):
            return f"a database file ({suffix})"
    return None


@pytest.mark.parametrize(
    "path",
    [
        "src/support/ui_kit/state/x.py",
        "src/modules/market_data/application/database/x.py",
        "tests/unit/logs_panel.py",
        "Docs/database.md",
    ],
)
def test_source_that_merely_shares_a_name_is_not_flagged(path: str) -> None:
    assert forbidden_reason(path) is None


@pytest.mark.parametrize(
    "path",
    [
        "state/ui_state.json",
        "state/bots/b1.json",
        "logs/dev-1.log",
        "database/spot/BTCUSDT.db",
        ".venv/bin/python",
        ".obsidian/workspace.json",
        "a/x.db-wal",
        "a/x.db-shm",
        "a/x.db-journal",
        "x.sqlite3",
    ],
)
def test_runtime_artifacts_are_flagged(path: str) -> None:
    assert forbidden_reason(path) is not None


def test_no_runtime_artifact_is_tracked() -> None:
    tracked = tracked_paths(_REPO_ROOT)
    assert len(tracked) > _MINIMUM_TRACKED_PATHS, (
        f"git reported only {len(tracked)} paths for {_REPO_ROOT}"
    )
    offenders = {
        path: reason
        for path in sorted(tracked)
        if (reason := forbidden_reason(path)) is not None
    }
    assert not offenders, (
        "runtime artifacts are tracked — `git rm --cached` them "
        f"(commit-rule.md §3): {offenders}"
    )
