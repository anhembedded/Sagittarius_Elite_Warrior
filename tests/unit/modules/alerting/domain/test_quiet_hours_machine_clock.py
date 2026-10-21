"""`EPIC-036D6` (review of PR #666) — a quiet period with no zone is read on the machine's own
clock, instant by instant, daylight saving included. The OS zone is set with `TZ` so the test
does not depend on where it runs."""

from __future__ import annotations

import time as clock
from datetime import UTC, datetime, time

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours

pytestmark = pytest.mark.skipif(
    not hasattr(clock, "tzset"), reason="the machine's zone cannot be set here"
)


@pytest.fixture
def machine_in(monkeypatch: pytest.MonkeyPatch):
    def set_zone(name: str) -> None:
        monkeypatch.setenv("TZ", name)
        clock.tzset()

    yield set_zone
    monkeypatch.undo()
    clock.tzset()


def test_the_machines_clock_decides_not_utc(machine_in) -> None:
    machine_in("Asia/Ho_Chi_Minh")  # UTC+7, no daylight saving
    night = QuietHours(time(22, 0), time(7, 0), None)

    assert night.contains(datetime(2026, 1, 15, 16, 0, tzinfo=UTC))  # 23:00 there
    assert not night.contains(datetime(2026, 1, 15, 2, 0, tzinfo=UTC))  # 09:00 there
    assert not night.contains(datetime(2026, 1, 15, 5, 0, tzinfo=UTC))  # 12:00 there


def test_daylight_saving_moves_the_machines_night(machine_in) -> None:
    machine_in("America/New_York")
    night = QuietHours(time(22, 0), time(7, 0), None)

    assert night.contains(datetime(2026, 1, 15, 11, 30, tzinfo=UTC))  # 06:30 EST
    assert not night.contains(datetime(2026, 7, 15, 11, 30, tzinfo=UTC))  # 07:30 EDT
