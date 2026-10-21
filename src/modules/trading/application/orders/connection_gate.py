"""`EPIC-035F` — which safety gate a failed connection check is.

The execute and cancel handlers both ask the venue's account reader whether the
connection works before they touch an order. A check that did not pass was always
`CONNECTION_NOT_READY`, which a caller reads as "wait for it". A check the exchange
answered by rejecting the API key (`-2015`, `-2008`, `-2014`) is not that: nothing
will make it pass but a different key, and an order already resting cannot be
cancelled meanwhile. It is `KEY_REJECTED`, so a caller can tell the two apart.

A check the exchange answered with a pause (`RATE_LIMITED`: HTTP 429, `-1003`, a ban) is
neither: the key and the network are fine, and the order is not wrong. It is the pause itself,
told the way a rejected submit tells it, `ExchangeRateLimitedError`, so a bot waits it out
(`GridRateLimitPause`) instead of stopping as if trading were off (`BUG-216`).

The check is the venue's last passing one when that is younger than a beat
(`OrderConnectionMemory`, `BUG-247`): a ladder of fifty orders reads the account once, not fifty times.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    EXCHANGE_PAUSE_TAG,
)


def connection_block(status: ExchangeConnectionStatus) -> ExecuteOrderSafetyGate | None:
    """The gate `status` blocks an order on, or `None` when the connection works."""
    if status.reachable and status.failure is None:
        return None
    if status.failure is ConnectionFailureKind.KEY_REJECTED:
        return ExecuteOrderSafetyGate.KEY_REJECTED
    return ExecuteOrderSafetyGate.CONNECTION_NOT_READY


def order_connection_block(scope: VenueTradingScope) -> ExecuteOrderSafetyGate | None:
    """The gate an order or a cancel on `scope`'s venue is blocked on, or `None`.

    @raise ExchangeRateLimitedError The check met the exchange's pause: nothing is wrong,
    and nothing can be sent until `retry_after` has passed."""
    status = scope.order_connection.status(scope.ports.account_reader)
    if status.failure is ConnectionFailureKind.RATE_LIMITED:
        raise _pause_of(status)
    return connection_block(status)


def _pause_of(status: ExchangeConnectionStatus) -> ExchangeRateLimitedError:
    if status.retry_after is None:
        raise ValueError("a RATE_LIMITED connection status names no pause")
    return ExchangeRateLimitedError(
        status.retry_after,
        banned=status.banned,
        raw_message=f"the connection check met the exchange's pause {EXCHANGE_PAUSE_TAG}",
    )
