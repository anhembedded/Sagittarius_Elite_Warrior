"""`scripts/verify_against_base.py` exists because a "compare against a clean
tree" run silently compared a branch's code against itself
(`Docs/CASE_STUDIES/CS-006_the_comparison_that_compared_itself.md`): a `git
worktree` was created at a path not named `Sagittarius_Elite_Warrior`, so
`PYTHONPATH=..` from the *original* checkout resolved
`Sagittarius_Elite_Warrior.src....` from that checkout, not from the worktree,
regardless of which tree the collected test file came from.

`test_the_worktree_is_named_like_the_repository` pins the one line that fixes
it — E12: name the worktree anything else and this fails.
`test_a_real_comparison_runs_inside_the_worktree` proves the whole script end
to end, not just the helper in isolation.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from verify_against_base import run, worktree_path

_GIT = shutil.which("git")
assert _GIT is not None, "git is not on PATH"


def test_the_worktree_is_named_like_the_repository(tmp_path: Path) -> None:
    fake_repo_root = Path("/somewhere/checked/out/as/a-branch-name")
    result = worktree_path(tmp_path, fake_repo_root)

    assert result.name == "a-branch-name"
    assert result.parent == tmp_path


def test_a_real_comparison_runs_inside_the_worktree() -> None:
    """End to end against this repository's own `HEAD`: a worktree is made, a
    trivial real test collects and passes inside it, and the worktree is gone
    again afterwards — the E12 probe for the whole script, not only the path
    arithmetic."""
    # An existing, already-committed test rather than this file's own test:
    # this file itself is not yet part of any commit the first time this runs.
    node_id = "tests/unit/test_rule_navigation_is_complete.py"

    exit_code = run("HEAD", [node_id])

    assert exit_code == 0
    worktrees = subprocess.run(
        [_GIT, "worktree", "list"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "verify-against-base-" not in worktrees
