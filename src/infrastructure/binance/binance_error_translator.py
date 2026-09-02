"""`EPIC-021F` — translates a `BinanceAPIException` into a named
`OrderRejectionReason`. The one place in this app allowed to read a Binance
error code for order rejection; everything above Infrastructure sees only
the named reason plus the original message.

**Verification note** (same disclosure as `EPIC-021A`/`C`/`D`): the code
mapping below is written from Binance's documented Futures API error codes,
not re-verified against a live call — egress to every `*.binance.*` domain
is policy-blocked in this sandbox.
"""

from __future__ import annotations

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectionReason,
)

#: Binance's one generic "filter failure" code — shared by several distinct
#: filters, so it alone cannot be looked up in the plain dict below.
_GENERIC_FILTER_FAILURE_CODE = -1013

#: Codes that mean exactly one thing, no message-text disambiguation needed.
#: `-1021` (Invalid timestamp / clock skew) is deliberately absent from this
#: map, not merely unmapped: it is a real, documented code — already
#: classified for the *connection* check by `EPIC-021D`'s
#: `ConnectionFailureKind.CLOCK_SKEW` — but it does not describe an
#: order-content problem, so no `OrderRejectionReason` member fits it. It
#: falls through to `UNKNOWN` below, on purpose, with the original message
#: kept: a recognized-elsewhere code is not the same thing as a known
#: order-rejection reason.
_UNAMBIGUOUS_CODE_TO_REASON: dict[int, OrderRejectionReason] = {
    -2019: OrderRejectionReason.INSUFFICIENT_MARGIN,  # "Margin is insufficient."
    -4164: OrderRejectionReason.MIN_NOTIONAL,  # Futures-specific: "Order's notional must be no smaller than X."
    -2022: OrderRejectionReason.REDUCE_ONLY_REJECTED,  # "ReduceOnly Order is rejected."
    -1003: OrderRejectionReason.RATE_LIMIT,  # "Too many requests."
}

#: `-1013` is Binance's one generic "filter failure" code, shared by
#: several distinct filters (`LOT_SIZE`, `PRICE_FILTER`, `MIN_NOTIONAL`,
#: ...) — the filter name only ever shows up in the message text, never as
#: a separate field, so this code alone cannot be looked up in a plain
#: dict. Checked in this order because a `MIN_NOTIONAL` message can itself
#: mention "quantity" incidentally; the more specific substrings go first.
_DASH_1013_MESSAGE_SUBSTRING_TO_REASON: tuple[tuple[str, OrderRejectionReason], ...] = (
    ("notional", OrderRejectionReason.MIN_NOTIONAL),
    ("price", OrderRejectionReason.PRICE_FILTER),
    ("quantity", OrderRejectionReason.LOT_SIZE),
    ("lot_size", OrderRejectionReason.LOT_SIZE),
)


def _translate_dash_1013(message: str) -> OrderRejectionReason:
    lowered = message.lower()
    for substring, reason in _DASH_1013_MESSAGE_SUBSTRING_TO_REASON:
        if substring in lowered:
            return reason
    return OrderRejectionReason.UNKNOWN


def translate_binance_error(exc: BinanceAPIException) -> OrderRejectionReason:
    """@brief Maps one `BinanceAPIException` to a named `OrderRejectionReason`.
    @details Never raises — an unrecognized code, or `-1013` with message
    text this app doesn't recognize either, both degrade to `UNKNOWN`
    rather than crashing the caller. `exc.message`/`str(exc)` still carries
    the original text for a human to read; this function only narrows
    which *category* the caller can branch on.
    """
    if exc.code == _GENERIC_FILTER_FAILURE_CODE:
        return _translate_dash_1013(exc.message or "")
    return _UNAMBIGUOUS_CODE_TO_REASON.get(exc.code, OrderRejectionReason.UNKNOWN)
