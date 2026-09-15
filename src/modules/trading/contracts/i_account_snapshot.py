"""Port: *can we talk to the venue, and what does it hold* (HLD §3.4).

**Why this port exists.** `ExchangeConnectionStatus` is what the Settings
screen shows, what the CLI `exchange-status` command prints, and what
`submit()`'s first safety gate reads — and all three reached it by
dispatching this module's `GetExchangeConnectionStatusQuery` or
`GetOpenPositionsQuery`. Two questions, one port, because both are the same
act: *read the account, change nothing*.

@par Read-only, and never raises
Neither method can place, modify or cancel anything, and neither raises:
every failure mode — no credentials, bad signature, clock skew, an
unsupported account mode, the network — is a named value inside the answer
(`ConnectionFailureKind`). That is the promise `submit()`'s gate is written
against, with no `try` around it, and `TradingAccountReaderContract` pins it
for every implementation.

@par The seam
A second venue is the obvious next consumer, and it is local: this port says
nothing about Binance. `ExchangeConnectionStatus.venue` already carries which
venue answered, and the adapter behind the port is chosen at composition.
What is **not** local, and is not pretended otherwise: the status's
`position_mode` / `margin_type` fields are USD-M Futures concepts, so a spot
venue would answer `None` for both rather than the port growing a union.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)


class IAccountSnapshot(ABC):
    """Read this account's connection state and open positions."""

    @abstractmethod
    def check_connection(self) -> ExchangeConnectionStatus:
        """Ping the venue, measure clock skew, read balance and account mode.

        Always answers. A caller branches on `reachable` and `failure`, never
        on an exception.
        """

    @abstractmethod
    def open_positions(self) -> tuple[LivePosition, ...]:
        """Every position the venue reports open, empty when there are none.

        Empty rather than `None`: "no open positions" is the ordinary state,
        and a caller rendering a table already handles it. A venue that could
        not be reached answers empty too — `check_connection()` is how a
        caller tells "nothing open" from "could not ask".
        """
