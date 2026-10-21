"""`EPIC-039L` - a Futures Grid's exchange-side protective stop, on the fake exchange.

@details The composed app over the Futures testnet fake with its bots running
(`futures_bots_world`): the production executor, the production protection, the fake's
`closePosition` semantics and its `ALGO_UPDATE`s. The journeys are the acceptance criteria of
`EPIC-039L` C2: the stop stands before the ladder is ready and its id is in the saved runtime;
it is cancelled only after the position is flat; a restart adopts it, re-places a missing one
and cancels an orphan; and a stop that ran, in the session or while the app was closed, ends
the bot flat and says why. Nothing here is a double of a port, and nothing reaches a real
exchange.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    BotOrderGateway,
    OrderOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.protective_stop_request import (
    ProtectiveStopOrder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    CHECK_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_protective_stop_event import (
    BotProtectiveStopEvent,
    ProtectiveStopChange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    ProtectiveStopState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.working_type import (
    WorkingType,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_bots_world import BootedFuturesBots, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .futures_stop_helpers import STOP_LOSS, started, stops
from .grid_fake_exchange import FakeExchange

S = BotLifecycleState
D = Decimal


def _resumed(app: BootedFuturesBots) -> None:
    app.engine.event_bus.emit(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
    )


def test_the_stop_stands_before_the_ladder_is_ready_and_its_id_is_in_the_saved_runtime(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)

        assert app.bot(bot_id).state is S.RUNNING
        (stop,) = stops(app)
        assert stop["closePosition"] is True
        assert (stop["orderType"], stop["side"]) == ("STOP_MARKET", "SELL")
        assert D(str(stop["triggerPrice"])) == STOP_LOSS
        assert stop["workingType"] == "MARK_PRICE"
        assert D(str(stop["quantity"])) == 0
        (saved,) = app.runtime(bot_id).protective_stops
        assert saved.client_order_id == stop["clientAlgoId"]
        assert (saved.state, saved.side, saved.trigger_price) == (
            ProtectiveStopState.STANDING,
            OrderSide.SELL,
            STOP_LOSS,
        )


def test_the_stops_id_is_in_the_saved_runtime_before_the_order_is_sent(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision D5: the record a crash must find is saved first, so a stop placed and not
    answered is never an order nobody can find."""
    seen: list[tuple[str, ProtectiveStopState]] = []
    original = BotOrderGateway.place_protective_stop

    def spy(self: BotOrderGateway, stop: ProtectiveStopOrder) -> OrderOutcome:
        saved = [
            (s.client_order_id, s.state)
            for bot_id in [self._identity.tag]
            for s in decode_runtime(
                holder["app"].store.load(BotId(bot_id)).runtime
            ).protective_stops
        ]
        seen.extend(saved)
        return original(self, stop)

    holder: dict[str, BootedFuturesBots] = {}
    monkeypatch.setattr(BotOrderGateway, "place_protective_stop", spy)
    with booted_futures_bots(futures) as app:
        holder["app"] = app

        started(app)

        (stop,) = stops(app)
        assert seen == [(stop["clientAlgoId"], ProtectiveStopState.INTENDED)]


def test_stop_cancels_the_protective_stop_only_after_the_position_is_flat(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        assert len(stops(app)) == 1

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert stops(app) == []
        assert app.runtime(bot_id).protective_stops == ()


def test_a_close_that_fails_leaves_the_stop_standing(futures: FakeExchange) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        # Every reduce-only market order the close sends is refused by the exchange.
        for _ in range(40):
            futures.urls.futures_book.faults.reject_next_order(
                -2022, "ReduceOnly Order is rejected."
            )

        app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert app.position() > 0, "the close did not go through"
        assert len(stops(app)) == 1, "so the stop still stands over the position"
        assert app.bot(bot_id).state is not S.STOPPED


def test_a_restart_adopts_the_standing_stop_and_places_no_second_one(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = started(first)
        (before,) = stops(first)

    with booted_futures_bots(futures) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        _resumed(second)

        assert second.bot(bot_id).state is S.RUNNING
        (after,) = stops(second)
        assert after["clientAlgoId"] == before["clientAlgoId"]


def test_a_position_without_a_stop_after_a_crash_is_re_protected(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = started(first)
    # The app died between the fill and the stop: nothing stands (the record is saved, the
    # order is gone).
    futures.urls.futures_book.algo.cancel_all(SYMBOL)

    with booted_futures_bots(futures) as second:
        _resumed(second)

        assert second.bot(bot_id).state is S.RUNNING
        (stop,) = stops(second)
        assert D(str(stop["triggerPrice"])) == STOP_LOSS
        (saved,) = second.runtime(bot_id).protective_stops
        assert saved.state is ProtectiveStopState.STANDING
        assert saved.client_order_id == stop["clientAlgoId"]


def test_the_stop_triggers_while_the_app_is_down_and_the_bot_returns_flat(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = started(first)

    # While the app is closed the mark falls through the stop: the exchange closes the position.
    futures.urls.futures_book.move_price(SYMBOL, STOP_LOSS - 100)
    futures.urls.futures_book.drain_user_data_events()

    with booted_futures_bots(futures) as second:
        assert second.position() == 0
        _resumed(second)

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.STOPPED
        assert runtime.reason is GridReason.PROTECTIVE_STOP_TRIGGERED
        assert second.position() == 0
        assert stops(second) == []
        assert second.resting() == {}


def test_the_stop_triggers_in_the_session_and_the_bot_stops_flat_and_says_why(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        # The ladder's resting buys would fill on the way down, and their reports would reach
        # the bot ahead of the stop's: this journey is the stop's own.
        futures.urls.futures_book.faults.hold_fills = True

        app.move_price(STOP_LOSS - 100)

        assert app.position() == 0
        assert app.bot(bot_id).state is S.STOPPED
        assert app.runtime(bot_id).reason is GridReason.PROTECTIVE_STOP_TRIGGERED
        assert stops(app) == []
        assert app.resting() == {}


def test_a_stop_that_runs_just_after_a_beat_read_the_positions_still_ends_the_bot_as_triggered(
    futures: FakeExchange,
) -> None:
    """`BOT-184` review: the idle beat's reading of the account's positions is shared and up to
    half a beat old. A stop that runs right after it leaves the position flat while that reading
    still says it stands; judged on the reading the stop looked missing, was sent again, and the
    bot went on trading after its stop loss. The look at the stops confirms on the account."""
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        futures.urls.futures_book.faults.hold_fills = True
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()  # the risk watch reads the positions: the shared reading is taken

        app.move_price(
            STOP_LOSS - 100
        )  # no beat since: the reading is younger than half a beat

        assert app.position() == 0
        assert app.bot(bot_id).state is S.STOPPED
        assert app.runtime(bot_id).reason is GridReason.PROTECTIVE_STOP_TRIGGERED


def test_an_absent_stop_is_judged_on_the_account_even_when_nothing_dropped_the_reading(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second line of defence of the test above: with every invalidation off, a stop that
    left the open list is still told as run by the account's own read."""
    monkeypatch.setattr(BotAccountReads, "account_changed", lambda self: None)
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        futures.urls.futures_book.faults.hold_fills = True
        app.monotonic.advance(CHECK_EVERY_SECONDS)
        app.ticker.fire()

        app.move_price(STOP_LOSS - 100)

        assert app.bot(bot_id).state is S.STOPPED
        assert app.runtime(bot_id).reason is GridReason.PROTECTIVE_STOP_TRIGGERED


def test_a_stop_over_a_symbol_the_owner_flattened_is_cancelled_not_left_to_open_one(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        # The owner closes the whole position by hand on the exchange's page.
        app.client().place_order(_flatten(app))
        assert app.position() == 0
        assert len(stops(app)) == 1

        app.ticker.fire()  # the price watch's beat

        assert stops(app) == [], (
            "a stop over nothing is cancelled: it could open a position"
        )
        assert app.runtime(bot_id).protective_stops == ()


def _flatten(app: BootedFuturesBots) -> Order:

    return Order(
        client_order_id=ClientOrderId("SEW-byhand-flat"),
        symbol=SYMBOL,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=app.position(),
        reduce_only=True,
    )


def test_a_stop_of_the_bots_that_the_plan_does_not_ask_for_is_taken_down_after_its_own_stands(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        (own,) = stops(app)
        # An old stop of this bot's, at another trigger, that nothing in its record names.
        app.client().place_order(_stray_stop(bot_id))
        assert len(stops(app)) == 2

        app.ticker.fire()  # the price watch's beat

        (left,) = stops(app)
        assert left["clientAlgoId"] == own["clientAlgoId"]


def _stray_stop(bot_id: str) -> Order:

    return Order(
        client_order_id=ClientOrderId(f"SEW-{bot_id}-0123456789"),
        symbol=SYMBOL,
        side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET,
        quantity=D(0),
        stop_price=D(55000),
        close_position=True,
        working_type=WorkingType.MARK_PRICE,
    )


def test_a_stop_that_ran_is_announced_for_the_alert_module(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        started(app)
        heard: list[BotProtectiveStopEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            BotProtectiveStopEvent, heard.append
        )
        futures.urls.futures_book.faults.hold_fills = True

        app.move_price(STOP_LOSS - 100)

        assert [event.change for event in heard] == [ProtectiveStopChange.TRIGGERED]
        assert heard[0].symbol == SYMBOL


def test_a_stop_that_went_missing_is_announced_and_placed_again(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = started(app)
        heard: list[BotProtectiveStopEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            BotProtectiveStopEvent, heard.append
        )
        futures.urls.futures_book.algo.cancel_all(
            SYMBOL
        )  # cancelled by hand on the exchange

        app.ticker.fire()

        assert [event.change for event in heard] == [ProtectiveStopChange.MISSING]
        (stop,) = stops(app)
        assert stop["clientAlgoId"] in {
            s.client_order_id for s in app.runtime(bot_id).protective_stops
        }
