"""`EPIC-031A` — the independent-review status passes only on a review by a session that wrote no commit."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts.check_independent_review import (
    PullRequest,
    judge,
)

_HEAD = "6424227a4f349b82f8a42c296f0184efa2baddae"
_AUTHOR = "https://claude.ai/code/session_01AUTHOR"
_REVIEWER = "https://claude.ai/code/session_01REVIEWER"
_COMMIT = f"feat(core): change\n\nWhy.\n\nClaude-Session: {_AUTHOR}\n"
_REVIEW = (
    f"## Re-review at `{_HEAD}`\n\n**Verdict: PASS.** Nothing new.\n\n"
    f"### Check ID coverage disclosure\n| A | Inspected |\n\nClaude-Session: {_REVIEWER}\n"
)


def _pull(
    comments: tuple[str, ...], paths: tuple[str, ...] = ("src/x.py",)
) -> PullRequest:
    return PullRequest(
        head_sha=_HEAD,
        changed_paths=paths,
        commit_messages=(_COMMIT,),
        comments=comments,
    )


def test_an_independent_passing_review_of_the_head_passes() -> None:
    assert judge(_pull((_REVIEW,))).passed


def test_documentation_only_needs_no_review() -> None:
    paths = ("Tasks/ROADMAP.md", ".github/PULL_REQUEST_TEMPLATE.md")
    assert judge(_pull((), paths)).passed


def test_a_workflow_change_is_code_and_needs_a_review() -> None:
    assert not judge(_pull((), ("README.md", ".github/workflows/ci.yml"))).passed


@pytest.mark.parametrize(
    ("comment", "missing"),
    [
        (_REVIEW.replace(_HEAD, "0d5fd5b3a77ce0a57bcf136f458c536901c4e765"), None),
        (_REVIEW.replace("Verdict: PASS", "Verdict: NEEDS_REVISION"), None),
        (_REVIEW.replace("coverage disclosure", "notes"), "the coverage disclosure"),
        (
            _REVIEW.replace(f"Claude-Session: {_REVIEWER}", ""),
            "a reviewer `Claude-Session:`",
        ),
        (_REVIEW.replace(_REVIEWER, _AUTHOR), "a session that wrote no commit"),
    ],
)
def test_each_missing_element_fails_the_status(
    comment: str, missing: str | None
) -> None:
    verdict = judge(_pull((comment,)))
    assert not verdict.passed
    if missing is not None:
        assert missing in verdict.reason


def test_no_comment_at_all_fails() -> None:
    verdict = judge(_pull(()))
    assert not verdict.passed
    assert _HEAD[:7] in verdict.reason
