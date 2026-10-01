"""`EPIC-028O` — the exchange did not answer a book-ticker or mark-price
read."""

from __future__ import annotations


class MarketPriceUnavailableError(RuntimeError):
    """Raised by `IBookTickerReader` and `IMarkPriceReader` for a network
    failure, an exchange error, an unlisted symbol or an answer that cannot be
    read, the cause chained, so `application/` never imports the SDK's
    exception types."""
