"""`EPIC-021F` — which Binance Futures endpoint `ITradingClient.place_order()`
actually calls."""

from __future__ import annotations

from enum import Enum


class OrderSubmissionMode(Enum):
    """@brief A parameter *of the adapter instance*, not a `bool` threaded
    through call sites.

    @details `VALIDATE_ONLY` and `LIVE` call two genuinely different
    endpoints (`POST /fapi/v1/order/test` vs `POST /fapi/v1/order`) — a
    `dry_run: bool` in a call site (`place_order(order, True)`) reads back
    to nobody as "which endpoint". `FuturesTradingClient` is constructed
    with exactly one of these and never switches at call time.

    `EPIC-021F` only ever constructs `VALIDATE_ONLY`; nothing in this repo
    is allowed to pass `LIVE` until `EPIC-021G` opens it (enforced by an
    `ast` guard test — see that task's own file for where it's lifted).
    """

    VALIDATE_ONLY = "VALIDATE_ONLY"
    LIVE = "LIVE"
