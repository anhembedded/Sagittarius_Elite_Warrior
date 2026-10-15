"""`EPIC-029` ADR D6 — the owner's orders resting on the venue now, read for a
registration (a restart, a reconciliation), for either kind of book."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)


def resting_orders(
    registration: OwnerBudgetRegistration, scope: VenueTradingScope
) -> tuple[Order, ...]:
    """The owner's orders open on the venue now.
    @throws AccountHistoryUnavailableError The venue did not answer."""
    client = scope.ports.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)
    try:
        open_orders = client.get_open_orders(registration.symbol)
    # Converted at the seam: `ITradingClient` names no exception type, and
    # any failure of this read means the venue did not answer.
    except Exception as exc:
        raise AccountHistoryUnavailableError(f"open orders: {exc}") from exc
    return tuple(
        order
        for order in open_orders
        if order.symbol == registration.symbol
        and tag_of(str(order.client_order_id)) == registration.tag
    )


def resting_notional(order: Order) -> Decimal:
    """What a resting order commits. A resting order is a LIMIT or a
    triggered type, so it always carries a price or a stop price."""
    price = order.price if order.price is not None else order.stop_price
    return (price or Decimal(0)) * order.quantity
