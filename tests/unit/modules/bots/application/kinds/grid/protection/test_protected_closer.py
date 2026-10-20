"""`EPIC-039L` (decision D6) - the stop is taken down only once the bot's exposure is closed.

@details The decorator is shown against the real `IExposureCloser` contract with an inner closer
that answers as the position venue's does: `None` when the bot's own position is closed (or a
remainder below one market step, or what a position by hand leaves), otherwise how the stop ended.
The mutation that matters is the order: release the protection before the close, and a close that
fails leaves a leveraged position with nothing standing over it."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protected_closer import (
    ProtectedCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
    ProtectionVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)


class _Closer(IExposureCloser):
    def __init__(self, answer: StopProgress | None, calls: list[str]) -> None:
        self._answer = answer
        self._calls = calls

    def closes_on_halt(self) -> bool:
        return True

    def close(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        self._calls.append("close")
        return self._answer


class _Protection(IExposureProtection):
    def __init__(self, released: bool, calls: list[str]) -> None:
        self._released = released
        self._calls = calls

    def protect(self, plan: GridPlan) -> bool:
        return True

    def supervise(self) -> ProtectionVerdict:
        return ProtectionVerdict.OK

    def describe_stop(self) -> str:
        return ""

    def read_coverage(self) -> StopCoverageReading:
        return StopCoverageReading(StopCoverage.NOT_APPLICABLE)

    def release(self) -> bool:
        self._calls.append("release")
        return self._released


def _closed(
    answer: StopProgress | None, *, released: bool = True
) -> tuple[StopProgress | None, list[str]]:
    calls: list[str] = []
    closer = ProtectedCloser(
        Mock(), _Closer(answer, calls), _Protection(released, calls)
    )
    return closer.close(OwnerBudgetRegistrationResult(None), Decimal(64000)), calls


def test_the_stop_is_released_after_the_close_and_never_before() -> None:
    progress, calls = _closed(None)

    assert progress is None
    assert calls == ["close", "release"]


@pytest.mark.parametrize(
    "unfinished",
    [
        StopProgress.WAITING_ON_EXCHANGE,
        StopProgress.WAITING_FOR_TRADING,
        StopProgress.ENDED,
    ],
)
def test_a_close_that_did_not_finish_leaves_the_stop_standing(
    unfinished: StopProgress,
) -> None:
    progress, calls = _closed(unfinished)

    assert progress is unfinished
    assert calls == ["close"]


def test_a_stop_that_could_not_be_cancelled_keeps_the_stop_sequence_waiting() -> None:
    progress, calls = _closed(None, released=False)

    assert progress is StopProgress.WAITING_ON_EXCHANGE
    assert calls == ["close", "release"]
