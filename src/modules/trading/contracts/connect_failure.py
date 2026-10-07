"""`EPIC-034D` — why the Connect step could not read an account, as a value.

@details Not an exception: a missing key, a rejected key and a maintenance
page are ordinary outcomes the screen words and offers a retry for. The
`kind` is the same closed vocabulary every connection check uses
(`ConnectionFailureKind`); `detail` names which read failed when the kind alone
does not (the commission rates, the symbol's filters, the price).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


@dataclass(frozen=True)
class ConnectFailure:
    source: AccountSource
    kind: ConnectionFailureKind
    detail: str = ""
