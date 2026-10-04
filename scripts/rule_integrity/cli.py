"""Run every rule-tree check and report what each found; exit 1 on any problem."""

from __future__ import annotations

import sys
from collections.abc import Callable
from itertools import groupby
from pathlib import Path

from .paths import check_paths
from .problems import Problem
from .repository import Repository, open_repository
from .tags import check_review_tags
from .trees import PROMPT_TREES, collect, empty_trees

Check = Callable[[Repository], list[Problem]]

#: (name, check) -- every check the CLI runs, and the real-tree guard parametrizes over.
CHECKS: tuple[tuple[str, Check], ...] = (
    ("paths", check_paths),
    ("review tags", check_review_tags),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _report_empty(problems: list[str]) -> None:
    print("error: a checked document tree is empty:", file=sys.stderr)
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(
        "\nEither the tree moved -- retarget scripts/rule_integrity/trees.py -- or "
        "it was deleted.\nPassing on an empty scan is what this check exists to prevent.",
        file=sys.stderr,
    )


def main() -> int:
    root = _repo_root()
    empty = empty_trees(root, PROMPT_TREES)
    if empty:
        _report_empty(empty)
        return 1
    repository = open_repository(root)
    if repository.tracked is None:
        print(
            "warning: git could not list this tree, so paths are being checked "
            "against the working directory (`BUG-129`).",
            file=sys.stderr,
        )
    problems = sorted(problem for _, check in CHECKS for problem in check(repository))
    for name, found in groupby(problems, key=lambda problem: problem.check):
        print(f"\n[{name}]", file=sys.stderr)
        for problem in found:
            print(f"  {problem}", file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} problem(s) in the rule tree.", file=sys.stderr)
        return 1
    documents = len(collect(root, PROMPT_TREES))
    print(
        f"OK: {len(CHECKS)} check(s) over {documents} prompt document(s) found no problem."
    )
    return 0
