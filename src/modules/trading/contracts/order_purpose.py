"""`EPIC-028I` — why an order is sent: to take a position, or to protect
one already held.

@details A protective order (a take-profit or stop-loss placed after an
entry fills) can only reduce a position: it is sent `reduce_only`, so the
exchange refuses it if it would open or grow one. The app's trading limits
(`TradingLimitPolicy`) guard against opening too much, too fast; a
protective order does neither, and counting it would let the limits refuse
the very order that protects a position the limits already let through (the
PR #300 epic review). So the limits pass a protective order, the session
does not count it, and `ExecuteOrderCommand` refuses one that is not
`reduce_only`, which is what keeps the exemption from opening a position.

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
