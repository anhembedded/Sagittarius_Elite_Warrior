"""`EPIC-047H` - the ledger, the measured cost and the settings' bounds."""

from __future__ import annotations

import math

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_costs import (
    PLANNING_WEIGHT,
    ExpectedCosts,
    ReadKind,
    measured_weight,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_weight_ledger import (
    WeightLedger,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    CEILING_DEFAULT_PCT,
    REFRESH_INTERVAL_DEFAULT_S,
    REFRESH_INTERVAL_LOWEST_S,
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)


def test_there_is_room_until_the_ceiling_and_then_a_wait_for_the_oldest_to_age_out() -> (
    None
):
    ledger = WeightLedger()
    ledger.charge(40, at=0.0)
    ledger.charge(30, at=20.0)

    assert ledger.seconds_until_room(2, ceiling=72, now=21.0) == 0
    assert ledger.seconds_until_room(15, ceiling=72, now=21.0) == pytest.approx(39.0)
    assert ledger.seconds_until_room(15, ceiling=72, now=61.0) == 0


def test_a_read_dearer_than_the_ceiling_never_fits() -> None:
    assert math.isinf(WeightLedger().seconds_until_room(73, ceiling=72, now=0.0))


def test_the_window_forgets_what_is_a_minute_old() -> None:
    ledger = WeightLedger()
    ledger.charge(50, at=0.0)

    assert ledger.spent(59.9) == 50
    assert ledger.spent(60.0) == 0


def _reading(used: int | None, seen_at: float | None) -> WeightReading:
    return WeightReading(used, 2400, seen_at, routine_open=True)


def test_the_measured_cost_is_the_rise_of_the_header_in_the_same_minute() -> None:
    assert measured_weight(_reading(100, 1200.5), _reading(130, 1203.0), 15) == 30


def test_no_answer_seen_in_between_costs_nothing_and_a_crossed_minute_is_overstated() -> (
    None
):
    assert measured_weight(_reading(100, 1200.5), _reading(100, 1200.5), 15) == 0
    assert measured_weight(_reading(900, 1199.0), _reading(40, 1201.0), 15) == 40


def test_an_unseen_header_costs_the_planning_figure() -> None:
    assert measured_weight(_reading(None, None), _reading(None, None), 15) == 15


def test_one_dear_read_does_not_become_the_cost_of_every_read_after_it() -> None:
    costs = ExpectedCosts()

    costs.observe(
        ReadKind.FACTS, 81
    )  # the cold read: the position mode and the Multi-Assets mode
    assert costs.expected(ReadKind.FACTS) == PLANNING_WEIGHT[ReadKind.FACTS]
    costs.observe(ReadKind.FACTS, 20)
    costs.observe(ReadKind.FACTS, 20)

    assert costs.expected(ReadKind.FACTS) == 20


def test_reads_that_keep_costing_more_than_planned_raise_the_expectation_never_below_the_figure() -> (
    None
):
    costs = ExpectedCosts()
    for weight in (3, 2, 3):
        costs.observe(ReadKind.FACTS, weight)
    assert costs.expected(ReadKind.FACTS) == PLANNING_WEIGHT[ReadKind.FACTS]

    for weight in (44, 44, 44):
        costs.observe(ReadKind.FACTS, weight)

    assert costs.expected(ReadKind.FACTS) == 44


@pytest.mark.parametrize(
    ("interval", "pct", "interval_is", "pct_is"),
    [
        (120, 3, 120, 3.0),
        (0, 3, 0, 3.0),
        (5, 3, REFRESH_INTERVAL_LOWEST_S, 3.0),
        (-1, 3, REFRESH_INTERVAL_DEFAULT_S, 3.0),
        (120, 0, 120, CEILING_DEFAULT_PCT),
        (120, 70, 120, 10.0),
    ],
)
def test_settings_are_judged_inside_their_bounds(
    interval: float, pct: float, interval_is: int, pct_is: float
) -> None:
    settings = VpsFeedSettings.judged(interval, pct, True)

    assert (settings.refresh_interval_s, settings.ceiling_pct) == (interval_is, pct_is)
    assert settings.refresh_enabled is (interval_is > 0)
