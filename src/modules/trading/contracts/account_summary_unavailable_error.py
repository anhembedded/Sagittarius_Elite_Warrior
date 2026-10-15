"""`BUG-174` — the venue's account could not be read, and why.

@details Raised by `GetAccountSummaryQueryHandler` in place of the bare
`None` it used to answer, which dropped the connection check's
`ConnectionFailureKind`: a desk logged "could not be read: None" for a
rejected key and showed no notice. The kind travels with the exception, so
the log, the stale mark and the notice's Details all name it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    EXCHANGE_PAUSE_TAG,
)


class AccountSummaryUnavailableError(RuntimeError):
    """The account check failed with `failure`; no summary exists."""

    def __init__(self, failure: ConnectionFailureKind) -> None:
        self.failure = failure
        self.reason = f"the account could not be read ({failure.value})"
        paused = (
            f" {EXCHANGE_PAUSE_TAG}"
            if failure is ConnectionFailureKind.RATE_LIMITED
            else ""
        )
        super().__init__(f"Account summary could not be read: {failure.value}{paused}")
