"""`EPIC-038E` — where a secret file may live: not in the repository, not in a git work tree.

@details A plan, a config or a key file under version control is a key one `git add`
from public (`RESEARCH` §14). So a file is refused when it lies inside this
repository (ignored or not: a mainnet key has no business in the checkout), and
when it lies inside any other git work tree that does not ignore it. If git cannot
be asked, the file is refused rather than trusted.

**Not detected:** a work tree kept outside its directory (a bare repository with
`--git-dir` and `--work-tree`, as some dotfiles setups do) leaves no `.git` beside
the files, so a secret file inside one is not seen as under version control.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)


def work_tree_containing(path: Path) -> Path | None:
    """The nearest ancestor holding `.git` (a directory, or a file for a worktree)."""
    for candidate in path.resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    return None


def git_ignores(path: Path) -> bool | None:
    """Whether git ignores `path`; `None` when git cannot be asked."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed git arguments, the path is one argument, no shell
            ["git", "check-ignore", "-q", "--", str(path.resolve())],  # noqa: S607 - git is found on PATH, as for every developer tool here
            cwd=path.resolve().parent,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode == 0:
        return True
    return False if done.returncode == 1 else None


class SecretFilePlacementCheck(ISecretFileCheck):
    def __init__(
        self,
        repository_root: Path,
        is_ignored: Callable[[Path], bool | None] = git_ignores,
        work_tree_of: Callable[[Path], Path | None] = work_tree_containing,
    ) -> None:
        self._repository_root = repository_root.resolve()
        self._is_ignored = is_ignored
        self._work_tree_of = work_tree_of

    def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
        resolved = path.resolve()
        if resolved.is_relative_to(self._repository_root):
            return SecretFileVerdict(
                "it lies inside the repository, where a key can be committed",
                f"move {path} to a directory outside {self._repository_root}",
            )
        if self._work_tree_of(path) is None:
            return SecretFileVerdict()
        ignored = self._is_ignored(path)
        if ignored is True:
            return SecretFileVerdict()
        why = (
            "git could not be asked whether it is ignored"
            if ignored is None
            else "it lies inside a git work tree and git does not ignore it"
        )
        return SecretFileVerdict(
            f"{why}, so it could be committed",
            f"move {path} outside the work tree, or add it to .gitignore",
        )
