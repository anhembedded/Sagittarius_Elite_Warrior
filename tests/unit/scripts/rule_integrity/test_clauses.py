"""Every clause of a rule file names its enforcing mechanism (`scripts/rule_integrity/clauses.py`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.scripts.rule_integrity.clauses import (
    check_clause_tags,
    untagged_clauses,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.rule_integrity.fake_repo import (
    MakeRepo,
)


def _lines(text: str) -> list[int]:
    return [clause.line for clause in untagged_clauses(text)]


def test_an_untagged_bullet_is_reported_at_its_line() -> None:
    text = "# T\n\n- Tagged. `[eye]`\n- Untagged obligation.\n"
    assert _lines(text) == [4]


def test_a_tag_may_close_a_folded_continuation_line_and_end_with_a_full_stop() -> None:
    text = "# T\n\n- Long clause\n  continued here `[review: A1]`.\n"
    assert _lines(text) == []


def test_an_untagged_paragraph_is_reported() -> None:
    text = "# T\n\nA paragraph that obliges.\nStill the same paragraph.\n"
    assert _lines(text) == [3]


def test_a_tagged_lead_in_covers_the_list_it_introduces() -> None:
    text = "# T\n\nThese hold: `[guard: test_x.py]`\n- one\n- two\n\n- three\n"
    assert _lines(text) == []


def test_a_tagged_lead_in_covers_nothing_past_a_heading() -> None:
    text = "# T\n\nThese hold: `[eye]`\n- covered\n\n## 2. Next\n- not covered\n"
    assert _lines(text) == [7]


def test_an_untagged_lead_in_is_exempt_but_its_items_are_not() -> None:
    text = "# T\n\nRules:\n- uncovered item\n- tagged item `[eye]`\n"
    assert _lines(text) == [4]


def test_the_role_line_after_the_title_is_exempt() -> None:
    text = "# T\n\nYou are the controller.\n\nYou are not exempt here.\n"
    assert _lines(text) == [5]


def test_a_directive_after_the_role_sentence_is_a_clause() -> None:
    text = "# T\n\nYou are the controller. Never apply a hotfix.\n"
    assert _lines(text) == [3]


def test_a_tagged_role_paragraph_with_a_directive_passes() -> None:
    text = "# T\n\nYou are the controller. Never apply a hotfix. `[review: E10]`\n"
    assert _lines(text) == []


def test_a_colon_with_no_list_after_it_is_an_ordinary_clause() -> None:
    text = "# T\n\nNever push to master, ever:\n\n## 2. Next\n"
    assert _lines(text) == [3]


def test_a_colon_before_a_fence_is_an_ordinary_clause() -> None:
    text = "# T\n\nReinstall first:\n```bash\npip install x\n```\n"
    assert _lines(text) == [3]


def test_tables_fences_comments_rules_and_front_matter_are_not_clauses() -> None:
    text = (
        "---\ndescription: front matter\n---\n\n# T\n\n"
        "| a | b |\n| :- | :- |\n| untagged | row |\n\n"
        "```bash\nan untagged command\n```\n\n"
        "<!-- an untagged comment -->\n\n---\n"
    )
    assert _lines(text) == []


def test_a_tag_containing_backticks_does_not_crash_and_counts_as_untagged() -> None:
    text = "# T\n\n- Item. `[guard: `grep x` is empty; review: G4]`\n"
    assert _lines(text) == [3]


def test_the_check_reports_rule_files_but_not_pitfalls(make_repo: MakeRepo) -> None:
    repository = make_repo(
        {
            ".claude/rules/probe-rule.md": "# T\n\n- Fine. `[eye]`\n- Untagged.\n",
            ".claude/rules/pitfalls/tests.md": "# T\n\n1. A trap, never tagged.\n",
        }
    )
    problems = check_clause_tags(repository)
    assert [(p.source, p.line) for p in problems] == [
        (".claude/rules/probe-rule.md", 4)
    ]
