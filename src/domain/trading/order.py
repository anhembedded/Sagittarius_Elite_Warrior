"""`EPIC-021E` — one live order, sent or about to be sent, to the exchange.

@details Distinct from `Trade` (`domain/backtesting/trade.py`): `Trade` is
the *result* of a backtest — always closed, always instant-fill by
definition. `Order` is the vocabulary a real exchange interaction needs
that backtesting never did: something that can sit `NEW`, get
`PARTIALLY_FILLED`, or be `REJECTED` outright. `architecture-rule.md` §5.5's
quick test — "does changing `Trade` force a change to `Order`?" — answers
no, which is why this lives in its own `domain/trading/` package rather
than beside `Trade`.

`frozen=True`: an `Order` is a value, not a mutable record this app edits
in place. A status change (per `order_status.is_valid_transition`) produces
a *new* `Order` via `dataclasses.replace`, so nothing can observe a
half-updated order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.time_in_force import TimeInForce
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide


@dataclass(frozen=True)
class Order:
    """Immutable description of one order this app has built (and may or
    may not have sent yet — see `status`).

    @details `price` is required for `OrderType.LIMIT`, ignored for
    `MARKET`; `stop_price` is required for `STOP_MARKET`/
    `TAKE_PROFIT_MARKET`, ignored otherwise. `time_in_force` is only
    meaningful for `LIMIT` (see `TimeInForce`'s own docstring). None of
    these per-type requirements are enforced here — `Order` is a plain data
    holder; `EPIC-021F`'s submission path is where "does this order type
    have what it needs" gets checked, against the exchange's own filters.
    """

    client_order_id: ClientOrderId
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    status: OrderStatus = OrderStatus.NEW
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    reduce_only: bool = False
    #: The exchange's own account of when this order was last updated
    #: (`updateTime`/`"T"` on the wire) — `None` only for an `Order` this
    #: app has built locally and not yet sent (`EPIC-021I` §3.1: the
    #: exchange's time, never a locally-stamped `datetime.now()`, so it
    #: matches Binance's own order history exactly).
    order_time: datetime | None = None
