"""The two roles. The developer starts a fresh session every round; the
reviewer keeps one session for the whole pull request (`ONBOARDING.md` §7, one
reviewer session per pull request) and resumes it each round."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace

from .claude_runner import (
    ClaudeCall,
    ClaudeCallError,
    ClaudeReply,
    ClaudeRunner,
    ToolPolicy,
    session_url,
)
from .prompts import reformat_prompt
from .replies import (
    DEV_SCHEMA,
    REVIEW_SCHEMA,
    DevReport,
    ReplyShapeError,
    Review,
    parse_dev_report,
    parse_review,
)

_log = logging.getLogger("App.ReviewLoop")

#: The reviewer reads and searches; it has no tool that writes or runs anything.
REVIEWER_POLICY = ToolPolicy(
    tools=("Read", "Glob", "Grep"), allowed=(), denied=(), permission_mode=None
)


class RoleError(RuntimeError):
    """A role gave no usable reply after its one retry."""


@dataclass(frozen=True)
class _Exchange[T]:
    record: T
    session_id: str


class Developer:
    """A fresh session every round. Each session is given its id up front, so
    its commits can carry the `Claude-Session:` trailer that tells them apart
    from the reviewer's comment (`commit-rule.md` §2)."""

    def __init__(
        self,
        runner: ClaudeRunner,
        policy: ToolPolicy,
        new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._runner = runner
        self._policy = policy
        self._new_id = new_id

    def work(self, prompt: str) -> DevReport:
        session_id = self._new_id()
        trailer = (
            "End every commit message with the `Co-Authored-By:` trailer commit-rule.md "
            f"requires and, as its last line, exactly:\nClaude-Session: {session_url(session_id)}"
        )
        call = ClaudeCall(
            f"{prompt}\n\n{trailer}",
            DEV_SCHEMA,
            self._policy,
            resume=None,
            session_id=session_id,
        )
        exchange = _ask(self._runner, call, parse_dev_report)
        _log.info("[review-loop] developer session %s answered", exchange.session_id)
        return exchange.record


class Reviewer:
    """One session for the whole pull request: given its id on the first call,
    resumed on every later one."""

    def __init__(
        self,
        runner: ClaudeRunner,
        new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._runner = runner
        self._new_id = new_id
        self._session_id: str | None = None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def review(self, prompt: str) -> Review:
        """One review in the reviewer's own session, resumed after the first."""
        call = ClaudeCall(
            prompt,
            REVIEW_SCHEMA,
            REVIEWER_POLICY,
            resume=self._session_id,
            session_id=None if self._session_id else self._new_id(),
        )
        exchange = _ask(self._runner, call, parse_review)
        self._session_id = exchange.session_id
        _log.info(
            "[review-loop] reviewer session %s: %s",
            exchange.session_id,
            exchange.record.verdict,
        )
        return exchange.record


def _ask[T](
    runner: ClaudeRunner, call: ClaudeCall, parse: Callable[[object], T]
) -> _Exchange[T]:
    reply = _run_with_one_retry(runner, call)
    try:
        return _Exchange(parse(reply.structured), reply.session_id)
    except ReplyShapeError as exc:
        _log.warning(
            "[review-loop] reply did not match its schema (%s); asking again", exc
        )
        problem = str(exc)
    follow_up = ClaudeCall(
        reformat_prompt(problem), call.schema, call.policy, resume=reply.session_id
    )
    second = _run_with_one_retry(runner, follow_up)
    try:
        return _Exchange(parse(second.structured), second.session_id)
    except ReplyShapeError as exc:
        raise RoleError(
            f"reply still malformed after a reformat request: {exc}"
        ) from exc


def _run_with_one_retry(runner: ClaudeRunner, call: ClaudeCall) -> ClaudeReply:
    failure = ""
    for attempt in (1, 2):
        if attempt > 1 and call.session_id is not None:
            # The failed attempt may have created the session; a retry under the
            # same id would be refused, so it starts under a fresh one.
            call = replace(call, session_id=str(uuid.uuid4()))
        try:
            reply = runner.run(call)
        except ClaudeCallError as exc:
            failure = str(exc)
        else:
            if not reply.is_error:
                return reply
            failure = f"claude reported an error ({reply.subtype}): {reply.text[:500]}"
        _log.warning(
            "[review-loop] claude call attempt %d failed: %s", attempt, failure
        )
    raise RoleError(failure)
