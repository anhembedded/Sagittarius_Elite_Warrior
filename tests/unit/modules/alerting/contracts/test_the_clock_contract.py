"""`IAlertClock`: the real clock and the fake obey one suite (HLD §10.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.system_alert_clock import (
    SystemAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.contract_alert_clock import (
    AlertClockContract,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FAKE_CLOCK_START,
    FakeAlertClock,
)


class TestSystemAlertClock(AlertClockContract):
    @pytest.fixture
    def impl(self) -> IAlertClock:
        return SystemAlertClock()


class TestFakeAlertClock(AlertClockContract):
    @pytest.fixture
    def impl(self) -> IAlertClock:
        return FakeAlertClock()


def test_the_fake_clock_stands_still_until_advanced() -> None:
    clock = FakeAlertClock()

    assert clock.now() == FAKE_CLOCK_START
    assert clock.now() == FAKE_CLOCK_START
    clock.advance(timedelta(minutes=3))
    assert clock.now() == FAKE_CLOCK_START + timedelta(minutes=3)


def test_the_fake_clock_can_start_anywhere() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    assert FakeAlertClock(start).now() == start
