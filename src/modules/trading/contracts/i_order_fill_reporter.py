"""`BOT-173` — the door a fill enters the app through, whichever exchange record told of it.

@details A trade is reported by whichever record of it arrives first: the
placement response of the order that made it, the user-data stream, or a
history re-read. This port is what the first two call (a history re-read goes
through registration, `OwnerInventoryDeriver`). An implementation counts a
trade once, keyed by its trade id, so a second record of it changes nothing.

@par Extension cases (`architecture-rule.md` §7.2.1)
  · a REST poll of the trade history that reports fills while the stream is
    down is one more caller of `order_filled`;
  · a Futures placement response (it carries no fills today) is the Futures
    client calling it.
Neither needs a change here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order


class IOrderFillReporter(ABC):
    """Receives one fill of `order` from any exchange record."""

    @abstractmethod
    def order_filled(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None = None,
        trade_id: int | None = None,
    ) -> None:
        """@brief `fill` is `(price, quantity)` of this one fill, `fee` its
        `(amount, asset)` where the record carries one, `trade_id` the
        exchange's id of it. A trade already reported is not counted again."""
