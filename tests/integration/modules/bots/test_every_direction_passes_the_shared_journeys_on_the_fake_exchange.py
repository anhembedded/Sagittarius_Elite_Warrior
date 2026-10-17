"""`EPIC-039I` - every direction of the Futures grid passes the same journeys on the fake exchange.

@details One parametrised suite over `futures_direction_scenarios.SCENARIOS` (LONG and SHORT today):
start, a fill and its counter, a cycle's profit, a report heard twice, a stop, a halt, a restart,
a stream gap, a position the owner added by hand, a start over a foreign position, and a mark
price through an exit. The composed app and the production executor run against the Futures
testnet fake; nothing here is a double of a port and nothing reaches a real exchange.

The position function holds in the executor, not only in the planner: see
`test_the_position_model_agrees_with_the_futures_executor.py`, parametrised the same way.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_bots_world import ORDER_QUANTITY, BootedFuturesBots, booted_futures_bots
from .futures_direction_scenarios import SCENARIOS, DirectionScenario
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import (
    _created,
    _publish_tick,
    _start,
    _started,
)

S = BotLifecycleState
D = Decimal

every_direction = pytest.mark.parametrize(
    "scenario", SCENARIOS, ids=lambda s: s.direction.name
)


def _resting(app: BootedFuturesBots) -> list[tuple[str, Decimal, bool]]:
    return sorted(app.resting().values())


def _by_hand(
    app: BootedFuturesBots, scenario: DirectionScenario, quantity: str
) -> None:
    """The user trades on the exchange's own website: a market order nobody here sent."""
    app.client().place_order(
        Order(
            client_order_id=ClientOrderId("web-by-hand"),
            symbol=SYMBOL,
            side=scenario.by_hand_side,
            order_type=OrderType.MARKET,
            quantity=D(quantity),
        )
    )


@every_direction
def test_a_start_opens_the_directions_position_and_lays_its_reduce_only_exits(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, (
            runtime.reason,
            runtime.reason_detail,
        )
        assert app.position() == scenario.opening
        assert _resting(app) == list(scenario.resting_at_start)
        assert {o.client_order_id for o in runtime.open_orders} == set(app.resting())
        assert runtime.inventory == scenario.opening
        assert all(o.quantity == ORDER_QUANTITY for o in runtime.open_orders)


@every_direction
def test_a_filled_entry_owes_a_reduce_only_completion_and_a_cycle_books_profit(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)
        fills: list[OrderFilledEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OrderFilledEvent, fills.append
        )

        app.move_price(scenario.entry_price)

        assert app.position() == scenario.position_after_entry
        assert _resting(app) == list(scenario.resting_after_entry)
        assert {o.client_order_id for o in app.runtime(bot_id).open_orders} == set(
            app.resting()
        )

        app.move_price(scenario.completion_price)

        runtime = app.runtime(bot_id)
        assert app.position() == scenario.opening
        assert runtime.inventory == scenario.opening
        assert runtime.completed_cycles == 1
        assert runtime.realised_profit > 0
        # The exchange's own realised profit (`rp`, before commission) is the executor's figure
        # plus what it paid in commission: the two books agree, whichever side closed.
        exchange_profit = sum((f.realized_profit or D(0) for f in fills), D(0))
        assert exchange_profit > 0
        assert runtime.realised_total > 0
        assert exchange_profit - runtime.realised_total <= runtime.commissions


@every_direction
def test_a_fill_the_exchange_reports_twice_is_counted_once_by_the_bot(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)
        futures.urls.futures_book.faults.duplicate_reports = True

        app.move_price(scenario.entry_price)

        assert app.position() == scenario.position_after_entry
        assert app.runtime(bot_id).inventory == app.position()


@every_direction
def test_stop_closes_the_position_reduce_only_and_confirms_flat_with_no_orders(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)
        app.move_price(scenario.entry_price)
        assert app.position() == scenario.position_after_entry

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
        assert app.runtime(bot_id).inventory == 0


@every_direction
def test_a_stop_that_would_keep_the_position_is_refused_in_words(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)

        refused = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.KEEP)
        )

        assert isinstance(refused, BotCommandResult)
        assert refused.refusal is BotRefusal.EXPOSURE_MUST_CLOSE
        assert app.bot(bot_id).state is S.RUNNING
        assert app.position() == scenario.opening


@every_direction
def test_a_halt_by_a_silent_feed_ends_flat_with_no_orders_and_says_why(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)
        app.move_price(scenario.entry_price)
        assert app.position() == scenario.position_after_entry
        _publish_tick(app, float(scenario.entry_price))

        app.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
        app.ticker.fire()
        app.deliver()

        runtime = app.runtime(bot_id)
        assert runtime.reason is GridReason.PRICE_FEED_STALE
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0, "a halt never leaves a leveraged position bare"
        assert app.resting() == {}
        assert runtime.inventory == 0


@every_direction
def test_a_restart_in_the_middle_of_the_ladder_recovers_its_orders_and_its_position(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = _started(first, scenario.config)

    # While the app is closed an order of the opening's reduce-only side fills and nobody hears.
    futures.urls.futures_book.move_price(SYMBOL, scenario.price_missed_while_closed)
    futures.urls.futures_book.drain_user_data_events()

    with booted_futures_bots(futures) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        assert len(second.resting()) == 3, "nothing was placed at boot"

        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING, (
            runtime.reason,
            runtime.reason_detail,
        )
        assert second.position() == scenario.position_after_missed
        assert runtime.inventory == second.position()
        assert {o.client_order_id for o in runtime.open_orders} == set(second.resting())
        assert _resting(second) == list(scenario.resting_after_missed)


@every_direction
def test_a_stream_gap_reconciles_the_position_and_places_the_missed_counter(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures, stream_up=False) as app:
        bot_id = _started(app, scenario.config)
        app.deliver()
        before = app.runtime(bot_id)

        futures.urls.futures_book.move_price(SYMBOL, scenario.entry_price)
        futures.urls.futures_book.drain_user_data_events()
        assert app.runtime(bot_id).inventory == before.inventory, "missed"

        app.engine.event_bus.emit(
            UserStreamHealthEvent(
                UserStreamState.CONNECTED, datetime.now(UTC), 1, venue=FUTURES
            )
        )

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING
        assert runtime.inventory == app.position() == scenario.position_after_entry
        assert {o.client_order_id for o in runtime.open_orders} == set(app.resting())
        assert _resting(app) == list(scenario.resting_after_entry), "the counter"


@every_direction
def test_a_position_added_by_hand_halts_the_recovery_and_only_the_bots_own_is_closed(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as first:
        bot_id = _started(first, scenario.config)
    futures.urls.futures_book.move_price(SYMBOL, D(64000))
    with booted_futures_bots(futures) as second:
        _by_hand(second, scenario, "0.003")
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )

        runtime = second.runtime(bot_id)
        assert runtime.reason is scenario.by_hand_reason
        assert second.bot(bot_id).state is S.STOPPED
        assert abs(second.position()) == D("0.003")
        assert second.resting() == {}
        assert "was left open" in runtime.reason_detail
        assert "not this bot's" in runtime.reason_detail


@every_direction
def test_an_order_worth_more_than_tradings_cap_is_caught_in_the_plan_not_at_start(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    """900 of margin at 3x gives each of four orders 675 against trading's 500: the Plan's
    verdict refuses, so Start is refused in the Plan's words and nothing is sent. (The start
    sequence's own guard, for a plan that reaches it anyway, is a unit test:
    `test_grid_start_cap.py`.)"""
    config = {**scenario.config, "capital_quote": "900"}
    with booted_futures_bots(futures) as app:
        bot_id = _created(app, config)

        started = _start(app, bot_id)

        assert not started.accepted
        assert "cap" in started.message
        assert app.position() == 0
        assert app.resting() == {}
        assert app.bot(bot_id).state is S.DRAFT


@every_direction
def test_a_flat_bot_beside_a_position_by_hand_halts_and_stops_leaving_it_open(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    """A bot whose exits all filled (or a NEUTRAL one between cycles) is flat; trading then
    refuses a position it finds as one the bot did not open. The recovery halts in words (a
    foreign fill, not a switch-off), the stop cancels the bot's orders, closes none of the
    foreign position and ends STOPPED."""
    with booted_futures_bots(futures) as first:
        bot_id = _started(first, scenario.config)
        for price in scenario.prices_to_flat:
            first.move_price(price)
        assert first.position() == 0
    with booted_futures_bots(futures) as second:
        _by_hand(second, scenario, "0.003")
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )

        runtime = second.runtime(bot_id)
        assert runtime.reason is GridReason.FOREIGN_FILL
        assert second.bot(bot_id).state is S.STOPPED
        assert abs(second.position()) == D("0.003"), "the foreign position is left open"
        assert second.resting() == {}
        assert "did not open" in runtime.reason_detail


@every_direction
def test_a_start_is_refused_for_a_position_the_bot_did_not_open(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        _by_hand(app, scenario, "0.002")
        bot_id = _created(app, scenario.config)

        started = _start(app, bot_id)

        assert not started.accepted
        assert f"already holds a {scenario.holds_word} position" in started.message
        assert app.resting() == {}
        assert abs(app.position()) == D("0.002"), "the bot sent nothing"


@every_direction
def test_a_mark_price_through_the_upper_exit_closes_the_position_and_stops_the_bot(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)

        # The last price the kline stream shows going through the exit does not stop the bot.
        _publish_tick(app, 71000.0)
        assert app.bot(bot_id).state is S.RUNNING

        # The exchange's mark through it does, while the order there has not filled yet.
        futures.urls.futures_book.faults.hold_fills = True
        futures.urls.futures_book.algo.hold_triggers = True  # the bot's own exit, alone
        app.move_price(scenario.mark_through_upper_exit)
        assert app.position() == scenario.opening
        app.ticker.fire()
        app.deliver()

        assert app.runtime(bot_id).reason is scenario.upper_exit_reason
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
