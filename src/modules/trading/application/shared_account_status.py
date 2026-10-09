"""`EPIC-035V` — one account read serves the periodic refreshes that fire together.

A Spot venue's holdings refresh and its account summary refresh are two jobs on
one interval, and each made the whole account read (ping, server time, account,
a ticker per holding): twice the request weight, and the owner's log showed every
`SpotAccountReader equity: priced …` line twice per 5 s. The two refresh query
handlers now read through this object, which keeps a venue's last good status for
`SHARED_READ_SECONDS`, so the second job of a tick finds the first one's read.

Only those two handlers use it. Every other caller of `check_connection()` (the
order gate, the readiness checks, an Emergency Stop) reads the exchange itself,
and the summary read that follows a fill asks for a fresh one (`read_now`): the
fill changed the balances after the tick's read.

A failed status is never kept: the next caller asks again.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: How long a good read is shared: two jobs scheduled on one interval run within
#: a moment of each other, and a read this young is the tick's own.
SHARED_READ_SECONDS: float = 1.0


@dataclass(slots=True)
class _Kept:
    status: ExchangeConnectionStatus
    read_at: float


class SharedAccountStatus:
    """The last good account status of each venue, for the refreshes of one tick."""

    def __init__(
        self,
        clock: Callable[[], float],
        window_seconds: float = SHARED_READ_SECONDS,
    ) -> None:
        """@param clock Monotonic seconds."""
        self._clock = clock
        self._window = window_seconds
        self._lock = threading.Lock()
        self._kept: dict[TradingVenue, _Kept] = {}

    def read(
        self, venue: TradingVenue, reader: ITradingAccountReader
    ) -> ExchangeConnectionStatus:
        """The venue's status: the kept one if it is younger than the window,
        else a read from the exchange. A second caller waits for a read already
        under way and shares it."""
        with self._lock:
            kept = self._kept.get(venue)
            if kept is not None and self._clock() - kept.read_at < self._window:
                return kept.status
            return self._read_from(venue, reader)

    def read_now(
        self, venue: TradingVenue, reader: ITradingAccountReader
    ) -> ExchangeConnectionStatus:
        """Read the exchange whatever is kept; the answer is kept for the next
        `read`."""
        with self._lock:
            return self._read_from(venue, reader)

    def _read_from(
        self, venue: TradingVenue, reader: ITradingAccountReader
    ) -> ExchangeConnectionStatus:
        status = reader.check_connection()
        if status.reachable and status.failure is None:
            self._kept[venue] = _Kept(status, self._clock())
        else:
            self._kept.pop(venue, None)
        return status
