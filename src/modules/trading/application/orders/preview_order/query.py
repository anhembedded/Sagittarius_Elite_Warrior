from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    TRIGGERED_ORDER_TYPES,
    OrderType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class PreviewOrderQuery:
    """@brief Query to build and validate one live order without sending it
    (`EPIC-021E`).

    @details `reference_price` is required and caller-supplied — this app
    has no live mark-price network path in scope for this task (fetching
    one belongs to `EPIC-021F`'s real execution path, not this
    domain-and-preview task); the caller decides what price the notional
    estimate is computed against. For `OrderType.LIMIT` this doubles as the
    order's own limit price; for the other order types it is only used to
    estimate notional.

    `reduce_only` defaults `False` (open/pyramid) — `order-preview`/
    `order-dry-run` never set it. `EPIC-021G`'s `LiveTradingCoordinator`
    is the first real caller that needs `True`: closing a LONG (`SELL`)
    and closing a SHORT (`COVER`) both require it, or the exchange reads
    the order as opening a new position instead of closing the existing
    one (`domain/trading/policies/signal_action_to_order_intent.py`).
    """

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    reference_price: Decimal
    reduce_only: bool = False
    #: `EPIC-028B` (ADR D3) — the venue this acts on. Keyword-only and
    #: required: a caller that forgets it fails at construction, never
    #: silently addresses some default venue.
    venue: TradingVenue = field(kw_only=True)
    #: `EPIC-028O` — the price a `STOP_LIMIT` waits for; `reference_price`
    #: is then its limit price. Required for a stop-limit, refused otherwise.
    stop_price: Decimal | None = field(default=None, kw_only=True)
    #: How long a resting order lives; `None` means GTC. Only for the
    #: resting types (`LIMIT`, `STOP_LIMIT`).
    time_in_force: TimeInForce | None = field(default=None, kw_only=True)
    #: The quote amount a market buy spends instead of a base quantity
    #: (Spot `quoteOrderQty`); `quantity` is then only the estimate shown.
    quote_quantity: Decimal | None = field(default=None, kw_only=True)
    #: The market's last price, which a stop-limit's stop is judged against
    #: (`stop_trigger_side.py`). Required for a stop-limit.
    last_price: Decimal | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """@throws ValueError a field this order type cannot use, or one it
        needs, so an inconsistent order never reaches the exchange."""
        is_stop = self.order_type in TRIGGERED_ORDER_TYPES
        if is_stop and (self.stop_price is None or self.last_price is None):
            raise ValueError(
                f"a {self.order_type.value.replace('_', '-')} needs a stop price "
                "and the last price"
            )
        if not is_stop and self.stop_price is not None:
            raise ValueError(f"{self.order_type.name} takes no stop price")
        resting = self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT)
        if self.time_in_force is not None and not resting:
            raise ValueError(f"{self.order_type.name} takes no time in force")
        if self.quote_quantity is not None and (
            self.order_type is not OrderType.MARKET or self.side is not OrderSide.BUY
        ):
            raise ValueError("only a market buy can be sized by quote amount")
        if self.quote_quantity is not None and self.quote_quantity <= 0:
            raise ValueError("a quote amount must be positive")
