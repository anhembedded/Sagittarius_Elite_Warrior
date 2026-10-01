"""`EPIC-028I` — why an order is sent: to take a position, to protect one
already held, or to close one.

@details A protective order (a take-profit or stop-loss placed after an
entry fills) and a close (the account tab's "close at market") can only
reduce a position: each is sent `reduce_only`, so the exchange refuses it if
it would open or grow one. The app's trading limits (`TradingLimitPolicy`)
guard against opening too much, too fast; an order that only reduces does
neither, and counting it would let the limits refuse the very order that
protects or closes a position the limits already let through (the PR #300
epic review; a close of a position larger than the per-order notional, or
in a session at its order cap, could otherwise never be sent: the PR #307
review). So the limits pass such an order and the session does not count
it.

The exemption holds only where the exchange enforces `reduce_only`:
`ExecuteOrderCommand` refuses an order with a reducing purpose that is not
`reduce_only`, or whose venue is not Futures (Spot has no reduce-only; its
mapper never sends the flag), and refuses a protective order that is not a
triggered type.

Shared with `EPIC-026K`, which places the same protective orders for a
strategy; both build them with `protective_orders_for`.
"""

from __future__ import annotations

from enum import Enum


class OrderPurpose(str, Enum):
    """Why an order is sent."""

    #: Takes or adds to a position; every trading limit applies.
    ENTRY = "entry"
    #: A reduce-only take-profit or stop-loss for a position already held.
    PROTECTIVE = "protective"
    #: A reduce-only order that closes a position already held.
    CLOSE = "close"

    @property
    def only_reduces(self) -> bool:
        """Whether an order sent for this purpose can only reduce a
        position, and so passes the trading limits."""
        return self is not OrderPurpose.ENTRY
