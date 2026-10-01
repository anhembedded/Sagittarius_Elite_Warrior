"""`EPIC-028R` — the Futures user-data stream's order messages:
`ORDER_TRADE_UPDATE` (a regular order's state and fills) and `ALGO_UPDATE`
(a conditional order's state). Each fill is an `order_filled`; an order
cancelled, rejected or expired, regular or conditional, is an `order_ended`
(`EPIC-028I`).

@details Split out of `futures_user_data_stream.py`, which keeps the
connection, its reconnects and `ACCOUNT_UPDATE`. A conditional order that
triggers places a regular order with an exchange id of its own; the
`ALGO_UPDATE` carrying that id (`ai`) is remembered in `AlgoOrderLinks`, so
the regular order's fill is reported under the app's client order id. A fill
reported before its `ALGO_UPDATE` keeps the exchange's id: Binance documents
the algo update first, and no live stream verified the order (egress to
`*.binance.*` is blocked here).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.algo_order_links import (
    AlgoOrderLinks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.algo_update_parser import (
    order_trade_update_order_id,
    parse_algo_update,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_data_event_parser import (
    fill_details,
    is_fill_execution,
    parse_order_trade_update,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    ended_without_filling,
)

logger = logging.getLogger("App.UserDataStream")


class FuturesOrderUpdates:
    """@brief Turns one venue's order messages into `order_filled` and
    `order_ended` events."""

    def __init__(self, events: VenueEventEmitter) -> None:
        self._events = events
        self._algo_links = AlgoOrderLinks()

    def on_algo_update(self, payload: dict[str, Any]) -> None:
        """`EPIC-028R` — a conditional order's state. Once it has triggered,
        the regular order it placed is linked to the app's client id."""
        try:
            update = parse_algo_update(payload)
        except (KeyError, ValueError) as exc:
            logger.error("Could not parse ALGO_UPDATE: %s | %s", exc, payload)
            return
        order = update.order
        logger.debug(
            "ALGO_UPDATE  %s  %s  placed order %s",
            order.client_order_id,
            order.status.name,
            update.placed_order_id,
        )
        if update.placed_order_id is not None:
            self._algo_links.remember(update.placed_order_id, order.client_order_id)
        if ended_without_filling(order.status):
            self._events.order_ended(order)

    def on_order_trade_update(self, payload: dict[str, Any]) -> None:
        try:
            order = parse_order_trade_update(payload)
            order_id = order_trade_update_order_id(payload)
        except (KeyError, ValueError) as exc:
            logger.error("Could not parse ORDER_TRADE_UPDATE: %s | %s", exc, payload)
            return
        linked = (
            self._algo_links.client_order_id_for(order_id)
            if order_id is not None
            else None
        )
        if linked is not None:
            # A triggered conditional order's regular order: report it as
            # the order the app placed (`EPIC-028R`).
            order = replace(order, client_order_id=linked)

        # `BUG-095` — `DEBUG`, not `INFO`: this fires per order-status
        # transition, the exact "838 trades -> 5,028 INFO lines froze the
        # UI" hot-path class `BUG-042` already named (`SignalLogHandler`
        # still mirrors every `"App"` `INFO+` line to the UI's log model
        # via a queued Qt signal — `MarketTickEventHandler`'s own
        # docstring documents the same fix for the same reason).
        logger.debug(
            "ORDER_TRADE_UPDATE  %s  %s  qty %s",
            order.client_order_id,
            order.status.name,
            order.quantity,
        )

        if is_fill_execution(payload):
            fill_price, fill_quantity = fill_details(payload)
            self._events.order_filled(order, (fill_price, fill_quantity))
        elif ended_without_filling(order.status):
            self._events.order_ended(order)
