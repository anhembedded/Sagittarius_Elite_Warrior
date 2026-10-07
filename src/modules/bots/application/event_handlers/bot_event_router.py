"""`EPIC-029E` — the bots module's one listener to trading's and market_data's events (ADR D9, D12).

Subscribed once, in `bots/module.py`'s `boot()`. Each handler runs on whatever
thread published the event (the websocket thread for fills, ends and ticks):
it **filters** on the venue and the bot's tag, **copies** the few facts the bot
needs into a frozen value, **posts** it to that bot's executor and returns.
Nothing here touches a bot's record or sends an order.

  · **A fill or an end** carries a client order id; its tag is the bot's id
    (D5). A restored bot with no executor yet gets one here, so a fill that
    arrives right after trading is enabled is never dropped.
  · **A rejection** (`OrderRejectedEvent`) ends the order with the exchange's
    reason, which halts the bot.
  · **A tick** goes to every executor trading that symbol on that market.
  · **The trading switch.** Off: every executor on the venue halts. On: every
    stored bot on the venue that is not DRAFT or STOPPED takes its lease back
    and, when RECOVERING, reconciles; when STOPPING, finishes its stop (D12).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_rejected_event import (
    OrderRejectedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.Events")


class BotEventRouter:
    """Routes each event to the executor of the bot it concerns."""

    def __init__(self, store: IBotStore, executors: BotExecutors) -> None:
        self._store = store
        self._executors = executors

    def on_fill(self, event: OrderFilledEvent) -> None:
        executor = self._executor_for(event.order.client_order_id, event.venue)
        if executor is not None:
            executor.on_fill(
                BotOrderFill(
                    event.order.client_order_id,
                    event.order.side,
                    event.fill_price,
                    event.fill_quantity,
                    event.fee_amount,
                    event.fee_asset,
                )
            )

    def on_end(self, event: OrderEndedEvent) -> None:
        executor = self._executor_for(event.order.client_order_id, event.venue)
        if executor is None:
            return
        rejected = event.order.status is OrderStatus.REJECTED
        executor.on_end(
            BotOrderEnd(
                event.order.client_order_id,
                "the exchange rejected the order" if rejected else None,
            )
        )

    def on_rejected(self, event: OrderRejectedEvent) -> None:
        executor = self._executor_for(event.order.client_order_id, event.venue)
        if executor is not None:
            executor.on_end(BotOrderEnd(event.order.client_order_id, event.reason))

    def on_tick(self, event: MarketTickEvent) -> None:
        candle = event.market_data
        for executor in self._executors.all():
            if (
                executor.symbol == candle.symbol
                and executor.venue.market_type is event.market_type
                and executor.venue.market_data_venue is event.market_data_venue
            ):
                executor.on_tick(Decimal(str(candle.close_price)))

    def on_switch(self, event: TradingSwitchChangedEvent) -> None:
        if not event.enabled:
            for executor in self._executors.on_venue(event.venue):
                executor.on_switch(False, event.cause)
            return
        for stored in self._store.load_all().bots:
            bot = stored.bot
            if (
                bot.definition.venue is event.venue
                and bot.state not in RUN_STARTING_STATES
            ):
                self._executors.for_bot(bot).on_switch(True, event.cause)

    def _executor_for(
        self, client_order_id: str, venue: TradingVenue
    ) -> GridExecutor | None:
        tag = tag_of(client_order_id)
        if tag is None:
            return None
        executor = self._executors.get(tag)
        if executor is None and self._store.exists(BotId(tag)):
            executor = self._executors.for_bot(self._store.load(BotId(tag)).bot)
        if executor is None or executor.venue is not venue:
            return None
        return executor
