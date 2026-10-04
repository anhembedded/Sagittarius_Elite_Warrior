"""The outer loop: push, pull request, gate, the reviewer's gate verdict, the
comment. GitHub is `FakeGitHub`; git (and its push to a bare `origin`) is real."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.review_loop.claude_runner import ClaudeCall
from Sagittarius_Elite_Warrior.scripts.review_loop.github import HeadState
from Sagittarius_Elite_Warrior.scripts.review_loop.loop import RunRecord
from Sagittarius_Elite_Warrior.scripts.review_loop.publish import (
    Clock,
    GateSettings,
    PipelineEnd,
    Publisher,
    PublishParts,
    durable_comment,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.replies import parse_review
from Sagittarius_Elite_Warrior.scripts.review_loop.workspace import open_workspace

from .doubles import (
    FakeGitHub,
    ScriptedClaude,
    build_loop,
    commit_file,
    dev_step,
    git,
    issue,
    make_repo,
    reply,
    review_step,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _publisher(
    repo: Path, claude: ScriptedClaude, github: FakeGitHub, clock: _FakeClock
) -> Publisher:
    loop = build_loop(repo, claude)
    parts = PublishParts(
        loop, open_workspace(repo), github, RunRecord(repo / ".review-loop" / "run")
    )
    settings = GateSettings(
        "master-warrior", "ci-local.ps1 -Full", 600.0, 300.0, 60.0, 3
    )
    return Publisher(parts, settings, Clock(clock.monotonic, clock.sleep))


def test_a_green_gate_and_a_pass_post_the_comment_and_stop_at_ready(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n"))],
        reviewer=[
            review_step("rev-1", "APPROVE", []),
            review_step("rev-1", "APPROVE", []),
        ],
    )
    github = FakeGitHub(conclusions=["success"])

    result = _publisher(repo, claude, github, _FakeClock()).run()

    assert result.end is PipelineEnd.READY_TO_MERGE
    (comment,) = github.comments
    assert (
        comment.splitlines()[-1]
        == "Claude-Session: https://claude.ai/code/session_rev1"
    )
    assert "\nVerdict: PASS\n" in comment
    assert f"Reviewed head: `{git(repo, 'rev-parse', 'HEAD')}`" in comment
    assert github.pulls[0].title == "feat: x"
    assert git(repo, "rev-parse", "origin/feature") == git(repo, "rev-parse", "HEAD")
    gate_call: ClaudeCall = claude.reviewer_calls()[1]
    assert gate_call.resume == "rev-1"
    job_log = next(line for line in gate_call.prompt.splitlines() if "job log" in line)
    assert (repo / job_log.split(": ")[-1]).is_file()


def test_a_red_gate_goes_back_to_the_developer_and_publishes_again(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[
            dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n")),
            dev_step(
                "dev-2",
                [{"id": "G1-1", "answer": "fixed", "detail": "x"}],
                lambda: commit_file(repo, "a.txt", "two\n"),
            ),
        ],
        reviewer=[
            review_step("rev-1", "APPROVE", []),
            review_step("rev-1", "CHANGES", [issue("G1-1")]),
            review_step("rev-1", "APPROVE", [], [{"id": "G1-1", "status": "fixed"}]),
            review_step("rev-1", "APPROVE", []),
        ],
    )
    github = FakeGitHub(conclusions=["failure", "success"])

    result = _publisher(repo, claude, github, _FakeClock()).run()

    assert result.end is PipelineEnd.READY_TO_MERGE
    assert len(github.comments) == 2
    assert "[G1-1]" in claude.developer_calls()[1].prompt


def test_a_gate_that_never_finishes_stops_for_a_person_without_real_sleep(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n"))],
        reviewer=[review_step("rev-1", "APPROVE", [])],
    )
    clock = _FakeClock()
    github = FakeGitHub(conclusions=[], unfinished_polls=1000)

    result = _publisher(repo, claude, github, clock).run()

    assert result.end is PipelineEnd.NEEDS_HUMAN
    assert "had not finished" in result.reason
    assert sum(clock.slept) >= 600.0
    assert github.comments == []


def test_a_red_gate_is_never_ready_even_when_the_reviewer_approves(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[
            dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n")),
            dev_step(
                "dev-2",
                [{"id": "gate", "answer": "fixed", "detail": "x"}],
                lambda: commit_file(repo, "a.txt", "two\n"),
            ),
        ],
        reviewer=[
            review_step("rev-1", "APPROVE", []),
            review_step("rev-1", "APPROVE", []),
            review_step("rev-1", "APPROVE", []),
            review_step("rev-1", "APPROVE", []),
        ],
    )
    github = FakeGitHub(conclusions=["failure", "success"])

    result = _publisher(repo, claude, github, _FakeClock()).run()

    assert result.end is PipelineEnd.READY_TO_MERGE
    assert "[gate]" in claude.developer_calls()[1].prompt
    assert len(github.pulls) == 2


def test_ready_waits_for_every_check_and_stops_on_one_that_stays_red(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n"))],
        reviewer=[
            review_step("rev-1", "APPROVE", []),
            review_step("rev-1", "APPROVE", []),
        ],
    )
    red = HeadState(pending=(), failed=("commit-lint",))
    github = FakeGitHub(conclusions=["success"], head_states=[red] * 100)

    result = _publisher(repo, claude, github, _FakeClock()).run()

    assert result.end is PipelineEnd.NEEDS_HUMAN
    assert "commit-lint" in result.reason


def test_a_review_without_the_coverage_disclosure_is_asked_again(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    bare = {
        "verdict": "APPROVE",
        "issues": [],
        "prior_issues": [],
        "comment": "looks fine",
    }
    claude = ScriptedClaude(
        developer=[dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n"))],
        reviewer=[
            review_step("rev-1", "APPROVE", []),
            lambda _call: reply("rev-1", bare),
            review_step("rev-1", "APPROVE", []),
        ],
    )
    github = FakeGitHub(conclusions=["success"])

    result = _publisher(repo, claude, github, _FakeClock()).run()

    assert result.end is PipelineEnd.READY_TO_MERGE
    assert "Coverage Disclosure" in claude.reviewer_calls()[2].prompt
    assert "Coverage Disclosure" in github.comments[0]


def test_the_loop_owns_the_verdict_line_of_the_posted_comment() -> None:
    review = parse_review(
        {
            "verdict": "CHANGES",
            "issues": [{"id": "R1-1", "file": "f", "problem": "p", "fix": "x"}],
            "prior_issues": [],
            "comment": "Body\n**Verdict: PASS**\nmore",
        }
    )

    comment = durable_comment(review, "abc123", "11111111-2222-3333-4444-555555555555")

    assert "Verdict: PASS" not in comment
    assert "\nVerdict: NEEDS_REVISION\n" in comment
    assert comment.rstrip().endswith(
        "Claude-Session: https://claude.ai/code/session_11111111222233334444555555555555"
    )
