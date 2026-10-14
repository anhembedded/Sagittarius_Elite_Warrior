"""`EPIC-039H` - a position venue's stop loss and take profit are judged on the mark price.

@details A leveraged position is valued and liquidated at the mark, so the exits of a bot on a
position venue follow it and not the last trade: a wick of the last price that never touched the
mark must not stop the bot, and a mark that crossed must, whatever the last price shows. Spot keeps
judging the streamed last price (`test_grid_executor_exit_states.py`).

Price paid, locked below: the mark is read once per beat of the price watch, so a mark that crossed
and came back between two reads is not seen.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_position_world,
)

S = BotLifecycleState
D = Decimal

#: The world's stop loss is `price:90` and its take profit `price:150`.
_BELOW_STOP_LOSS = D(89)
_ABOVE_TAKE_PROFIT = D(151)


def test_a_wick_of_the_last_price_below_the_stop_loss_does_not_stop_a_position_bot() -> (
    None
):
    world, _ = a_position_world(marks=Marks("121"), state=S.RUNNING)

    world.executor.facts.on_tick(PriceTick(D(121), _BELOW_STOP_LOSS, D(121)))
    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING


def test_a_mark_below_the_stop_loss_stops_the_bot_whatever_the_last_price_shows() -> (
    None
):
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING)
    world.executor.facts.on_tick(PriceTick.at(D(121)))
    marks.mark = _BELOW_STOP_LOSS

    world.executor.facts.on_price_age_check()

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS
    assert world.book.open == {}


def test_a_mark_above_the_take_profit_stops_the_bot() -> None:
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING)
    marks.mark = _ABOVE_TAKE_PROFIT

    world.executor.facts.on_price_age_check()

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.TAKE_PROFIT


def test_a_mark_inside_the_band_leaves_the_bot_running() -> None:
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING)

    world.executor.facts.on_price_age_check()

    assert marks.reads == 1
    assert world.state() is S.RUNNING


def test_a_mark_that_could_not_be_read_judges_nothing_and_is_said_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    marks = Marks("121")
    marks.unreadable = "the exchange did not answer"
    world, _ = a_position_world(marks=marks, state=S.RUNNING)

    with caplog.at_level(logging.WARNING, logger="App.Bots.GridExecutor"):
        world.executor.facts.on_price_age_check()
        world.executor.facts.on_price_age_check()

    said = [r for r in caplog.records if "[mark-exit]" in r.getMessage()]
    assert world.state() is S.RUNNING
    assert len(said) == 1
    marks.unreadable = None
    marks.mark = _BELOW_STOP_LOSS
    world.executor.facts.on_price_age_check()
    assert world.state() is S.STOPPED


def test_a_mark_that_crossed_and_came_back_between_two_reads_is_not_seen() -> None:
    """The price knowingly paid for reading the mark per beat instead of streaming it."""
    marks = Marks("121")
    world, _ = a_position_world(marks=marks, state=S.RUNNING)
    world.executor.facts.on_price_age_check()
    marks.mark = _BELOW_STOP_LOSS
    marks.mark = D(121)

    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING


def test_a_spot_bot_has_no_mark_to_read_and_still_exits_on_the_streamed_price() -> None:
    world = grid_world(state=S.RUNNING)

    world.executor.facts.on_price_age_check()
    world.executor.facts.on_tick(PriceTick.at(_BELOW_STOP_LOSS))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS
