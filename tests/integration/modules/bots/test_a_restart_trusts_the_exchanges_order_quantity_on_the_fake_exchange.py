"""`BUG-205` — a restart brings a saved order's quantity level with the exchange's.

@details The Orders panel shows the saved ladder's quantity. The reconcile
compared order ids only, so an order the exchange holds at another quantity than
the bot saved stayed shown, and booked, at the saved one. The exchange's record is
the truth (`domain-truth-rule.md`): the reconcile adopts its quantity and says so.
"""

from __future__ import annotations

import logging
from decimal import Decimal

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

from .grid_fake_exchange import SPOT, SYMBOL, FakeExchange, booted, resting
from .test_grid_bot_against_fake_server import _started

S = BotLifecycleState


class _Collect(logging.Handler):
    def __init__(self, lines: list[str]) -> None:
        super().__init__(logging.INFO)
        self._lines = lines

    def emit(self, record: logging.LogRecord) -> None:
        self._lines.append(record.getMessage())


def test_a_restart_adopts_the_quantity_the_exchange_holds_for_a_saved_order(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as first:
        bot_id = _started(first)
        top = max(first.runtime(bot_id).open_orders, key=lambda order: order.price)
        saved = top.quantity
    shrunk = saved - Decimal("0.00001")
    exchange.urls.spot_account.resize_resting(top.client_order_id, shrunk)

    with booted(exchange) as second:
        logged: list[str] = []
        handler = _Collect(logged)
        logger = logging.getLogger("App.Bots.GridExecutor")
        logger.addHandler(handler)
        try:
            second.engine.event_bus.emit(
                TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
            )
        finally:
            logger.removeHandler(handler)

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING
        shown = {o.client_order_id: o.quantity for o in runtime.open_orders}
        assert shown[top.client_order_id] == shrunk
        assert set(resting(second.urls)) == set(shown)
        assert any(
            "[order-quantity]" in line and top.client_order_id in line
            for line in logged
        )


def test_a_ladder_saves_the_quantity_the_exchange_accepted_for_each_order(
    exchange: FakeExchange,
) -> None:
    """The venue accepts every LIMIT order for a step less than it was sent for: the
    saved ladder, which the Orders panel shows, holds what the exchange holds."""
    exchange.urls.spot_account.accept_limits_for_less(Decimal("0.00001"))

    with booted(exchange) as app:
        bot_id = _started(app)

        held = {
            row["clientOrderId"]: Decimal(row["origQty"])
            for row in app.urls.spot_account.open_orders(SYMBOL)
        }
        shown = {o.client_order_id: o.quantity for o in app.runtime(bot_id).open_orders}
        assert shown == held
        assert shown


def test_a_restart_settles_an_order_held_for_less_that_filled_whole_while_closed(
    exchange: FakeExchange,
) -> None:
    """The exchange held the nearest SELL for less than the bot saved, and it filled
    whole while the app was closed. It is gone from the open orders, so its quantity
    comes from history: the order is settled as the whole fill it was, not read as
    "ended without filling" with its remainder laid again. The base the exchange did
    not take stays in the inventory, so the counter BUY may then be refused by the
    budget (a halt that names it): what this test pins is the settled order."""
    with booted(exchange) as first:
        bot_id = _started(first)
        sells = [o for o in first.runtime(bot_id).open_orders if o.side.value == "SELL"]
        nearest = min(sells, key=lambda order: order.price)
        held_before = first.runtime(bot_id).inventory
    sold = nearest.quantity - Decimal("0.0003")
    exchange.urls.spot_account.resize_resting(nearest.client_order_id, sold)
    exchange.urls.spot_account.set_last_price(SYMBOL, nearest.price)
    exchange.urls.spot_account.drain_user_data_events()  # nobody was listening

    with booted(exchange) as second:
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
        )

        runtime = second.runtime(bot_id)
        assert runtime.inventory == held_before - sold
        assert [o for o in runtime.open_orders if o.price == nearest.price] == []
        assert nearest.price not in {p for _s, p in resting(second.urls).values()}


def test_a_restart_halts_when_the_exchange_holds_an_order_for_more_than_saved(
    exchange: FakeExchange,
) -> None:
    """More than the bot accounts for is never adopted: the order could trade base
    the bot's books do not cover, so the bot halts and names it."""
    with booted(exchange) as first:
        bot_id = _started(first)
        top = max(first.runtime(bot_id).open_orders, key=lambda order: order.price)
    exchange.urls.spot_account.resize_resting(
        top.client_order_id, top.quantity + Decimal("0.00001")
    )

    with booted(exchange) as second:
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
        )

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.HALTED
        assert runtime.reason is GridReason.ORDER_QUANTITY_MISMATCH
        assert top.client_order_id in runtime.reason_detail
