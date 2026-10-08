"""`EPIC-035F` — which safety gate a failed connection check is.

The execute and cancel handlers both ask the venue's account reader whether the
connection works before they touch an order. A check that did not pass was always
`CONNECTION_NOT_READY`, which a caller reads as "wait for it". A check the exchange
answered by rejecting the API key (`-2015`, `-2008`, `-2014`) is not that: nothing
will make it pass but a different key, and an order already resting cannot be
cancelled meanwhile. It is `KEY_REJECTED`, so a caller can tell the two apart.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)


def connection_block(status: ExchangeConnectionStatus) -> ExecuteOrderSafetyGate | None:
    """The gate `status` blocks an order on, or `None` when the connection works."""
    if status.reachable and status.failure is None:
        return None
    if status.failure is ConnectionFailureKind.KEY_REJECTED:
        return ExecuteOrderSafetyGate.KEY_REJECTED
    return ExecuteOrderSafetyGate.CONNECTION_NOT_READY
