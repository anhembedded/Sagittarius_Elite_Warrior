"""Test doubles for the dev/review loop, each a subclass of the port it stands
in for (`testing-rule.md` §2), plus a real git repository on `tmp_path`."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.review_loop.claude_runner import (
    ClaudeCall,
    ClaudeReply,
    ClaudeRunner,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.cli import developer_policy
from Sagittarius_Elite_Warrior.scripts.review_loop.commit_tier import CommitTier
from Sagittarius_Elite_Warrior.scripts.review_loop.github import (
    GateLogs,
    GateRun,
    GitHub,
    HeadState,
    PullRequest,
    PullRequestDraft,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.loop import (
    LoopSettings,
    ReviewLoop,
    RunRecord,
)
from Sagittarius_Elite_Warrior.scripts.review_loop.roles import Developer, Reviewer
from Sagittarius_Elite_Warrior.scripts.review_loop.workspace import (
    Workspace,
    open_workspace,
)

Step = Callable[[ClaudeCall], ClaudeReply]
_GIT = shutil.which("git") or "git"


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        [_GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def make_repo(root: Path) -> Path:
    """A repository whose base branch `master-warrior` has one commit, with a
    feature branch checked out and a bare `origin` it can push to."""
    origin = root / "origin.git"
    subprocess.run([_GIT, "init", "-q", "--bare", str(origin)], check=True)
    repo = root / "checkout"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "master-warrior")
    git(repo, "config", "user.email", "dev@example.com")
    git(repo, "config", "user.name", "dev")
    (repo / ".gitignore").write_text(".review-loop/\n", encoding="utf-8")
    (repo / "app.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "master-warrior")
    git(repo, "checkout", "-q", "-b", "feature")
    return repo


def commit_file(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"change {name}")


def reply(session: str, structured: object) -> ClaudeReply:
    return ClaudeReply(session, structured, "", False, "success", 0.01)


def dev_step(
    session: str, answers: list[dict[str, str]], action: Callable[[], None]
) -> Step:
    def step(_call: ClaudeCall) -> ClaudeReply:
        action()
        body = {
            "answers": answers,
            "summary": "done",
            "pr_title": "feat: x",
            "pr_body": "## What",
        }
        return reply(session, body)

    return step


def review_step(
    session: str,
    verdict: str,
    issues: list[dict[str, str]],
    prior: list[dict[str, str]] | None = None,
) -> Step:
    body = {
        "verdict": verdict,
        "issues": issues,
        "prior_issues": prior or [],
        "comment": "review\n\n## Coverage Disclosure\n| A | ok |",
    }
    return lambda _call: reply(session, body)


def issue(issue_id: str) -> dict[str, str]:
    return {
        "id": issue_id,
        "file": "app.txt",
        "problem": f"problem {issue_id}",
        "fix": "fix it",
    }


@dataclass
class ScriptedClaude(ClaudeRunner):
    """Answers each call with the next scripted step; one script per role."""

    developer: list[Step]
    reviewer: list[Step]
    calls: list[ClaudeCall] = field(default_factory=list)

    def run(self, call: ClaudeCall) -> ClaudeReply:
        self.calls.append(call)
        queue = (
            self.reviewer
            if call.policy.tools == ("Read", "Glob", "Grep")
            else self.developer
        )
        if not queue:
            raise AssertionError(f"no scripted reply left for: {call.prompt[:80]}")
        return queue.pop(0)(call)

    def reviewer_calls(self) -> list[ClaudeCall]:
        return [c for c in self.calls if c.policy.tools == ("Read", "Glob", "Grep")]

    def developer_calls(self) -> list[ClaudeCall]:
        return [c for c in self.calls if c.policy.tools != ("Read", "Glob", "Grep")]


@dataclass
class FakeGitHub(GitHub):
    """Gate conclusions are handed out in order, one per head asked about."""

    conclusions: list[str]
    unfinished_polls: int = 0
    pulls: list[PullRequestDraft] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    head_states: list[HeadState] = field(default_factory=list)

    def ensure_pull_request(self, draft: PullRequestDraft) -> PullRequest:
        self.pulls.append(draft)
        return PullRequest(7, "https://github.example/pull/7")

    def finished_gate(self, head_sha: str, check_name: str) -> GateRun | None:
        if self.unfinished_polls > 0:
            self.unfinished_polls -= 1
            return None
        return GateRun(
            len(self.comments) + 1, 99, self.conclusions.pop(0), "https://gate"
        )

    def download_gate_logs(self, gate: GateRun, directory: Path) -> GateLogs:
        directory.mkdir(parents=True, exist_ok=True)
        job = directory / "job.log"
        job.write_text(
            f"RESULT: {gate.conclusion}\nFAILED_STEPS: none\n", encoding="utf-8"
        )
        return GateLogs(job, None)

    def post_comment(self, pull_number: int, body: str) -> str:
        self.comments.append(body)
        return "https://github.example/pull/7#comment"

    def head_state(self, head_sha: str) -> HeadState:
        """The scripted states in order, then green for good."""
        return self.head_states.pop(0) if self.head_states else HeadState((), ())


def green_tier(repo: Path) -> CommitTier:
    """Red exactly while a file named BROKEN is committed."""
    check = "import pathlib,sys; sys.exit(1 if pathlib.Path('BROKEN').exists() else 0)"
    return CommitTier(((sys.executable, "-c", check),), repo, {})


def build_loop(repo: Path, claude: ScriptedClaude, max_rounds: int = 5) -> ReviewLoop:
    workspace: Workspace = open_workspace(repo)
    record = RunRecord(repo / ".review-loop" / "run")
    return ReviewLoop(
        workspace,
        (Developer(claude, developer_policy("python")), Reviewer(claude)),
        (green_tier(repo), record),
        LoopSettings("Tasks/backlog/BOT-1_x.md", "master-warrior", max_rounds, 2),
    )
