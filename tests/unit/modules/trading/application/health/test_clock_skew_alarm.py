"""`BUG-209` — a clock that drifts during a run is a WARNING, then an ERROR, then an INFO.

The pre-flight judges the clock once before the run; afterwards the only trace of drift was
`skew_ms` on the INFO health line. The alarm uses the pre-flight's thresholds
(500 ms passes, 501 warns, 999 warns, 1000 fails) and logs the **change of level**, not each
measurement, so a probe that runs every health interval stays quiet while the clock does.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.health.clock_skew_alarm import (
    ClockSkewAlarm,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.health.clock_skew_probe import (
    ClockSkewProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.clock_skew_recorder import (
    ClockSkewRecorder,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.preflight.preflight_world import (
    reads_over,
    status,
    venue,
)

LOGGER = "App.Trading.ClockSkew"
FUTURES = TradingVenue.FUTURES_TESTNET


def _levels(caplog: pytest.LogCaptureFixture) -> list[int]:
    return [r.levelno for r in caplog.records if r.name == LOGGER]


@pytest.mark.parametrize(
    ("skew_ms", "expected"),
    [
        (0, []),
        (500, []),
        (-500, []),
        (501, [logging.WARNING]),
        (-999, [logging.WARNING]),
        (999, [logging.WARNING]),
        (1000, [logging.ERROR]),
        (-1000, [logging.ERROR]),
        (5000, [logging.ERROR]),
    ],
)
def test_the_levels_are_the_preflights_boundaries(
    caplog: pytest.LogCaptureFixture, skew_ms: int, expected: list[int]
) -> None:
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        ClockSkewAlarm().observe("futures_testnet", skew_ms)

    assert _levels(caplog) == expected


def test_a_drifting_clock_warns_once_not_each_interval(
    caplog: pytest.LogCaptureFixture,
) -> None:
    alarm = ClockSkewAlarm()

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        for skew in (600, 650, 700, 640):
            alarm.observe("futures_testnet", skew)

    assert _levels(caplog) == [logging.WARNING]


def test_the_story_of_a_drift_is_warning_error_warning_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    alarm = ClockSkewAlarm()

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        for skew in (100, 700, 1200, 1300, 800, 90, 80):
            alarm.observe("futures_testnet", skew)

    assert _levels(caplog) == [
        logging.WARNING,
        logging.ERROR,
        logging.WARNING,
        logging.INFO,
    ]
    assert "[clock-skew-recovered]" in caplog.records[-1].getMessage()


def test_a_measurement_that_found_nothing_changes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    alarm = ClockSkewAlarm()

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        alarm.observe("futures_testnet", 700)
        alarm.observe("futures_testnet", None)
        alarm.observe("futures_testnet", 710)

    assert _levels(caplog) == [logging.WARNING]


def test_two_venues_are_judged_separately(caplog: pytest.LogCaptureFixture) -> None:
    alarm = ClockSkewAlarm()

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        alarm.observe("futures_testnet", 700)
        alarm.observe("spot_testnet", 700)

    assert _levels(caplog) == [logging.WARNING, logging.WARNING]


def test_the_probe_raises_the_alarm_for_what_it_measures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = ClockSkewProbe(
        reads_over(venue(FUTURES, status(FUTURES, skew_ms=1200))),
        ClockSkewRecorder(),
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        probe.measure()
        probe.measure()

    assert _levels(caplog) == [logging.ERROR], "once, though measured twice"
