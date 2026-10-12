"""What one pre-flight check found, as a value (`EPIC-038F`).

A check never prints and never exits: it returns a `CheckResult`, and the
`preflight` command turns the results into a `Report` and an exit code. The
result holds *findings*, one per thing the check looked at (a venue, a
directory), so a check that covers three venues says which of them is wrong
instead of folding the three into one sentence.

`CheckCause` exists for the exit code and nothing else: a failed finding says
whether the fault is the operator's configuration, the exchange being out of
reach, or neither, because a supervisor keys its restart policy on that
(`ExitCode.CONFIGURATION` is never retried, `ExitCode.EXCHANGE` is).

**No secret ever goes into a finding.** `reason` and `remedy` are sentences an
operator reads and a monitor stores; a key, a secret or a signed URL in either
would reach a terminal, a journal and a JSON file. `test_no_secret_value_appears_
in_the_report` greps the rendered report for the fake key and secret.

@par Extension cases
  · a new thing a check can be wrong about — a new `subject` string, no type
    changes;
  · a new fault class that deserves its own exit code — a `CheckCause` member
    and one row in `preflight_outcome`'s table (a test fails until it exists).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class CheckStatus(IntEnum):
    """How bad a finding is; the order is the severity, so `max()` is the worst."""

    PASS = 0
    WARN = 1
    FAIL = 2


class CheckCause(IntEnum):
    """Why a finding failed, for the exit code; the order is the precedence."""

    #: A plain failure of the machine or of what the check measured (exit 4).
    NONE = 0
    #: The exchange could not be reached or was out of service; a restart can
    #: outlast it (exit 6, restarted with a delay).
    EXCHANGE = 1
    #: Only the operator can fix it: no key, a key the exchange rejects, a key that
    #: can withdraw (exit 5, never restarted).
    CONFIGURATION = 2


@dataclass(frozen=True, slots=True)
class CheckFinding:
    """One thing a check looked at, and what it found."""

    #: What was looked at: a venue name, a directory, `""` for the machine.
    subject: str
    status: CheckStatus
    #: A plain-language sentence; never a secret.
    reason: str
    #: What the operator does about it; empty for a `PASS`.
    remedy: str = ""
    cause: CheckCause = CheckCause.NONE


class CheckOrigin(str, Enum):
    """Where a result came from, so a report can tell a finding from a fault in the check."""

    #: The check ran and answered.
    ANSWERED = "answered"
    #: The check raised; the runner turned that into a `FAIL`.
    CRASHED = "crashed"
    #: The check did not answer within its deadline.
    TIMED_OUT = "timed_out"
    #: The operator asked for this check to be skipped.
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Everything one check found; `status` is the worst of its findings."""

    check_id: str
    title: str
    findings: tuple[CheckFinding, ...]
    origin: CheckOrigin = CheckOrigin.ANSWERED

    def __post_init__(self) -> None:
        if not self.findings:
            raise ValueError(
                f"check {self.check_id!r} returned no finding: a check that looked at "
                "nothing says so with a WARN, it does not return an empty result"
            )

    @property
    def status(self) -> CheckStatus:
        return max(finding.status for finding in self.findings)

    @property
    def cause(self) -> CheckCause:
        """The strongest cause among the failed findings; `NONE` when none failed."""
        failed = [f.cause for f in self.findings if f.status is CheckStatus.FAIL]
        return max(failed, default=CheckCause.NONE)

    @classmethod
    def single(
        cls,
        check_id: str,
        title: str,
        finding: CheckFinding,
        origin: CheckOrigin = CheckOrigin.ANSWERED,
    ) -> CheckResult:
        return cls(check_id, title, (finding,), origin)
