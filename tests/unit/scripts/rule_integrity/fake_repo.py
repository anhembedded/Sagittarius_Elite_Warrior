"""A fake repository on disk: the files a test writes are exactly what git tracks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.rule_integrity.repository import Repository

MakeRepo = Callable[[dict[str, str]], Repository]


def write_repo(root: Path, files: dict[str, str]) -> Repository:
    """Write `files` (repository path -> text) under `root` and track all of them.

    `Repository` is the real class with an explicit tracked set -- the same object
    `open_repository` builds from `git ls-files` -- so no git process is needed.
    """
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Repository(root, frozenset(files))
