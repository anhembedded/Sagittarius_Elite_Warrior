"""`EPIC-031A` — the independent-review status passes only on a trusted, independent, current pass.

The probes P1-P4 are the PR #326 review's bypasses: an author whose commits
carry no session, a passer-by with an invented session, a pass later reversed,
and a blocking review that quotes the pass line.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts.check_independent_review import (
    Comment,
    PullRequest,
    authored_messages,
    judge,
)

_HEAD = "6424227a4f349b82f8a42c296f0184efa2baddae"
_AUTHOR = "https://claude.ai/code/session_01AUTHOR"
_REVIEWER = "https://claude.ai/code/session_01REVIEWER"
_COMMIT = f"feat(core): change\n\nWhy.\n\nClaude-Session: {_AUTHOR}\n"


def _review(verdict: str = "PASS", session: str = _REVIEWER, extra: str = "") -> str:
    return (
        f"## Review at `{_HEAD}`\n\n**Verdict: {verdict}**\n\n{extra}\n\n"
        f"### Check ID coverage disclosure\n| A | Inspected |\n\nClaude-Session: {session}\n"
    )


def _pull(
    *comments: Comment,
    paths: tuple[str, ...] = ("src/x.py",),
    commits: tuple[str, ...] = (_COMMIT,),
) -> PullRequest:
    return PullRequest(
        head_sha=_HEAD, changed_paths=paths, commit_messages=commits, comments=comments
    )


def _owner(body: str) -> Comment:
    return Comment(body, "OWNER")


def test_an_independent_passing_review_of_the_head_passes() -> None:
    assert judge(_pull(_owner(_review()))).passed


def test_documentation_only_needs_no_review() -> None:
    paths = ("Tasks/ROADMAP.md", ".github/PULL_REQUEST_TEMPLATE.md")
    assert judge(_pull(paths=paths)).passed


def test_a_workflow_change_is_code_and_needs_a_review() -> None:
    assert not judge(_pull(paths=("README.md", ".github/workflows/ci.yml"))).passed


def test_p1_a_commit_without_a_session_trailer_fails() -> None:
    unsigned = "feat(core): change\n\nWhy.\n"
    verdict = judge(_pull(_owner(_review()), commits=(_COMMIT, unsigned)))
    assert not verdict.passed
    assert "no Claude-Session trailer" in verdict.reason


@pytest.mark.parametrize(
    "association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", ""]
)
def test_p2_a_review_from_outside_the_repository_is_ignored(association: str) -> None:
    forged = Comment(
        _review(session="https://claude.ai/code/session_01FAKE"), association
    )
    assert not judge(_pull(forged)).passed


@pytest.mark.parametrize("association", ["MEMBER", "COLLABORATOR"])
def test_members_and_collaborators_may_review(association: str) -> None:
    assert judge(_pull(Comment(_review(), association))).passed


def test_p3_a_later_blocking_verdict_overrides_an_earlier_pass() -> None:
    verdict = judge(_pull(_owner(_review()), _owner(_review("BLOCKING"))))
    assert not verdict.passed
    assert "`Verdict: PASS`" in verdict.reason


def test_a_later_pass_overrides_an_earlier_revision_request() -> None:
    assert judge(_pull(_owner(_review("NEEDS_REVISION")), _owner(_review()))).passed


def test_p4_a_quoted_pass_inside_a_revision_request_does_not_pass() -> None:
    quoting = _review("NEEDS_REVISION", extra="After the fix I expect `Verdict: PASS`.")
    assert not judge(_pull(_owner(quoting))).passed


def test_a_comment_without_a_verdict_line_is_not_a_review() -> None:
    chatter = _owner(f"Thanks for {_HEAD[:7]}; will look soon.")
    assert judge(_pull(_owner(_review()), chatter)).passed


@pytest.mark.parametrize(
    ("body", "missing"),
    [
        (_review().replace("coverage disclosure", "notes"), "the coverage disclosure"),
        (
            _review().replace(f"Claude-Session: {_REVIEWER}", ""),
            "a reviewer `Claude-Session:`",
        ),
        (_review(session=_AUTHOR), "a session that wrote no commit"),
    ],
)
def test_each_missing_element_fails_the_status(body: str, missing: str) -> None:
    verdict = judge(_pull(_owner(body)))
    assert not verdict.passed
    assert missing in verdict.reason


def test_a_review_of_another_commit_does_not_count() -> None:
    stale = _owner(_review().replace(_HEAD, "0d5fd5b3a77ce0a57bcf136f458c536901c4e765"))
    verdict = judge(_pull(stale))
    assert not verdict.passed
    assert _HEAD[:7] in verdict.reason


def test_p6_a_base_merge_commit_does_not_need_a_session() -> None:
    """PR #326 round-2 finding: a merge from the base carries no trailer, and is skipped."""
    commits: list[dict[str, object]] = [
        {"commit": {"message": _COMMIT}, "parents": [{"sha": "a"}]},
        {
            "commit": {"message": "Merge branch 'master-warrior' into feature"},
            "parents": [{"sha": "a"}, {"sha": "b"}],
        },
    ]
    messages = authored_messages(commits)
    assert messages == (_COMMIT,)
    assert judge(_pull(_owner(_review()), commits=messages)).passed
