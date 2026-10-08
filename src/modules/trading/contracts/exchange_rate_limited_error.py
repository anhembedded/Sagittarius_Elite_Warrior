"""`EPIC-035D` — the exchange (or this app's own gate) said: not yet.

A rate-limit answer (HTTP 429, `-1003`, `-1015`) or a ban (HTTP 418) is not a
fault of the request and says nothing about the account: it names a pause. The
venue's gate closes for it, so every later call of that venue raises this error
at once, without a request, until the pause ends (`retry_after` is what is left).

It is an `OrderRejectedByExchangeError` with reason `RATE_LIMIT`, so every caller
that already words an order's rejection (the manual desk, the strategy's live
path, the CLI) words this one without a change; a caller that can wait — a bot —
catches this subtype and waits `retry_after`.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)


class ExchangeRateLimitedError(OrderRejectedByExchangeError):
    """@brief A call was refused, or not sent, because of a rate limit.

    @details Nothing was placed by the call that raised this: the exchange
    answered the limit before reading the request, or the gate stopped it before
    it left the machine. An order's submit that raises this is therefore safe to
    send again once `retry_after` has passed; it is not an unknown outcome.
    """

    def __init__(
        self, retry_after: timedelta, *, banned: bool, raw_message: str
    ) -> None:
        super().__init__(OrderRejectionReason.RATE_LIMIT, raw_message)
        self.retry_after = retry_after
        self.banned = banned
