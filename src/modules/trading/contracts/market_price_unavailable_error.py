"""`EPIC-028O` — the exchange did not answer a book-ticker or mark-price
read."""

from __future__ import annotations

from datetime import timedelta


class MarketPriceUnavailableError(RuntimeError):
    """Raised by `IBookTickerReader` and `IMarkPriceReader` for a network
    failure, an exchange error, an unlisted symbol or an answer that cannot be
    read, the cause chained, so `application/` never imports the SDK's
    exception types."""


class MarketPriceRateLimitedError(MarketPriceUnavailableError):
    """The read failed because the exchange asked for a pause (`EPIC-035D`).

    @details Still "unavailable" to every caller that only needs to know the read
    failed; a caller that can wait (a bot) reads `retry_after`."""

    def __init__(self, message: str, retry_after: timedelta) -> None:
        super().__init__(message)
        self.retry_after = retry_after
