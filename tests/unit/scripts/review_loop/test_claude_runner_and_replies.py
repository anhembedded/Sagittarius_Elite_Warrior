"""The `claude` command line, the environment it runs in, and the reply records."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts.review_loop.claude_runner import (
    SESSION_VARIABLES,
    ClaudeCall,
    ClaudeCallError,
    CliClaudeRunner,
    CliSettings,
    build_argv,
    parse_reply,
    scrubbed_environment,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.cli import (
    developer_policy,
    repository_from_remote,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.replies import (
    REVIEW_SCHEMA,
    Answer,
    ReplyShapeError,
    Verdict,
    parse_dev_report,
    parse_review,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.roles import REVIEWER_POLICY

_FAKE_CLAUDE = """#!{python}
import json, os, sys
json.dump({{"session_id": "s-1", "structured_output": {{"argv": sys.argv[1:],
  "session": os.environ.get("CLAUDE_CODE_SESSION_ID"), "extra": os.environ.get("EXTRA")}},
  "result": "", "is_error": False, "subtype": "success", "total_cost_usd": 0.5}}, sys.stdout)
"""


def _settings(executable: str, cwd: Path) -> CliSettings:
    return CliSettings(executable, cwd, 2.5, 30.0, {"EXTRA": "yes"})


def test_every_list_option_is_one_argument_so_none_swallows_the_next() -> None:
    call = ClaudeCall("review it", REVIEW_SCHEMA, REVIEWER_POLICY, resume="s-1")

    argv = build_argv(_settings("claude", Path(".")), call)

    assert argv[:3] == ["claude", "-p", "review it"]
    assert "--tools=Read,Glob,Grep" in argv
    assert "--resume=s-1" in argv
    assert "--max-budget-usd=2.5" in argv
    assert not any(a.startswith("--allowedTools") for a in argv)
    assert not any(a.startswith("--session-id") for a in argv)


def test_a_new_session_takes_the_id_it_is_given() -> None:
    call = ClaudeCall(
        "x", REVIEW_SCHEMA, REVIEWER_POLICY, resume=None, session_id="abc"
    )

    assert "--session-id=abc" in build_argv(_settings("claude", Path(".")), call)


def test_the_developer_may_commit_but_never_push_or_rewrite_history() -> None:
    policy = developer_policy("/venv/python")

    assert "Bash(git commit:*)" in policy.allowed
    assert {"Bash(git push:*)", "Bash(git reset:*)", "Bash(git rebase:*)"} <= set(
        policy.denied
    )
    assert policy.tools is None


def test_the_calling_sessions_variables_never_reach_a_child() -> None:
    base = {name: "parent" for name in SESSION_VARIABLES} | {"PATH": "/bin"}

    env = scrubbed_environment(base, {"PYTHONPATH": "/x"})

    assert env == {"PATH": "/bin", "PYTHONPATH": "/x"}


def test_a_real_process_gets_the_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "claude"
    fake.write_text(_FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "the-parent")
    call = ClaudeCall("hello", REVIEW_SCHEMA, REVIEWER_POLICY, resume=None)

    reply = CliClaudeRunner(_settings(str(fake), tmp_path)).run(call)

    assert reply.session_id == "s-1"
    assert reply.cost_usd == 0.5
    assert isinstance(reply.structured, dict)
    assert reply.structured["session"] is None
    assert reply.structured["extra"] == "yes"
    assert reply.structured["argv"][:2] == ["-p", "hello"]


def test_output_that_is_not_a_reply_is_a_failed_call() -> None:
    with pytest.raises(ClaudeCallError):
        parse_reply("Error: not logged in")
    with pytest.raises(ClaudeCallError):
        parse_reply('{"result": "no session"}')


def _review(
    verdict: str, issues: list[object], prior: list[object]
) -> dict[str, object]:
    return {"verdict": verdict, "issues": issues, "prior_issues": prior, "comment": "c"}


def test_a_review_parses_and_keeps_its_open_findings() -> None:
    review = parse_review(
        _review(
            "CHANGES",
            [],
            [{"id": "R1-1", "status": "open"}, {"id": "R1-2", "status": "fixed"}],
        )
    )

    assert review.verdict is Verdict.CHANGES
    assert review.still_open() == {"R1-1"}


@pytest.mark.parametrize(
    "data",
    [
        _review(
            "APPROVE", [{"id": "R1-1", "file": "f", "problem": "p", "fix": "x"}], []
        ),
        _review("APPROVE", [], [{"id": "R1-1", "status": "open"}]),
        _review("CHANGES", [], [{"id": "R1-1", "status": "fixed"}]),
        _review("MAYBE", [], []),
        {"verdict": "APPROVE", "issues": []},
        "not an object",
    ],
    ids=[
        "approve-with-issue",
        "approve-with-open",
        "changes-with-nothing",
        "verdict",
        "missing",
        "type",
    ],
)
def test_a_review_the_loop_cannot_act_on_is_refused(data: object) -> None:
    with pytest.raises(ReplyShapeError):
        parse_review(data)


def test_a_developer_report_parses() -> None:
    report = parse_dev_report(
        {
            "answers": [{"id": "R1-1", "answer": "rebuttal", "detail": "wrong"}],
            "summary": "s",
            "pr_title": "t",
            "pr_body": "b",
        }
    )

    assert report.answers[0].answer is Answer.REBUTTAL
    assert not report.claims_a_fix()


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/anhembedded/Sagittarius_Elite_Warrior",
        "https://github.com/anhembedded/Sagittarius_Elite_Warrior.git",
        "git@github.com:anhembedded/Sagittarius_Elite_Warrior.git",
    ],
)
def test_the_repository_is_read_from_the_origin_remote(url: str) -> None:
    assert repository_from_remote(url) == "anhembedded/Sagittarius_Elite_Warrior"
