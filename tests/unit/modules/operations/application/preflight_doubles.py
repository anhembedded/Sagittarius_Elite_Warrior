"""Doubles for the pre-flight tests, built from the ports (`testing-rule.md` §2)."""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
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


class NoPorts:
    """A `PortResolver` for checks that resolve nothing."""

    def resolve[T](self, abstract: type[T]) -> T:
        raise AssertionError(
            f"{abstract.__name__} was resolved; the test arranged none"
        )


class ScriptedCheck(IPreflightCheck):
    """A check that answers what it is told, or does what `action` does."""

    def __init__(
        self,
        check_id: str,
        status: CheckStatus = CheckStatus.PASS,
        action: Callable[[], None] | None = None,
        deadline_seconds: float = 5.0,
    ) -> None:
        self.check_id = check_id
        self.title = f"scripted {check_id}"
        self.deadline_seconds = deadline_seconds
        self._status = status
        self._action = action
        self.runs = 0

    def run(self, scope: PreflightScope) -> CheckResult:
        self.runs += 1
        if self._action is not None:
            self._action()
        return CheckResult.single(
            self.check_id,
            self.title,
            CheckFinding("", self._status, f"{self.check_id} said so"),
        )


def declared(
    check: IPreflightCheck, contributor: str = "test"
) -> PreflightCheckDescriptor:
    return PreflightCheckDescriptor(
        check.check_id, lambda _resolver: check, contributor
    )


def never_returns(release: threading.Event) -> Callable[[], None]:
    """Blocks until the test sets `release`: a check that does not answer."""
    return lambda: release.wait()


def resolver() -> PortResolver:
    return NoPorts()
