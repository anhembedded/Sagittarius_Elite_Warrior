"""`BOT-180` — a well-formed `fix:` pull request body passes and each kind of omission fails."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts import check_fix_pr_body
from Sagittarius_Elite_Warrior.scripts.check_fix_pr_body import is_fix_title, problems

_DIAGRAM = "```mermaid\nsequenceDiagram\n    Runner->>Exchange: place\n```"


def _body(
    root: str = "The reconciler double counts (`a.py:10`).",
    action: str = "Count once.",
    before: str = _DIAGRAM,
    after: str = _DIAGRAM,
) -> str:
    return (
        "## What\n\n- BUG-1\n\n"
        f"## Root cause\n\n{root}\n\n"
        f"## Corrective action\n\n{action}\n\n"
        f"## Sequence: before\n\n{before}\n\n"
        f"## Sequence: after\n\n{after}\n\n"
        "## Verification\n\nred then green\n"
    )


@pytest.mark.parametrize(
    "title", ["fix: a", "fix(bots): a", "Fix(bug-1): a", "fix!: a"]
)
def test_a_fix_title_is_recognised(title: str) -> None:
    assert is_fix_title(title)


@pytest.mark.parametrize(
    "title", ["feat: a", "docs(tasks): a", "prefix: a", "fixture: a"]
)
def test_a_non_fix_title_is_not_checked(title: str) -> None:
    assert problems(title, "") == []


def test_a_well_formed_fix_body_passes() -> None:
    assert problems("fix(bots): a", _body()) == []


def test_not_applicable_with_a_reason_replaces_the_diagram() -> None:
    body = _body(
        before="Not applicable: one function.", after="Not applicable: one function."
    )
    assert problems("fix: a", body) == []


@pytest.mark.parametrize(
    "heading",
    ["Root cause", "Corrective action", "Sequence: before", "Sequence: after"],
)
def test_a_missing_heading_fails(heading: str) -> None:
    body = _body().replace(f"## {heading}", "## Renamed")
    assert problems("fix: a", body) == [f"missing the `## {heading}` section"]


@pytest.mark.parametrize("field", ["root", "action", "before", "after"])
def test_an_empty_section_fails(field: str) -> None:
    found = problems("fix: a", _body(**{field: ""}))
    assert len(found) == 1 and "is empty" in found[0]


def test_a_sequence_without_diagram_or_waiver_fails() -> None:
    found = problems("fix: a", _body(before="It sends then fails."))
    assert len(found) == 1 and "Sequence: before" in found[0]


def test_a_mermaid_block_that_is_not_a_sequence_diagram_fails() -> None:
    body = _body(after="```mermaid\nflowchart TD\n    A-->B\n```")
    assert len(problems("fix: a", body)) == 1


def test_a_sequence_diagram_in_a_non_mermaid_fence_fails() -> None:
    body = _body(after="```text\nsequenceDiagram\n```")
    assert len(problems("fix: a", body)) == 1


def test_not_applicable_without_a_reason_fails() -> None:
    assert len(problems("fix: a", _body(before="Not applicable:"))) == 1


def test_the_after_diagram_does_not_satisfy_the_before_section() -> None:
    body = _body(before="nothing here")
    assert "Sequence: before" in problems("fix: a", body)[0]


def test_an_instruction_comment_is_not_content() -> None:
    body = _body(before="<!-- ```mermaid\nsequenceDiagram\n``` -->")
    assert "is empty" in problems("fix: a", body)[0]


def test_a_heading_inside_a_fence_does_not_split_the_section() -> None:
    fenced = "```mermaid\nsequenceDiagram\n    Note over A: x\n```\n```text\n## Sequence: after\n```"
    assert problems("fix: a", _body(before=fenced)) == []


def test_an_empty_body_fails_every_heading() -> None:
    assert len(problems("fix: a", "")) == 4


def test_main_reads_the_title_and_body_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PR_TITLE", "fix: a")
    monkeypatch.setenv("PR_BODY", "## Root cause\n\nx")
    assert check_fix_pr_body.main() == 1
    assert "Corrective action" in capsys.readouterr().out
    monkeypatch.setenv("PR_BODY", _body())
    assert check_fix_pr_body.main() == 0


def test_main_skips_a_non_fix_pull_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PR_TITLE", "feat: a")
    monkeypatch.setenv("PR_BODY", "")
    assert check_fix_pr_body.main() == 0
