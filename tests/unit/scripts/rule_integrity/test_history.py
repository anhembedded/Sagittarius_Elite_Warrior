"""A rule states what holds, not how it came to hold (`scripts/rule_integrity/history.py`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.scripts.rule_integrity.history import check_history
from Sagittarius_Elite_Warrior.tests.unit.scripts.rule_integrity.fake_repo import (
    MakeRepo,
)

_RULE = ".claude/rules/probe-rule.md"


def test_a_date_and_a_pr_number_in_a_rule_are_reported_at_their_lines(
    make_repo: MakeRepo,
) -> None:
    text = "# T\n\n- Decided (user decision 2026-09-18).\n- Since PR #230.\n"
    problems = check_history(make_repo({_RULE: text}))
    assert [(p.source, p.line) for p in problems] == [(_RULE, 3), (_RULE, 4)]
    assert "DECISION_*.md" in problems[0].message


def test_a_date_in_a_fenced_block_or_a_decision_path_is_not_reported(
    make_repo: MakeRepo,
) -> None:
    text = (
        "# T\n\n```bash\nlog --since 2026-09-18\n```\n\n"
        "- Cite `DECISION_2026-08-25_sanity_model.md`. `[eye]`\n"
    )
    assert check_history(make_repo({_RULE: text})) == []


def test_the_map_and_constitution_are_checked_but_skills_and_pitfalls_are_not(
    make_repo: MakeRepo,
) -> None:
    dated = "# T\n\nOn 2026-10-04.\n"
    repository = make_repo(
        {
            ".claude/ONBOARDING.md": dated,
            ".claude/CONSTITUTION.md": dated,
            "CLAUDE.md": dated,
            ".claude/skills/probe/SKILL.md": dated,
            ".claude/rules/pitfalls/tests.md": dated,
        }
    )
    assert sorted(p.source for p in check_history(repository)) == [
        ".claude/CONSTITUTION.md",
        ".claude/ONBOARDING.md",
        "CLAUDE.md",
    ]
