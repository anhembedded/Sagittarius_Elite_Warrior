"""`EPIC-031A` — the commit-message check accepts the repository's format and names each breach."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts.check_commit_messages import problems

_TRAILER = (
    "\n\nCo-Authored-By: An Assistant <noreply@example.com>\n"
    "Claude-Session: https://claude.ai/code/session_01ABC\n"
)


def _message(subject: str, body: str = "Why the change was made.") -> str:
    return f"{subject}\n\n{body}{_TRAILER}"


@pytest.mark.parametrize(
    "subject",
    [
        "feat(trading): add a thing",
        "docs: no scope is fine",
        "refactor(support/ui_kit): a path-like scope",
        "fix(epic-028s): the scope names the task",
        "fix(bug-127): the scope names the bug",
    ],
)
def test_a_conforming_message_has_no_problem(subject: str) -> None:
    assert problems(_message(subject)) == []


def test_a_fix_may_cite_its_id_in_the_body() -> None:
    assert problems(_message("fix(core): close the leak", "Root cause: BUG-142.")) == []


def test_a_fix_may_cite_the_review_that_found_it() -> None:
    message = _message("fix(core): close the leak", "PR #323 review finding 1.")
    assert problems(message) == []


@pytest.mark.parametrize(
    ("message", "fragment"),
    [
        (_message("Add a thing"), "is not `<type>(<scope>): <subject>`"),
        (_message("feature(core): add a thing"), "type `feature` is not one of"),
        (_message("feat(Core): add a thing"), "is not `<type>(<scope>): <subject>`"),
        ("feat(core): add a thing" + _TRAILER, "the body is empty"),
        ("feat(core): add a thing\n\nWhy.\n", "`Co-Authored-By:` trailer is missing"),
        ("feat(core): add a thing\n\nWhy.\n", "`Claude-Session:` trailer is missing"),
        (
            _message("fix(core): close the leak", "No id here."),
            "cites no BUG/BOT/EPIC/PRO id",
        ),
        ("", "the message is empty"),
    ],
)
def test_each_breach_is_named(message: str, fragment: str) -> None:
    found = problems(message)
    assert any(fragment in problem for problem in found), found


def test_trailers_alone_do_not_count_as_a_body() -> None:
    message = (
        "feat(core): add a thing\n\nSigned-off-by: Someone <s@example.com>" + _TRAILER
    )
    assert any("the body is empty" in problem for problem in problems(message))
