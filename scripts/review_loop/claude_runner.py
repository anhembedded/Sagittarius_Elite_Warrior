"""One headless `claude -p` call: the argument vector, the environment, the reply.

Measured on Claude Code 2.1.289 before this was written:

- `--output-format json` returns one object with `session_id`, `result`,
  `is_error`, `subtype` and `total_cost_usd`; with `--json-schema` it also
  carries the validated `structured_output`.
- `--resume <id>` keeps the same `session_id` and the conversation.
- `--allowedTools` only pre-approves. A reviewer allowed `Bash(git diff:*)` still
  wrote a file with `git diff --output=w3.txt`; `--tools Read,Glob,Grep` is what
  takes the writing tools away.
- A `claude` started inside another Claude Code session inherits
  `CLAUDE_CODE_SESSION_ID` and runs as that session; `scrubbed_environment` drops
  the session's variables so every call is its own session.
"""

from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: The variables that bind a process to the Claude Code session it runs in.
SESSION_VARIABLES: frozenset[str] = frozenset(
    {
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CODE_REMOTE_SESSION_ID",
        "CLAUDECODE",
        "CLAUDE_CODE_MESSAGING_SOCKET",
        "CLAUDE_CODE_MESSAGING_TOKEN",
        "CLAUDE_CODE_CHILD_SESSION",
    }
)


class ClaudeCallError(RuntimeError):
    """`claude` exited non-zero, timed out, or printed no JSON reply."""


@dataclass(frozen=True)
class ToolPolicy:
    """What a role may do. `tools` names the only tools that exist in the
    session (`None` keeps the default set); `allowed` pre-approves within them;
    `denied` is refused even where a setting would allow it."""

    tools: tuple[str, ...] | None
    allowed: tuple[str, ...]
    denied: tuple[str, ...]
    permission_mode: str | None


@dataclass(frozen=True)
class ClaudeCall:
    """One call. `resume` continues a session; otherwise `session_id`, when
    set, is the id the new session takes (`--session-id`)."""

    prompt: str
    schema: Mapping[str, object]
    policy: ToolPolicy
    resume: str | None
    session_id: str | None = None


@dataclass(frozen=True)
class ClaudeReply:
    session_id: str
    structured: object
    text: str
    is_error: bool
    subtype: str
    cost_usd: float | None


@dataclass(frozen=True)
class CliSettings:
    executable: str
    cwd: Path
    budget_usd: float
    timeout_s: float
    extra_env: Mapping[str, str]


class ClaudeRunner(ABC):
    """The port each role talks to; the loop never spawns a process itself."""

    @abstractmethod
    def run(self, call: ClaudeCall) -> ClaudeReply: ...


class CliClaudeRunner(ClaudeRunner):
    def __init__(self, settings: CliSettings) -> None:
        self._settings = settings

    def run(self, call: ClaudeCall) -> ClaudeReply:
        argv = build_argv(self._settings, call)
        env = scrubbed_environment(os.environ, self._settings.extra_env)
        try:
            # `S603` is suppressed, not worked around: the vector is built from
            # this module's own literals plus the prompt as one argument, there
            # is no shell, and the executable is the resolved path the CLI
            # entry point checked.
            completed = subprocess.run(  # noqa: S603
                argv,
                cwd=self._settings.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self._settings.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCallError(
                f"claude timed out after {self._settings.timeout_s:.0f}s"
            ) from exc
        if completed.returncode != 0:
            raise ClaudeCallError(
                f"claude exited {completed.returncode}: {completed.stderr[-2000:]}"
            )
        return parse_reply(completed.stdout)


def build_argv(settings: CliSettings, call: ClaudeCall) -> list[str]:
    """The `claude` command line for one call. Every list-valued option uses
    the `--flag=value` form, so a variadic option never swallows the next one."""
    argv = [
        settings.executable,
        "-p",
        call.prompt,
        "--output-format",
        "json",
        f"--json-schema={json.dumps(call.schema)}",
        f"--max-budget-usd={settings.budget_usd}",
    ]
    policy = call.policy
    if policy.tools is not None:
        argv.append(f"--tools={','.join(policy.tools)}")
    if policy.allowed:
        argv.append(f"--allowedTools={','.join(policy.allowed)}")
    if policy.denied:
        argv.append(f"--disallowedTools={','.join(policy.denied)}")
    if policy.permission_mode is not None:
        argv.append(f"--permission-mode={policy.permission_mode}")
    if call.resume is not None:
        argv.append(f"--resume={call.resume}")
    elif call.session_id is not None:
        argv.append(f"--session-id={call.session_id}")
    return argv


def session_url(session_id: str) -> str:
    """The `Claude-Session:` URL for a session id, in the shape
    `check_independent_review.py` and `commit-lint` read."""
    return "https://claude.ai/code/session_" + session_id.replace("-", "")


def scrubbed_environment(
    base: Mapping[str, str], extra: Mapping[str, str]
) -> dict[str, str]:
    """`base` without the calling session's variables, plus `extra`."""
    env = {key: value for key, value in base.items() if key not in SESSION_VARIABLES}
    env.update(extra)
    return env


def parse_reply(stdout: str) -> ClaudeReply:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeCallError(
            f"claude printed no JSON reply: {stdout[:500]!r}"
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("session_id"), str):
        raise ClaudeCallError(f"claude's reply has no session_id: {stdout[:500]!r}")
    cost = data.get("total_cost_usd")
    return ClaudeReply(
        session_id=data["session_id"],
        structured=data.get("structured_output"),
        text=str(data.get("result", "")),
        is_error=bool(data.get("is_error")),
        subtype=str(data.get("subtype", "")),
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
    )
