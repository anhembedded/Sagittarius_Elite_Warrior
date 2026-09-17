"""`git_tracked_paths.tracked_paths()` must fail loudly, not warn quietly,
when git cannot answer (`BUG-129`, `CS-005`).

**Why.** The first fix routed the unavailable-git case through
`warnings.warn()`. A round-2 review of the pull request that shipped it
found the warning real but useless: neither of this repository's two
failure-detection mechanisms — `CLAUDE.md`'s mandated
`grep -nE "FAILED|ERROR|Traceback|ResourceWarning"`, nor `ci-local.ps1`'s
`Invoke-RunLogScan`, which greps the structured `- (WARNING|ERROR|CRITICAL) -`
app-log format — sees a pytest warnings-summary line. Reproduced directly:
with `git` removed from `PATH`, both guard files that call `tracked_paths()`
finished `130 passed, 81 warnings`, exit 0 — a silent fallback wearing a
warning as a costume. `tracked_paths()` now raises `GitUnavailableError`
instead, so the caller's own test fails and nothing has to grep a warning.

**How.** Each test below breaks the one condition the fix depends on and
confirms the failure a caller actually gets, per `pr-review` §E12 — not just
that `tracked_paths()` itself raises, but that the two real guards built on
it propagate the failure rather than swallowing it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.tests.unit.architecture.git_tracked_paths import (
    GitUnavailableError,
    tracked_paths,
)


def test_tracked_paths_finds_this_repository_s_own_files() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    tracked = tracked_paths(repo_root)
    assert "src" in tracked
    assert "tests/unit/architecture/git_tracked_paths.py" in tracked


def test_raises_when_git_is_not_on_path() -> None:
    with (
        patch("shutil.which", return_value=None),
        pytest.raises(GitUnavailableError, match="BUG-129"),
    ):
        tracked_paths(Path(__file__).resolve().parents[3])


def test_raises_when_git_ls_files_fails() -> None:
    with pytest.raises(GitUnavailableError, match="BUG-129"):
        tracked_paths(Path("/does/not/exist/at/all"))


def test_the_zone_check_fails_rather_than_skips_when_git_is_unavailable() -> None:
    """Break the condition the fix depends on and confirm the real guard —
    not just `tracked_paths()` in isolation — fails when git cannot answer."""
    from Sagittarius_Elite_Warrior.tests.unit.architecture.test_module_boundaries import (
        test_src_root_is_where_we_think_it_is,
    )

    with (
        patch("shutil.which", return_value=None),
        pytest.raises(GitUnavailableError),
    ):
        test_src_root_is_where_we_think_it_is()


def test_the_emptiness_check_fails_rather_than_skips_when_git_is_unavailable() -> None:
    from Sagittarius_Elite_Warrior.tests.unit.architecture.scanned_roots_registry import (
        GUARDS,
    )
    from Sagittarius_Elite_Warrior.tests.unit.architecture.test_scanned_roots_are_not_empty import (
        test_scanned_root_exists_and_is_not_empty,
    )

    guard, roots = GUARDS[0]
    root, pattern = roots[0]
    with (
        patch("shutil.which", return_value=None),
        pytest.raises(GitUnavailableError),
    ):
        test_scanned_root_exists_and_is_not_empty(guard, root, pattern)
