"""The composition root: read the arguments, build the parts, run, report.

Exit status: 0 when the pull request is ready to merge (or, with
`--local-only`, when the reviewer approved the local branch); 1 when a person
is needed (rounds used up, a finding nobody agrees on, the gate timed out);
2 when a tool failed (git, gh, claude).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .claude_runner import (
    ClaudeCallError,
    CliClaudeRunner,
    CliSettings,
    ToolPolicy,
    scrubbed_environment,
)
from .commit_tier import CommitTier
from .github import GhCliGitHub, GitHubError
from .loop import LoopEnd, LoopSettings, ReviewLoop, RunRecord
from .publish import Clock, GateSettings, PipelineEnd, Publisher, PublishParts
from .roles import Developer, Reviewer, RoleError
from .workspace import PROTECTED_BRANCHES, GitError, Workspace, open_workspace

_log = logging.getLogger("App.ReviewLoop")
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_REMOTE = re.compile(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$")

EXIT_DONE = 0
EXIT_NEEDS_HUMAN = 1
EXIT_TOOL_FAILED = 2


def developer_policy(python: str) -> ToolPolicy:
    """The developer edits, tests and commits. It cannot push, merge or
    rewrite history; the loop pushes only after the reviewer approves."""
    return ToolPolicy(
        tools=None,
        allowed=(
            "Read",
            "Edit",
            "Write",
            "Glob",
            "Grep",
            "Bash(git add:*)",
            "Bash(git commit:*)",
            "Bash(git status:*)",
            "Bash(git diff:*)",
            "Bash(git log:*)",
            "Bash(git show:*)",
            "Bash(git mv:*)",
            "Bash(git rm:*)",
            f"Bash({python} -m pytest:*)",
            f"Bash({python} -m ruff:*)",
            f"Bash({python} -m mypy:*)",
            "Bash(pwsh -NoProfile -File scripts/ci-local.ps1:*)",
            "Bash(python3 scripts/render_task_counts.py)",
            "Bash(python3 scripts/check_skill_prompt_references.py)",
        ),
        denied=(
            "Bash(git push:*)",
            "Bash(git merge:*)",
            "Bash(git rebase:*)",
            "Bash(git reset:*)",
            "Bash(git commit --amend:*)",
        ),
        permission_mode="acceptEdits",
    )


def commit_tier_commands(python: str, base: str) -> tuple[tuple[str, ...], ...]:
    """`ci-rule.md` §1, "Every Commit": the commit tier, the architecture
    guards, and the commit-message lint CI runs on the pull request."""
    return (
        (python, "scripts/check_commit_messages.py", f"{base}..HEAD"),
        ("pwsh", "-NoProfile", "-File", "scripts/ci-local.ps1", "-SkipTests"),
        (
            python,
            "-m",
            "pytest",
            "tests/unit/architecture",
            "-q",
            "-p",
            "no:cacheprovider",
        ),
    )


def repository_from_remote(url: str) -> str:
    match = _REMOTE.search(url.strip())
    if match is None:
        raise GitError(f"origin is not a github.com remote: {url}")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = _repo_root()
    try:
        workspace = open_workspace(root)
        _refuse_unsafe_start(workspace)
        record = RunRecord(
            root / ".review-loop" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        _configure_logging(record.root)
        return _run(args, workspace, record)
    except (GitError, GitHubError, ClaudeCallError, RoleError) as exc:
        _log.error("[review-loop] stopped by a tool failure: %s", exc)
        return EXIT_TOOL_FAILED


def _run(args: argparse.Namespace, workspace: Workspace, record: RunRecord) -> int:
    root = workspace.root
    python = args.python or _default_python(root)
    extra_env = {"PYTHONPATH": str(root.parent), "QT_QPA_PLATFORM": "offscreen"}
    runner = CliClaudeRunner(
        CliSettings(
            _tool(args.claude),
            root,
            args.budget_usd,
            args.call_timeout_min * 60,
            extra_env,
        )
    )
    reviewer = Reviewer(runner)
    # Diffs and the commit lint compare against the remote's base, fetched now,
    # so a stale local base never widens the change under review.
    workspace.fetch(args.base)
    remote_base = f"origin/{args.base}"
    commit_tier = CommitTier(
        commit_tier_commands(python, remote_base),
        root,
        scrubbed_environment(os.environ, extra_env),
    )
    loop = ReviewLoop(
        workspace,
        (Developer(runner, developer_policy(python)), reviewer),
        (commit_tier, record),
        LoopSettings(args.task, remote_base, args.max_rounds, args.stuck_after),
    )
    _log.info(
        "[review-loop] start: task %s, branch %s, base %s, run record %s",
        args.task,
        workspace.branch(),
        args.base,
        record.root,
    )
    if args.local_only:
        result = loop.run(())
        done = result.end is LoopEnd.APPROVED
        _summarise(record, {"end": result.end, "reason": result.reason}, reviewer)
        return EXIT_DONE if done else EXIT_NEEDS_HUMAN
    repository = args.repository or repository_from_remote(workspace.remote_url())
    publisher = Publisher(
        PublishParts(loop, workspace, GhCliGitHub(_tool("gh"), repository), record),
        GateSettings(
            args.base,
            args.gate_check,
            args.gate_timeout_min * 60,
            args.settle_timeout_min * 60,
            60.0,
            args.max_publishes,
        ),
        Clock(time.monotonic, time.sleep),
    )
    outcome = publisher.run()
    _summarise(
        record,
        {"end": outcome.end, "reason": outcome.reason, "pr": outcome.pr_url},
        reviewer,
    )
    return EXIT_DONE if outcome.end is PipelineEnd.READY_TO_MERGE else EXIT_NEEDS_HUMAN


def _refuse_unsafe_start(workspace: Workspace) -> None:
    branch = workspace.branch()
    if branch in PROTECTED_BRANCHES:
        raise GitError(f"refusing to run on {branch}: work on a feature branch")
    if not workspace.is_clean():
        raise GitError(
            "the working tree has uncommitted changes: commit or stash them first"
        )


def _summarise(
    record: RunRecord, outcome: dict[str, object], reviewer: Reviewer
) -> None:
    summary = {
        **outcome,
        "reviewer_session": reviewer.session_id,
        "record": str(record.root),
    }
    (record.root / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    _log.info("[review-loop] end: %s", json.dumps(summary))
    print(json.dumps(summary))


def _configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    app = logging.getLogger("App")
    app.setLevel(logging.INFO)
    app.propagate = False
    for handler in (
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(directory / "loop.log"),
    ):
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        app.addHandler(handler)


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise GitError(f"{name} is not on PATH")
    return path


def _default_python(root: Path) -> str:
    venv = root / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found above this script")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev_review_loop",
        description="Developer and reviewer sessions in a loop until merge-ready.",
    )
    parser.add_argument(
        "--task", required=True, help="the task file the developer delivers"
    )
    parser.add_argument("--base", default="master-warrior")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--stuck-after", type=int, default=2)
    parser.add_argument("--max-publishes", type=int, default=3)
    parser.add_argument("--budget-usd", type=float, default=5.0, help="per claude call")
    parser.add_argument("--call-timeout-min", type=float, default=45.0)
    parser.add_argument("--gate-check", default="ci-local.ps1 -Full")
    parser.add_argument("--gate-timeout-min", type=float, default=90.0)
    parser.add_argument(
        "--settle-timeout-min",
        type=float,
        default=15.0,
        help="how long every other check and status may take after the review",
    )
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--python", default=None)
    parser.add_argument(
        "--repository", default=None, help="owner/name; default: origin"
    )
    parser.add_argument(
        "--local-only", action="store_true", help="stop at local APPROVE"
    )
    return parser
