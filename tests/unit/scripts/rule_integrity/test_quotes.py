"""An attributed quote is text the cited document contains (`scripts/rule_integrity/quotes.py`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts.rule_integrity.quotes import check_quotes
from Sagittarius_Elite_Warrior.tests.unit.scripts.rule_integrity.fake_repo import (
    MakeRepo,
)

_SOURCE = ".claude/rules/source-rule.md"

_DOCUMENTS: dict[str, str] = {
    ".claude/ONBOARDING.md": (
        "# Map\n\n## 7. Authority\nThe author **never** merges its own code — ever.\n\n"
        "## 8. Traps\nTraps live elsewhere.\n"
    ),
    ".claude/CONSTITUTION.md": (
        "# C\n\n## The Invariants\n1. **Mechanism Over Memory:** gates, not vigilance.\n"
        "2. **Verify, Don't Restate:** run the proof.\n"
    ),
}


def _problems(make_repo: MakeRepo, line: str) -> list[tuple[int, str]]:
    repository = make_repo({**_DOCUMENTS, _SOURCE: f"# Source\n\n{line}\n"})
    return [(p.line, p.message) for p in check_quotes(repository)]


@pytest.mark.parametrize(
    "line",
    [
        '"the author never merges its own code" (ONBOARDING §7)',
        '(`ONBOARDING.md` §7): "never merges its own code - ever"',
        'ONBOARDING §7\'s "never merges its own code" row',
        "“Verify, don’t restate” (CONSTITUTION P2)",
        '"never merges its own code" (ONBOARDING.md)',
        '"short" (ONBOARDING §7)',
        'An unattributed "quotation of some length" stays prose.',
    ],
)
def test_an_exact_quote_is_not_reported(make_repo: MakeRepo, line: str) -> None:
    assert _problems(make_repo, line) == []


@pytest.mark.parametrize(
    "line",
    [
        "\"Redesign a hard design; 'it works' is not a reason\" (ONBOARDING §7)",
        '(ONBOARDING §8): "the author never merges its own code"',
        'ONBOARDING §7 "an invented sentence" says so',
        '"Mechanism Over Memory" (CONSTITUTION P2)',
    ],
)
def test_a_fabricated_quote_is_reported_at_its_line(
    make_repo: MakeRepo, line: str
) -> None:
    problems = _problems(make_repo, line)
    assert [number for number, _ in problems] == [3]
    assert "is not in `.claude/" in problems[0][1]
