"""`EPIC-039L` - the exchange's protective stop beside the bot's own exits and the plan's sides.

@details The composed Futures world over the fake: where an exit is a stop loss the exchange's
stop and the bot's own can both act, a NEUTRAL grid whose position changes sign must not keep a
close-all stop on the side that has no position (check T3 unrecorded), and a stop the exchange
ends without a fill (check T2) is not a trigger.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_protective_stop_event import (
    BotProtectiveStopEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_bots_world import booted_futures_bots
from .futures_direction_scenarios import LONG, NEUTRAL, SCENARIOS, DirectionScenario
from .futures_fake_exchange import FUTURES
from .futures_stop_helpers import started, stops
from .grid_fake_exchange import FakeExchange

S = BotLifecycleState
D = Decimal


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.direction.value)
def test_a_mark_price_through_the_upper_exit_ends_flat_whichever_exit_acts_first(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    """With the exchange's stop live, the exit that is a stop loss (SHORT's) is the exchange's
    to run first, and the bot says so; the others (a take profit) are the bot's own."""
    with booted_futures_bots(futures) as app:
        bot_id = started(app, scenario.config)
        futures.urls.futures_book.faults.hold_fills = True

        app.move_price(scenario.mark_through_upper_exit)
        app.ticker.fire()
        app.deliver()

        exchange_ran_first = scenario.upper_exit_reason is GridReason.STOP_LOSS
        assert app.runtime(bot_id).reason is (
            GridReason.PROTECTIVE_STOP_TRIGGERED
            if exchange_ran_first
            else scenario.upper_exit_reason
        )
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}


def test_a_neutral_grid_that_turns_short_keeps_only_the_stop_that_covers_it(
    futures: FakeExchange,
) -> None:
    """Until check T3 is recorded a close-all stop on the side with no position must not
    stand (decision D9): the long side's SELL stop goes once the BUY stop covers the short."""
    with booted_futures_bots(futures) as app:
        bot_id = started(app, NEUTRAL.config)

        app.move_price(D(62900))
        app.ticker.fire()
        app.deliver()
        assert app.position() > 0
        assert [stop["side"] for stop in stops(app)] == ["SELL"]

        for price in (D(64100), D(65100)):
            app.move_price(price)
        app.ticker.fire()
        app.deliver()
        app.ticker.fire()
        app.deliver()

        assert app.position() < 0
        assert [stop["side"] for stop in stops(app)] == ["BUY"]
        assert {s.side for s in app.runtime(bot_id).protective_stops} == {OrderSide.BUY}


def test_a_stop_the_exchange_ended_without_a_fill_does_not_stop_a_healthy_grid(
    futures: FakeExchange,
) -> None:
    """Check T2, the answer where the exchange cancels a close-all stop when the position goes
    through zero: the bot reads the order's own status, finds no trigger, and runs on."""
    futures.urls.futures_book.algo.expire_when_flat = True
    heard: list[BotProtectiveStopEvent] = []
    with booted_futures_bots(futures) as app:
        bot_id = started(app, LONG.config)
        app.engine.context.container.resolve(IEventBus).on(
            BotProtectiveStopEvent, heard.append
        )

        for price in LONG.prices_to_flat:
            app.move_price(price)
        app.ticker.fire()
        app.deliver()

        assert app.position() == 0
        assert app.bot(bot_id).state is S.RUNNING
        assert heard == []


def test_a_stop_left_cancelling_by_a_failed_cancel_is_finished_and_the_position_re_protected(
    futures: FakeExchange,
) -> None:
    """A record saved `CANCELLING` whose order still stands (the cancel did not go through)
    ends on the next look, and the position that stands gets a new stop, not a resend of it."""
    with booted_futures_bots(futures) as first:
        bot_id = started(first)
        (before,) = stops(first)
    for saved in futures.tmp_path.rglob("*.json"):
        text = saved.read_text(encoding="utf-8")
        if str(before["clientAlgoId"]) in text:
            saved.write_text(
                text.replace('"standing"', '"cancelling"'), encoding="utf-8"
            )

    with booted_futures_bots(futures) as second:
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )
        second.ticker.fire()
        second.deliver()

        assert second.bot(bot_id).state is S.RUNNING
        (after,) = stops(second)
        assert after["clientAlgoId"] != before["clientAlgoId"]
        (saved_stop,) = second.runtime(bot_id).protective_stops
        assert saved_stop.client_order_id == after["clientAlgoId"]
