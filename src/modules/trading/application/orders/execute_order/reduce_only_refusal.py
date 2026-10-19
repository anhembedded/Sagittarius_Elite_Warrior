"""`BUG-231` — what the log says when the exchange refuses a reduce-only order.

@details A reduce-only order the exchange refuses (`-2022`, "ReduceOnly Order is rejected.") says
nothing of why: the owner's incident had the same orders accepted at one hour and refused at the
next, and the journal held only the exception type. So the refusal is logged once, at WARNING and
tagged `[reduce-only-refused]`, with what lets a cause be ruled in or out in one run: the order as
sent (side, type, quantity, price, trigger, `reduceOnly`, `closePosition`, `positionSide`), the
account's position mode and margin type, the position the exchange reports on the symbol, and the
exchange's own text. Every read here is a diagnostic: one that fails is said, never raised, so the
refusal itself still reaches the caller untouched.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)

logger = logging.getLogger("App.CommandHandler")

#: Every order this app sends on a position venue goes out as One-way (`positionSide=BOTH`).
_POSITION_SIDE_SENT = "BOTH"


def log_if_reduce_only_refused(
    scope: VenueTradingScope,
    client: ITradingClient,
    order: Order,
    refusal: OrderRejectedByExchangeError,
) -> None:
    """Log `refusal` with its context when it is a reduce-only refusal; do nothing otherwise."""
    if refusal.reason is not OrderRejectionReason.REDUCE_ONLY_REJECTED:
        return
    mode, margin = _account_mode(scope)
    logger.warning(
        "Reduce-only order refused on %s: %s %s %s qty=%s price=%s trigger=%s reduceOnly=%s "
        "closePosition=%s positionSide=%s; account position mode=%s margin type=%s; "
        "position on the symbol=%s; exchange said: %s [reduce-only-refused]",
        scope.venue.value,
        order.symbol,
        order.side.value,
        order.order_type.value,
        order.quantity,
        order.price,
        order.stop_price,
        order.reduce_only,
        order.close_position,
        _POSITION_SIDE_SENT,
        mode,
        margin,
        _position(client, order.symbol),
        refusal.raw_message,
    )


def _account_mode(scope: VenueTradingScope) -> tuple[str, str]:
    """The account's position mode and margin type as the connection check reads them now."""
    try:
        status = scope.ports.account_reader.check_connection()
    except Exception as exc:  # a diagnostic read never masks the refusal it explains
        logger.warning("The connection check for the refusal log failed", exc_info=True)
        return f"unreadable ({type(exc).__name__})", "unreadable"
    mode = status.position_mode.value if status.position_mode else "not reported"
    margin = status.margin_type.value if status.margin_type else "not reported"
    return mode, margin


def _position(client: ITradingClient, symbol: str) -> str:
    """The signed position the exchange reports on `symbol`, or why it could not be read."""
    try:
        held = client.get_positions(symbol)
    except Exception as exc:  # a diagnostic read never masks the refusal it explains
        logger.warning("The position read for the refusal log failed", exc_info=True)
        return f"unreadable ({type(exc).__name__})"
    return str(sum((p.position_amt for p in held), Decimal(0)))
