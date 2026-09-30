"""`EPIC-028F` — the exchange did not answer a commission-rate read."""

from __future__ import annotations


class CommissionRateUnavailableError(RuntimeError):
    """Raised by `ICommissionRateReader` for a missing credential, a network
    failure or an exchange error, the cause chained, so `application/`
    never imports the SDK's exception types."""
