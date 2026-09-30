"""`EPIC-028E` — the exchange would not give an account's history.

@details Raised by `IAccountHistoryReader` implementations in place of the
SDK's own exceptions, so a caller outside the adapter never imports
`python-binance` to catch a failed read (`architecture-rule.md` §3). The
original exception is chained (`raise ... from`), so the log still shows the
exchange's code and message.
"""

from __future__ import annotations


class AccountHistoryUnavailableError(RuntimeError):
    """An order or trade history read failed; nothing partial is returned."""
