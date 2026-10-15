"""`BUG-214` - a restart applies the fills it missed in the order the exchange filled them.

@details Two rungs filled while the app was closed. The reconcile applied them in level
order, so the lower rung's counter was computed before the higher rung (which filled
first, and whose counter takes that level) was applied: the counter met the order still
resting there and the bot halted with `DUPLICATE_LEVEL_ORDER`, closing a healthy position.
The exchange's history says when each trade happened; the reconcile orders by it.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)

from .futures_bots_world import GRID, ORDER_QUANTITY, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import GRID as SPOT_GRID
from .grid_fake_exchange import SPOT, FakeExchange, booted, resting
from .grid_fake_exchange import SYMBOL as SPOT_SYMBOL

S = BotLifecycleState
D = Decimal


def test_a_futures_long_restart_applies_two_buys_filled_on_the_way_down_in_that_order(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as first:
        created = first.engine.dispatch(
            CreateBotCommand, CreateBotCommand("grid", "grid", FUTURES, SYMBOL, GRID)
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None
        bot_id = created.bot_id
        started = first.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult) and started.accepted
        opening = first.position()

    # The app is closed: the 63,000 buy fills, then the 62,000 buy - the opposite of
    # level order, so the 62,000 buy's counter takes the level the 63,000 one held.
    book = futures.urls.futures_book
    book.move_price(SYMBOL, D(62900))
    book.move_price(SYMBOL, D(61900))
    book.drain_user_data_events()

    with booted_futures_bots(futures) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING, runtime.reason_detail
        assert second.position() == opening + 2 * ORDER_QUANTITY, (
            "no healthy position closed"
        )
        assert runtime.inventory == second.position()
        assert sorted(second.resting().values()) == [
            ("SELL", D(63000), True),
            ("SELL", D(64000), True),
            ("SELL", D(65000), True),
            ("SELL", D(66000), True),
        ]
        assert {o.client_order_id for o in runtime.open_orders} == set(second.resting())


def test_a_spot_restart_applies_two_buys_filled_on_the_way_down_in_that_order(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as first:
        created = first.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("grid", "grid", SPOT, SPOT_SYMBOL, SPOT_GRID),
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None
        bot_id = created.bot_id
        started = first.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult) and started.accepted
        buys = sorted(
            (
                o.price
                for o in first.runtime(bot_id).open_orders
                if o.side.value == "BUY"
            ),
            reverse=True,
        )

    # The two highest buys fill, the higher first.
    book = exchange.urls.spot_account
    book.set_last_price(SPOT_SYMBOL, buys[0] - D(1))
    book.set_last_price(SPOT_SYMBOL, buys[1] - D(1))

    with booted(exchange) as second:
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
        )
        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING, runtime.reason_detail
        assert {o.client_order_id for o in runtime.open_orders} == set(
            resting(second.urls)
        )
