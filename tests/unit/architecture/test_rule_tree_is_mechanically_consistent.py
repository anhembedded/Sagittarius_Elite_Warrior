"""The real rule tree passes every `scripts/rule_integrity/` check.

`scripts/check_skill_prompt_references.py` already runs these checks as a gate
step, but a gate step reports one red line; this guard reports each check as
its own test, with every problem it found, so a broken citation and a missing
tag are two named failures rather than one. It reads the trees through
`scripts/rule_integrity/trees.py` -- the same tuples the CLI reads -- so the two
cannot disagree about what is scanned.

Retire when: `ci-local.ps1` reports the reference-check step per check with its
problem list, so this parametrization duplicates what the gate log already says.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts.rule_integrity.cli import CHECKS, Check
from Sagittarius_Elite_Warrior.scripts.rule_integrity.repository import (
    open_repository,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "check", [check for _, check in CHECKS], ids=[name for name, _ in CHECKS]
)
def test_the_rule_tree_has_no_problem(check: Check) -> None:
    repository = open_repository(_REPO_ROOT)
    assert repository.tracked is not None, "git could not list the repository"
    problems = check(repository)
    assert problems == [], "\n".join(str(problem) for problem in problems)
