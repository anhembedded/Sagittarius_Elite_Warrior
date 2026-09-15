"""`EPIC-021F` — why the exchange refused an order, named rather than a raw
Binance error code.

@details The Application layer (and every layer above it) is never allowed
to know a Binance error code — that is an Infrastructure detail
(`binance_error_translator.py` is the only place that reads one). This
module owns both the closed vocabulary of reasons and the exception that
carries one, exactly like `ConnectionFailureKind` +
`ExchangeConnectionStatus` (`EPIC-021D`) are co-located: implementation
details of one cohesive concept, not independent governance concerns.
"""

from __future__ import annotations

from enum import Enum


class OrderRejectionReason(Enum):
    """@brief A named, UI-branchable reason an order was refused.

    @details `UNKNOWN` is not a failure of this enum — it is the honest
    answer for a Binance error code this app does not (yet) have a
    narrower name for, including a code that is real and documented but
    does not describe an order-content problem (`-1021`, clock skew, is
    exactly this: a real code, already handled elsewhere by `EPIC-021D`,
    that simply is not one of the reasons an *order* gets rejected).
    `binance_error_translator.py` always keeps the original message
    alongside `UNKNOWN` so nothing is silently swallowed.
    """

    INSUFFICIENT_MARGIN = "insufficient_margin"
    LOT_SIZE = "lot_size"
    MIN_NOTIONAL = "min_notional"
    PRICE_FILTER = "price_filter"
    REDUCE_ONLY_REJECTED = "reduce_only_rejected"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class OrderRejectedByExchangeError(Exception):
    """@brief Raised by `ITradingClient.place_order()` when the exchange
    itself refuses the order — whether that refusal came from
    `/fapi/v1/order/test` (`EPIC-021F`, nothing was ever going to be
    created) or `/fapi/v1/order` (`EPIC-021G`).

    @details Carries both the named `reason` a caller can branch on and
    `raw_message` (Binance's own text) so a human can still look it up —
    the same "named reason, original text preserved" shape as
    `ExchangeConnectionStatus`'s failure kinds.
    """

    def __init__(self, reason: OrderRejectionReason, raw_message: str) -> None:
        super().__init__(f"{reason.value}: {raw_message}")
        self.reason = reason
        self.raw_message = raw_message
