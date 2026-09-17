"""`BUG-129`: the reference checker must answer about the **repository**, not
about whoever's disk it happens to run on.

`scripts/check_skill_prompt_references.py` resolved every cited path with
`Path.exists()`. A working tree carries more than the repository does — a
directory emptied by a move survives as a `__pycache__` shell, and nothing
deletes it — so a briefing citing a path the repository no longer has passed
locally and failed in CI, which clones fresh. `master-warrior` was red for
**20 consecutive runs** — measured from the runs, not inherited — while the
local gate reported that step green.

The tier is this one rather than a pytest of the script's internals, because
the disagreement is between two answers to "does this path exist": git's and
the filesystem's. A test that stubs either one cannot show them disagreeing, so
each test below builds a real (tiny) repository and puts a real untracked
directory in it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_skill_prompt_references import check

#: Three of the trees the checker reads; the first is the one the tests cite from.
_TREES = (
    Path(".claude") / "rules" / "probe.md",
    Path(".claude") / "skills" / "probe" / "SKILL.md",
    Path(".claude") / "agents" / "probe.md",
)


#: Resolved once, absolutely: the same reason the checker itself does it — a
#: bare `git` is a name looked up at spawn time (`ruff` S607).
_GIT = shutil.which("git")


def _git(root: Path, *args: str) -> None:
    assert _GIT is not None, "git is required to build this test's fixture repo"
    subprocess.run(
        [_GIT, "-C", str(root), *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository holding three document trees and one tracked source
    file, all committed — so anything added afterwards is untracked."""
    for relative in _TREES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# probe\n", encoding="utf-8")
    tracked = tmp_path / "src" / "kept" / "module.py"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("value = 1\n", encoding="utf-8")

    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "config", "user.email", "probe@example.invalid")
    _git(tmp_path, "config", "user.name", "Probe")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "--quiet", "-m", "probe")
    return tmp_path


def _cite(repo: Path, reference: str) -> None:
    (repo / _TREES[0]).write_text(f"# probe\n\nRead `{reference}` first.\n", "utf-8")


def test_a_path_only_the_working_tree_has_is_reported_missing(repo: Path) -> None:
    """`BUG-129`'s exact shape: `src/application/use_cases/` was deleted by the
    backtesting move and stayed on disk holding nothing but `__pycache__`."""
    stale = repo / "src" / "moved_away" / "__pycache__"
    stale.mkdir(parents=True)
    (stale / "module.cpython-312.pyc").write_bytes(b"\x00")
    _cite(repo, "src/moved_away/")

    assert (repo / "src" / "moved_away").is_dir(), "precondition: on disk"
    assert check(repo) == [(_TREES[0], "src/moved_away/")]


def test_an_untracked_file_does_not_resolve_either(repo: Path) -> None:
    """Not only directories: a file a contributor has locally but never
    committed is the same false green, and the same for a reader who clones."""
    (repo / "src" / "kept" / "scratch.py").write_text("x = 1\n", encoding="utf-8")
    _cite(repo, "src/kept/scratch.py")

    assert check(repo) == [(_TREES[0], "src/kept/scratch.py")]


def test_a_tracked_file_still_resolves(repo: Path) -> None:
    """The fix must not buy correctness by failing everything."""
    _cite(repo, "src/kept/module.py")

    assert check(repo) == []


def test_a_directory_resolves_from_the_files_git_tracks_inside_it(
    repo: Path,
) -> None:
    """git tracks files, never directories, so a cited directory has to be
    answered by the tracked files under it — with or without a trailing
    slash, since the briefings are written both ways."""
    _cite(repo, "src/kept/")
    assert check(repo) == []

    _cite(repo, "src/kept")
    assert check(repo) == []


def test_a_deleted_but_still_staged_path_resolves(repo: Path) -> None:
    """The index, not `HEAD`: a move that has been `git add`ed but not yet
    committed is real work, and the checker runs before that commit."""
    _git(repo, "mv", "src/kept/module.py", "src/kept/renamed.py")
    _cite(repo, "src/kept/renamed.py")

    assert check(repo) == []
