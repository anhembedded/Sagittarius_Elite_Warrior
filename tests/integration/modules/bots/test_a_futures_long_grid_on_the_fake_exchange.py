"""`EPIC-039H` - a Futures Long Grid runs on the fake exchange: start, counters, stop.

@details The composed app over the Futures testnet fake with its bots running (`futures_bots_world`):
the use cases are dispatched, the production executor and its Futures collaborators place the
orders, the fake matches them and reports the fills through the stream's own handler. Nothing here
is a double of a port, and nothing reaches a real exchange.

At each step the exchange's open orders and position are asserted against the bot's own ladder and
inventory, price for price and id for id.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_bots_world import (
    GRID,
    OPENING_QUANTITY,
    ORDER_QUANTITY,
    BootedFuturesBots,
    booted_futures_bots,
)
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange

S = BotLifecycleState
D = Decimal


def _created(app: BootedFuturesBots, config: dict[str, str] | None = None) -> str:
    created = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand("futures grid", "grid", FUTURES, SYMBOL, config or GRID),
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None, created.message
    return created.bot_id


def _started(app: BootedFuturesBots) -> str:
    bot_id = _created(app)
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return bot_id


def test_a_futures_long_opens_its_position_and_lays_reduce_only_sells(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, (
            runtime.reason,
            runtime.reason_detail,
        )
        assert app.position() == OPENING_QUANTITY
        resting = app.resting()
        assert sorted(
            (side, price, reduce) for side, price, reduce in resting.values()
        ) == [
            ("BUY", D(62000), False),
            ("BUY", D(63000), False),
            ("SELL", D(65000), True),
            ("SELL", D(66000), True),
        ]
        runtime = app.runtime(bot_id)
        assert {o.client_order_id for o in runtime.open_orders} == set(resting)
        assert runtime.inventory == OPENING_QUANTITY
        assert all(o.quantity == ORDER_QUANTITY for o in runtime.open_orders)


def test_a_filled_buy_owes_a_reduce_only_sell_one_level_up_and_a_cycle_books_profit(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)
        fills: list[OrderFilledEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OrderFilledEvent, fills.append
        )

        app.move_price(
            62900
        )  # the 63,000 buy fills; 64,000, empty until now, is its exit

        assert app.position() == OPENING_QUANTITY + ORDER_QUANTITY
        assert sorted(app.resting().values()) == [
            ("BUY", D(62000), False),
            ("SELL", D(64000), True),
            ("SELL", D(65000), True),
            ("SELL", D(66000), True),
        ]
        assert {o.client_order_id for o in app.runtime(bot_id).open_orders} == set(
            app.resting()
        )

        app.move_price(64100)  # that exit fills: one cycle, the buy back

        runtime = app.runtime(bot_id)
        assert app.position() == OPENING_QUANTITY
        assert runtime.inventory == OPENING_QUANTITY
        assert runtime.completed_cycles == 1
        assert sorted(app.resting().values()) == [
            ("BUY", D(62000), False),
            ("BUY", D(63000), False),
            ("SELL", D(65000), True),
            ("SELL", D(66000), True),
        ]
        # The exchange's own realised profit of the exit (`rp`, before commission) is the
        # executor's figure plus what it paid in commission: the two books agree.
        exchange_profit = sum(
            (f.realized_profit or D(0) for f in fills if f.order.side.value == "SELL"),
            D(0),
        )
        assert exchange_profit > 0
        assert runtime.realised_total > 0
        assert exchange_profit - runtime.realised_total <= runtime.commissions


def test_a_fill_the_exchange_reports_twice_is_counted_once_by_the_bot(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)
        futures.urls.futures_book.faults.duplicate_reports = True

        app.move_price(62900)

        assert app.position() == OPENING_QUANTITY + ORDER_QUANTITY
        assert app.runtime(bot_id).inventory == app.position()


def test_stop_closes_the_position_reduce_only_and_confirms_flat_with_no_orders(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)
        app.move_price(62900)
        assert app.position() > 0

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        assert app.bot(bot_id).state is S.STOPPED
        assert app.position() == 0
        assert app.resting() == {}
        assert app.runtime(bot_id).inventory == 0


def test_a_stop_that_would_keep_a_futures_position_is_refused_in_words(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)

        refused = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.KEEP)
        )

        assert isinstance(refused, BotCommandResult)
        assert refused.refusal is BotRefusal.EXPOSURE_MUST_CLOSE
        assert "close the position" in refused.message
        assert app.bot(bot_id).state is S.RUNNING
        assert len(app.resting()) == 4
        assert app.position() == OPENING_QUANTITY


def test_funding_is_booked_whole_to_the_bot_that_holds_the_position(
    futures: FakeExchange,
) -> None:
    """`EPIC-039G` handed it over: funding is per position, not per owner, and the symbol is
    leased to the bot, so the whole charge is the bot's and is never pro-rated."""
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)
        futures.urls.futures_book.set_funding_rate(SYMBOL, D("0.0001"))

        futures.urls.futures_book.advance_clock(8 * 3600 * 1000)
        app.deliver()

        # The long pays: 0.012 BTC at the mark of 64,000 times a rate of 0.01 %.
        assert app.runtime(bot_id).funding_total == -D("0.012") * D(64000) * D("0.0001")
