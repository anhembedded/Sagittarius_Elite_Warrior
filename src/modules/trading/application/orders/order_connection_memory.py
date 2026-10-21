"""`BUG-247` — the connection an order or a cancel was last found to have, kept for a beat.

Every order and every cancel asks the venue's account reader whether the connection works before
it touches the order (`order_connection_block`). On Futures that check is a ping, the server
time and the whole account: 7 weight (`positionSide` adds 30 a minute). A Grid laying or
re-laying a ladder sends one order per level, so a 48-level ladder spent about 340 weight on
checks alone, 760 for the start, and two bots doing it together closed the gate at 70 % of the
minute and paused every read (the owner's VPS, `BUG-247`).

A check that passed is therefore trusted for `ORDER_CONNECTION_REUSE_SECONDS`. A check that did not
pass (unreachable, key rejected, rate limited, Hedge mode) is never kept: the next order asks
again, as it did before. What the check guards (a key, the network, the account's mode) changes in
minutes, not within a beat, and `PositionModeMemory` already trusts the mode for 60 s; a failure
that does arrive inside the window is met by the order itself, which the exchange refuses with its
own answer. The lock covers the memo only, never the network read, so a slow read never holds up
another order or a cancel; and a read whose answer arrives after a newer read's is not kept.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)

#: One price-watch beat (`CHECK_EVERY_SECONDS`): a ladder placed at the pacer's spacing sends
#: about twenty orders inside it.
ORDER_CONNECTION_REUSE_SECONDS: float = 5.0


@dataclass(frozen=True, slots=True)
class _Kept:
    status: ExchangeConnectionStatus
    read_at: float


class OrderConnectionMemory:
    """The last passing connection check of one venue, for the orders that follow it."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        reuse_seconds: float = ORDER_CONNECTION_REUSE_SECONDS,
    ) -> None:
        """@param clock Monotonic seconds."""
        self._clock = clock
        self._reuse_seconds = reuse_seconds
        self._lock = threading.Lock()
        self._kept: _Kept | None = None
        #: Reads begun, and the newest one whose result the memo holds.
        self._begun = 0
        self._settled = 0

    def status(self, reader: ITradingAccountReader) -> ExchangeConnectionStatus:
        """The kept status if it passed less than the window ago, else a read from the exchange."""
        with self._lock:
            kept = self._kept
        if kept is not None and 0 <= self._clock() - kept.read_at < self._reuse_seconds:
            return kept.status
        with self._lock:
            self._begun += 1
            mine = self._begun
        read_at = self._clock()
        status = reader.check_connection()
        with self._lock:
            # A read that began before one already settled is older news: a slow pass must not
            # bring back what a later failure cleared.
            if mine > self._settled:
                self._settled = mine
                self._kept = (
                    _Kept(status, read_at)
                    if status.reachable and status.failure is None
                    else None
                )
        return status
