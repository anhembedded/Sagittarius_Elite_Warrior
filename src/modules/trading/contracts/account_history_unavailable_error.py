"""`EPIC-028E` — the exchange would not give an account's history.

@details Raised by `IAccountHistoryReader` implementations in place of the
SDK's own exceptions, so a caller outside the adapter never imports
`python-binance` to catch a failed read (`architecture-rule.md` §3). The
original exception is chained (`raise ... from`), so the log still shows the
exchange's code and message.

`kind` is set when the exchange's answer names *why* the venue's account cannot
be read (a refused key, a bad signature, a skewed clock, a maintenance page, no
key at all): the same vocabulary the Connect step uses
(`ConnectionFailureKind`), so a screen can tell that this read failed for the
cause the connection check already reported and tell the user once (`BUG-181`).
`None` is any other failure, which a screen tells on its own.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)


class AccountHistoryUnavailableError(RuntimeError):
    """An order or trade history read failed; nothing partial is returned."""

    def __init__(self, message: str, kind: ConnectionFailureKind | None = None) -> None:
        super().__init__(message)
        self.kind = kind
