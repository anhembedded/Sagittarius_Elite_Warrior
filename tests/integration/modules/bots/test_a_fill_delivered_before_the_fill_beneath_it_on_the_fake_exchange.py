"""`BUG-225` - a live fill delivered before the fill of the rung it counters to is not a duplicate.

@details The price fell through two adjacent buy rungs and the user-data stream handed the app
the lower rung's fill first. Its counter order belongs on the higher rung, whose own buy had
filled on the exchange but was not yet applied, so the ledger still held it and the bot halted
with `DUPLICATE_LEVEL_ORDER` (the live-path twin of `BUG-214`, which fixed the reconcile). The
bot asks the exchange about the order in the way before halting: a filled one is applied first.
"""

from __future__ import annotations

import asyncio
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

from .futures_bots_world import GRID, ORDER_QUANTITY, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import GRID as SPOT_GRID
from .grid_fake_exchange import SPOT, FakeExchange, booted, resting
from .grid_fake_exchange import SYMBOL as SPOT_SYMBOL

S = BotLifecycleState
D = Decimal


def test_a_futures_long_counters_a_lower_fill_delivered_before_the_higher_one(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures, stream_up=False) as app:
        created = app.engine.dispatch(
            CreateBotCommand, CreateBotCommand("grid", "grid", FUTURES, SYMBOL, GRID)
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None
        bot_id = created.bot_id
        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult) and started.accepted
        opening = app.position()

        # The 63,000 buy fills, then the 62,000 buy; the stream delivers them reversed.
        book = futures.urls.futures_book
        book.move_price(SYMBOL, D(62900))
        book.move_price(SYMBOL, D(61900))
        for event in reversed(book.drain_user_data_events()):
            asyncio.run(app.stream._handle_message(event))

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, runtime.reason_detail
        assert app.position() == opening + 2 * ORDER_QUANTITY
        assert runtime.inventory == app.position()
        assert sorted(app.resting().values()) == [
            ("SELL", D(63000), True),
            ("SELL", D(64000), True),
            ("SELL", D(65000), True),
            ("SELL", D(66000), True),
        ]
        assert {o.client_order_id for o in runtime.open_orders} == set(app.resting())


def test_a_spot_grid_counters_a_lower_fill_delivered_before_the_higher_one(
    exchange: FakeExchange,
) -> None:
    with booted(exchange, stream_up=False) as app:
        created = app.engine.dispatch(
            CreateBotCommand,
            CreateBotCommand("grid", "grid", SPOT, SPOT_SYMBOL, SPOT_GRID),
        )
        assert isinstance(created, BotCommandResult) and created.bot_id is not None
        bot_id = created.bot_id
        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult) and started.accepted
        buys = sorted(
            (o.price for o in app.runtime(bot_id).open_orders if o.side.value == "BUY"),
            reverse=True,
        )

        book = exchange.urls.spot_account
        book.set_last_price(SPOT_SYMBOL, buys[0] - D(1))
        book.set_last_price(SPOT_SYMBOL, buys[1] - D(1))
        reports = [
            event
            for event in book.drain_user_data_events()
            if event["e"] == "executionReport"
        ]
        for event in reversed(reports):
            asyncio.run(app.stream._handle_message(event))

        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, runtime.reason_detail
        assert {o.client_order_id for o in runtime.open_orders} == set(
            resting(app.urls)
        )
