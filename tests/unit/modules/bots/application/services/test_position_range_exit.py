"""`EPIC-039H` (O6) - what a position venue's bot does when the mark price leaves the range.

@details `hold` (the default) idles at the exposure the bot has; `close` stops with the position
closed at market and the reason `RANGE_EXIT`. Spot only ever holds, so a definition that asks it to
close is refused in the one sentence every judge shares (`exposure_refusal`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_LIMITS,
    exposure_limits_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exposure_check import (
    exposure_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
    RangeExit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_position_world,
)

S = BotLifecycleState
D = Decimal

#: The world's range is 100..140, its stop loss `price:90` and its take profit `price:150`.
_BELOW_RANGE_ABOVE_STOP = "95"
_ABOVE_RANGE_BELOW_TAKE_PROFIT = "145"
_CLOSE = {**CONFIG, "on_range_exit": "close"}


def test_a_definition_that_says_nothing_holds_out_of_range_and_keeps_its_bytes() -> (
    None
):
    params = GridParams.from_config(CONFIG)

    assert params.on_range_exit is RangeExit.HOLD
    assert "on_range_exit" not in params.to_config()


def test_close_is_read_and_written_back() -> None:
    params = GridParams.from_config(_CLOSE)

    assert params.on_range_exit is RangeExit.CLOSE
    assert params.to_config()["on_range_exit"] == "close"


def test_an_unreadable_range_exit_names_the_key() -> None:
    with pytest.raises(GridParamsError, match="on_range_exit"):
        GridParams.from_config({**CONFIG, "on_range_exit": "flee"})


def test_spot_refuses_to_close_out_of_range_and_a_position_venue_allows_it() -> None:
    params = GridParams.from_config(_CLOSE)
    futures = exposure_limits_of(TradingVenue.FUTURES_TESTNET, GRID_MARKETS)

    refused = exposure_refusal(params, SPOT_LIMITS)

    assert refused is not None
    assert refused.severity is VerdictSeverity.REFUSED
    assert refused.code == "RANGE_EXIT_NOT_ALLOWED"
    assert exposure_refusal(params, futures) is None


@pytest.mark.parametrize(
    "mark", [_BELOW_RANGE_ABOVE_STOP, _ABOVE_RANGE_BELOW_TAKE_PROFIT]
)
def test_close_stops_the_bot_when_the_mark_leaves_the_range_on_either_side(
    mark: str,
) -> None:
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING, config=_CLOSE)
    marks.mark = D(mark)

    world.executor.facts.on_price_age_check()

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.RANGE_EXIT
    assert world.book.open == {}
    assert mark in world.runtime().reason_detail


@pytest.mark.parametrize(
    "mark", [_BELOW_RANGE_ABOVE_STOP, _ABOVE_RANGE_BELOW_TAKE_PROFIT]
)
def test_hold_idles_out_of_range_and_keeps_the_bot_running(mark: str) -> None:
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING)
    marks.mark = D(mark)

    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING


@pytest.mark.parametrize("mark", ["100", "121", "140"])
def test_close_leaves_a_mark_on_or_inside_the_range_edges_alone(mark: str) -> None:
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING, config=_CLOSE)
    marks.mark = D(mark)

    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING


def test_a_stop_loss_beyond_the_range_still_names_the_stop_loss_not_the_range_exit() -> (
    None
):
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING, config=_CLOSE)
    marks.mark = D(89)

    world.executor.facts.on_price_age_check()

    assert world.runtime().reason is GridReason.STOP_LOSS
