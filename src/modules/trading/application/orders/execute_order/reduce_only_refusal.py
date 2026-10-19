"""`BUG-231` — what the log says when the exchange refuses a reduce-only order.

@details A reduce-only order the exchange refuses (`-2022`, "ReduceOnly Order is rejected.") says
nothing of why: the owner's incident had the same orders accepted at one hour and refused at the
next, and the journal held only the exception type. So the refusal is logged once, at WARNING and
tagged `[reduce-only-refused]`, with what lets a cause be ruled in or out in one run: the order as
sent (side, type, quantity, price, trigger, `reduceOnly`, `closePosition`, `positionSide`), the
account's position mode, the position the exchange reports on the symbol with its own margin type,
the owner book's position beside it, and the exchange's own text. Every read here is a diagnostic:
one that fails is said, never raised, so the refusal itself still reaches the caller untouched.

The reads are network requests, so they run **after** the venue's live-submission lock is released
(`AfterRelease`, entered before the lock so it exits after it): a refusal on a slow exchange must
not hold up every other live order of the venue for the reads' sake. The refusal's own caller still
waits for them, since the `with` exits before the refusal propagates: a limit, bounded by the
reads' request timeouts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from types import TracebackType
from typing import Self

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


@dataclass(frozen=True, slots=True)
class RefusedOrder:
    """What a refusal is logged with: the refused order, whose it was and who refused it."""

    scope: VenueTradingScope
    client: ITradingClient
    order: Order
    refusal: OrderRejectedByExchangeError
    #: The signed position the order's owner book holds (a bot's derived one), `None` for an
    #: order with no owner: set beside the exchange's, it shows whether the two agree.
    engine_position: Decimal | None = None


class AfterRelease:
    """Logs the reduce-only refusal noted while it is open, once the `with` has been left.

    Entered before the venue's live-submission lock, so it exits after the lock is released."""

    def __init__(self) -> None:
        self._refused: RefusedOrder | None = None

    def note(self, refused: RefusedOrder) -> None:
        self._refused = refused

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._refused is not None:
            log_if_reduce_only_refused(self._refused)


def log_if_reduce_only_refused(refused: RefusedOrder) -> None:
    """Log the refusal with its context when it is a reduce-only refusal; nothing otherwise."""
    if refused.refusal.reason is not OrderRejectionReason.REDUCE_ONLY_REJECTED:
        return
    order = refused.order
    logger.warning(
        "[reduce-only-refused] Reduce-only order refused on %s: %s %s %s qty=%s price=%s "
        "trigger=%s reduceOnly=%s closePosition=%s positionSide=%s; account position mode=%s; "
        "position on the symbol (exchange)=%s; owner book position=%s; exchange said: %s",
        refused.scope.venue.value,
        order.symbol,
        order.side.value,
        order.order_type.value,
        order.quantity,
        order.price,
        order.stop_price,
        order.reduce_only,
        order.close_position,
        _POSITION_SIDE_SENT,
        _position_mode(refused.scope),
        _position(refused.client, order.symbol),
        "no owner" if refused.engine_position is None else refused.engine_position,
        refused.refusal.raw_message,
    )


def _position_mode(scope: VenueTradingScope) -> str:
    """The account's position mode as the connection check reads it now (a One-way answer can be
    up to a minute old, `PositionModeMemory`), or why it could not be read."""
    try:
        status = scope.ports.account_reader.check_connection()
    except Exception as exc:  # a diagnostic read never masks the refusal it explains
        logger.warning(
            "[reduce-only-refused] The connection check for the refusal log failed",
            exc_info=True,
        )
        return f"unreadable ({type(exc).__name__})"
    if status.failure is not None:
        return f"unreadable ({status.failure.value})"
    return status.position_mode.value if status.position_mode else "not reported"


def _position(client: ITradingClient, symbol: str) -> str:
    """The signed position the exchange reports on `symbol` and its margin type, or why it could
    not be read. The margin type is the position's own: the account-wide figure of the
    connection check is that of the first open position of any symbol."""
    try:
        held = client.get_positions(symbol)
    except Exception as exc:  # a diagnostic read never masks the refusal it explains
        logger.warning(
            "[reduce-only-refused] The position read for the refusal log failed",
            exc_info=True,
        )
        return f"unreadable ({type(exc).__name__})"
    if not held:
        return "0 (flat)"
    amount = sum((p.position_amt for p in held), Decimal(0))
    margins = ", ".join(sorted({p.margin_type.value for p in held}))
    return f"{amount} margin type={margins}"
