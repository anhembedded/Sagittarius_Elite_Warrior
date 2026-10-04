"""The inner loop over a real git repository on `tmp_path`, with both roles
scripted through `ScriptedClaude`."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.review_loop.loop import LoopEnd

from .doubles import (
    ScriptedClaude,
    build_loop,
    commit_file,
    dev_step,
    git,
    issue,
    make_repo,
    review_step,
)


def test_an_approval_ends_the_loop_and_the_reviewer_can_only_read(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n"))],
        reviewer=[review_step("rev-1", "APPROVE", [])],
    )

    result = build_loop(repo, claude).run(())

    assert result.end is LoopEnd.APPROVED
    (review,) = claude.reviewer_calls()
    assert review.policy.tools == ("Read", "Glob", "Grep")
    assert review.resume is None
    assert review.session_id is not None
    (dev,) = claude.developer_calls()
    assert dev.session_id is not None
    trailer = (
        "Claude-Session: https://claude.ai/code/session_"
        + dev.session_id.replace("-", "")
    )
    assert trailer in dev.prompt
    full_patch = next(
        line for line in review.prompt.splitlines() if "full.patch" in line
    )
    assert "+one" in (repo / full_patch.split(": ")[-1]).read_text(encoding="utf-8")


def test_a_second_review_resumes_the_same_session_and_reads_only_the_delta(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[
            dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "first\n")),
            dev_step(
                "dev-2",
                [{"id": "R1-1", "answer": "fixed", "detail": "done"}],
                lambda: commit_file(repo, "b.txt", "second\n"),
            ),
        ],
        reviewer=[
            review_step("rev-1", "CHANGES", [issue("R1-1")]),
            review_step("rev-1", "APPROVE", [], [{"id": "R1-1", "status": "fixed"}]),
        ],
    )

    result = build_loop(repo, claude).run(())

    assert result.end is LoopEnd.APPROVED
    assert "[R1-1]" in claude.developer_calls()[1].prompt
    second = claude.reviewer_calls()[1]
    assert second.resume == "rev-1"
    delta = (repo / ".review-loop/run/round-02/evidence/delta.patch").read_text(
        encoding="utf-8"
    )
    assert "+second" in delta
    assert "+first" not in delta


def test_a_red_commit_tier_goes_back_to_the_developer_without_a_review(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[
            dev_step("dev-1", [], lambda: commit_file(repo, "BROKEN", "x\n")),
            dev_step(
                "dev-2",
                [{"id": "commit-tier", "answer": "fixed", "detail": "removed"}],
                lambda: (
                    git(repo, "rm", "-q", "BROKEN"),
                    git(repo, "commit", "-q", "-m", "fix"),
                ),
            ),
        ],
        reviewer=[review_step("rev-1", "APPROVE", [])],
    )

    result = build_loop(repo, claude).run(())

    assert result.end is LoopEnd.APPROVED
    assert len(claude.reviewer_calls()) == 1
    assert "[commit-tier]" in claude.developer_calls()[1].prompt


def test_a_fix_claimed_without_a_commit_is_sent_back(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[
            dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n")),
            dev_step(
                "dev-2",
                [{"id": "R1-1", "answer": "fixed", "detail": "x"}],
                lambda: None,
            ),
            dev_step(
                "dev-3",
                [{"id": "R1-1", "answer": "fixed", "detail": "x"}],
                lambda: commit_file(repo, "a.txt", "two\n"),
            ),
        ],
        reviewer=[
            review_step("rev-1", "CHANGES", [issue("R1-1")]),
            review_step("rev-1", "APPROVE", [], [{"id": "R1-1", "status": "fixed"}]),
        ],
    )

    result = build_loop(repo, claude).run(())

    assert result.end is LoopEnd.APPROVED
    assert "[no-commit]" in claude.developer_calls()[2].prompt


def test_a_finding_kept_open_after_two_answers_stops_for_a_person(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    rebuttal = [{"id": "R1-1", "answer": "rebuttal", "detail": "the finding is wrong"}]
    still_open = [{"id": "R1-1", "status": "open"}]
    claude = ScriptedClaude(
        developer=[
            dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n")),
            dev_step("dev-2", rebuttal, lambda: None),
            dev_step("dev-3", rebuttal, lambda: None),
        ],
        reviewer=[
            review_step("rev-1", "CHANGES", [issue("R1-1")]),
            review_step("rev-1", "CHANGES", [], still_open),
            review_step("rev-1", "CHANGES", [], still_open),
        ],
    )

    result = build_loop(repo, claude).run(())

    assert result.end is LoopEnd.NEEDS_HUMAN
    assert "R1-1" in result.reason
    assert "[R1-1]" in claude.developer_calls()[2].prompt


def test_a_malformed_review_is_asked_again_in_the_same_session(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[dev_step("dev-1", [], lambda: commit_file(repo, "a.txt", "one\n"))],
        reviewer=[
            review_step("rev-1", "APPROVE", [issue("R1-1")]),
            review_step("rev-1", "APPROVE", []),
        ],
    )

    result = build_loop(repo, claude).run(())

    assert result.end is LoopEnd.APPROVED
    follow_up = claude.reviewer_calls()[1]
    assert follow_up.resume == "rev-1"
    assert "did not match" in follow_up.prompt


def test_the_rounds_run_out(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    claude = ScriptedClaude(
        developer=[
            dev_step(
                f"dev-{n}", [], lambda n=n: commit_file(repo, f"f{n}.txt", f"{n}\n")
            )
            for n in range(1, 3)
        ],
        reviewer=[
            review_step("rev-1", "CHANGES", [issue(f"R{n}-1")]) for n in range(1, 3)
        ],
    )

    result = build_loop(repo, claude, max_rounds=2).run(())

    assert result.end is LoopEnd.NEEDS_HUMAN
    assert "2 rounds" in result.reason
