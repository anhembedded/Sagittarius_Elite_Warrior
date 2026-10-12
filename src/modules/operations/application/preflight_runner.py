"""Runs the declared pre-flight checks, each isolated from the others (`EPIC-038F`).

The runner knows no check. It is given the table the modules declared
(`IPreflightCheckTable`) and a `PortResolver`, builds each check from its
factory and runs it; adding a check edits nothing here
(`test_a_new_check_appears_without_editing_the_runner`).

**Isolation.** One check that raises, hangs or cannot be built becomes a `FAIL`
named for that check, and the others still run:

  * it raises -> `CheckOrigin.CRASHED`, with the exception's *type* in the
    report and the traceback in the log. The message stays out of the report
    because an exchange client's exception can carry a signed URL;
  * it does not answer within `deadline_seconds` -> `CheckOrigin.TIMED_OUT`,
    with the check's own `timeout_cause` (a check that waits on the exchange makes
    this exit 6, not 4: a supervisor restarts on 6). A
    thread cannot be killed, so the check keeps running on a daemon thread of
    its own (it cannot keep the process alive) and its eventual answer is
    ignored;
  * its factory raises or builds a check under another id -> crashed, the same.

The checks run one after another, in id order. They share the exchange's
answers through `PreflightScope.once`, and a parallel run would ask the
exchange the same question once per check instead.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckOrigin,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    PortResolver,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)

logger = logging.getLogger("App.Operations.Preflight")

_BUG_IN_THE_CHECK = (
    "This is a fault in the check, not in the machine: the log has the traceback "
    "under the [preflight] tag. Re-run with --skip {check_id} to continue without it."
)


class PreflightRunner:
    def __init__(
        self, descriptors: Sequence[PreflightCheckDescriptor], resolver: PortResolver
    ) -> None:
        self._descriptors = tuple(descriptors)
        self._resolver = resolver

    def check_ids(self) -> tuple[str, ...]:
        return tuple(descriptor.check_id for descriptor in self._descriptors)

    def run(self, scope: PreflightScope) -> tuple[CheckResult, ...]:
        results = tuple(self._run_one(d, scope) for d in self._descriptors)
        logger.info(
            "[preflight] %d checks ran: %s",
            len(results),
            ", ".join(f"{r.check_id}={r.status.name}" for r in results),
        )
        return results

    def _run_one(
        self, descriptor: PreflightCheckDescriptor, scope: PreflightScope
    ) -> CheckResult:
        if descriptor.check_id in scope.skip:
            return _skipped(descriptor.check_id)
        built = self._build(descriptor)
        if isinstance(built, CheckResult):
            return built
        return _run_isolated(built, scope)

    def _build(
        self, descriptor: PreflightCheckDescriptor
    ) -> IPreflightCheck | CheckResult:
        try:
            check = descriptor.factory(self._resolver)
        except Exception:
            logger.warning(
                "[preflight] could not build check %r (declared by %r)",
                descriptor.check_id,
                descriptor.contributor_id,
                exc_info=True,
            )
            return _failed(
                descriptor.check_id,
                descriptor.check_id,
                CheckOrigin.CRASHED,
                f"the check could not be built ({descriptor.contributor_id} declared it)",
            )
        if check.check_id != descriptor.check_id:
            return _failed(
                descriptor.check_id,
                descriptor.check_id,
                CheckOrigin.CRASHED,
                f"declared as {descriptor.check_id!r} but built as {check.check_id!r}",
            )
        return check


def _run_isolated(check: IPreflightCheck, scope: PreflightScope) -> CheckResult:
    answers: list[CheckResult] = []
    crashes: list[Exception] = []

    def work() -> None:
        try:
            answers.append(check.run(scope))
        except Exception as exc:
            logger.warning(
                "[preflight] check %r raised %s",
                check.check_id,
                type(exc).__name__,
                exc_info=True,
            )
            crashes.append(exc)

    thread = threading.Thread(
        target=work, name=f"preflight-{check.check_id}", daemon=True
    )
    thread.start()
    thread.join(check.deadline_seconds)
    if thread.is_alive():
        logger.warning(
            "[preflight] check %r gave no answer within %.1fs",
            check.check_id,
            check.deadline_seconds,
        )
        return _failed(
            check.check_id,
            check.title,
            CheckOrigin.TIMED_OUT,
            f"the check gave no answer within {check.deadline_seconds:g} s",
            check.timeout_cause,
        )
    if crashes:
        return _failed(
            check.check_id,
            check.title,
            CheckOrigin.CRASHED,
            f"the check failed with {type(crashes[0]).__name__}",
        )
    return answers[0]


def _failed(
    check_id: str,
    title: str,
    origin: CheckOrigin,
    reason: str,
    cause: CheckCause = CheckCause.NONE,
) -> CheckResult:
    return CheckResult.single(
        check_id,
        title,
        CheckFinding(
            "",
            CheckStatus.FAIL,
            reason,
            _BUG_IN_THE_CHECK.format(check_id=check_id),
            cause,
        ),
        origin,
    )


def _skipped(check_id: str) -> CheckResult:
    return CheckResult.single(
        check_id,
        check_id,
        CheckFinding(
            "",
            CheckStatus.WARN,
            "skipped at the operator's request (--skip)",
            "Run without --skip before relying on this machine.",
        ),
        CheckOrigin.SKIPPED,
    )
