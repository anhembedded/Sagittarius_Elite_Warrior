"""`EPIC-028R` — which app order a triggered conditional order's regular
order belongs to.

@details A Futures conditional order lives in Binance's Algo Order API under
the app's client order id (`clientAlgoId`). When it triggers, Binance places
a regular order with an id of its own and reports the link once, in the
`ALGO_UPDATE` that carries `ai`. The user-data stream remembers that link
here so the regular order's `ORDER_TRADE_UPDATE` (its fill) is reported under
the app's client order id. Bounded: the oldest links are forgotten first, a
fill arriving long after its trigger being far older than the window.
"""

from __future__ import annotations

from collections import OrderedDict

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)

#: Far more conditional orders than one session triggers.
_DEFAULT_CAPACITY = 1_000


class AlgoOrderLinks:
    """@brief Exchange order id → the app's client order id, for orders a
    triggered conditional order placed."""

    def __init__(self, capacity: int = _DEFAULT_CAPACITY) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        self._capacity = capacity
        self._links: OrderedDict[int, ClientOrderId] = OrderedDict()

    def remember(self, placed_order_id: int, client_order_id: ClientOrderId) -> None:
        self._links[placed_order_id] = client_order_id
        self._links.move_to_end(placed_order_id)
        while len(self._links) > self._capacity:
            self._links.popitem(last=False)

    def client_order_id_for(self, order_id: int) -> ClientOrderId | None:
        """@return The app's client order id the regular order `order_id`
        belongs to, or `None` when no triggered conditional order placed it."""
        return self._links.get(order_id)
