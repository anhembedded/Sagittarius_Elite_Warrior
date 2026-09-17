"""Run pytest node ids against a clean worktree of a base ref, so "is this
pre-existing" is answered by a correct comparison rather than by a checkout
mistake (`Docs/CASE_STUDIES/CS-006_the_comparison_that_compared_itself.md`).

@par The mistake this replaces
`EPIC-025` PR #226 claimed two failing tests were pre-existing after "comparing"
them against a `git worktree` of `master-warrior`: it ran
`PYTHONPATH=.. pytest <worktree>/tests/...` from the *original* checkout. Absolute
imports resolve `Sagittarius_Elite_Warrior.src....` by searching `PYTHONPATH` for a
directory of that exact name -- `..` from the original checkout finds it there,
regardless of which tree the collected test *file* came from. The "clean tree" run
silently imported the original checkout's own `src/`, so the comparison always
answered "identical", proving nothing.

@par The fix
`worktree_path()` below names the worktree directory itself
`Sagittarius_Elite_Warrior` (matching this repository's own name, whatever the
caller's checkout is called) inside a fresh temporary parent, so `PYTHONPATH` set to
that parent can resolve the import only from the worktree -- there is no path back to
the original checkout's code left to fall into. `tests/unit/test_verify_against_base.py`
pins this by asserting the worktree's basename, not by trusting the docstring.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _git() -> str:
    """An absolute path, resolved once — `subprocess.run` then takes no
    partial executable name and no shell (`scripts/check_skill_prompt_references.py`'s
    own pattern, `BUG-129`)."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is not on PATH")
    return git


def worktree_path(tmp_parent: Path, repo_root: Path = _REPO_ROOT) -> Path:
    """Where the comparison worktree must live: a fresh parent directory, with
    the worktree itself named exactly like `repo_root` -- the one detail that
    makes `Sagittarius_Elite_Warrior.src....` resolve from *this* tree and no
    other, once `PYTHONPATH` is set to `tmp_parent`."""
    return tmp_parent / repo_root.name


def run(ref: str, node_ids: list[str], repo_root: Path = _REPO_ROOT) -> int:
    git = _git()
    with tempfile.TemporaryDirectory(prefix="verify-against-base-") as tmp:
        worktree = worktree_path(Path(tmp), repo_root)
        subprocess.run(  # noqa: S603 -- `git` is an absolute path resolved above
            [git, "worktree", "add", "--detach", str(worktree), ref],
            cwd=repo_root,
            check=True,
        )
        try:
            head_sha = subprocess.run(  # noqa: S603
                [git, "rev-parse", "HEAD"],
                cwd=worktree,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            print(f"[verify-against-base] {ref} -> {head_sha}, tree: {worktree}")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(worktree.parent)
            env["QT_QPA_PLATFORM"] = "offscreen"
            result = subprocess.run(  # noqa: S603 -- the repo's own venv python, absolute path
                [
                    str(repo_root / ".venv" / "bin" / "python"),
                    "-m",
                    "pytest",
                    "-q",
                    *node_ids,
                ],
                cwd=worktree,
                env=env,
                check=False,
            )
            return result.returncode
        finally:
            subprocess.run(  # noqa: S603
                [git, "worktree", "remove", "--force", str(worktree)],
                cwd=repo_root,
                check=False,
            )
            shutil.rmtree(worktree, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ref", help="git ref to compare against, e.g. origin/master-warrior"
    )
    parser.add_argument(
        "node_ids", nargs="+", help="pytest node ids, relative to the repo root"
    )
    args = parser.parse_args()
    return run(args.ref, args.node_ids)


if __name__ == "__main__":
    sys.exit(main())
