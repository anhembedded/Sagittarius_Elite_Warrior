"""`EPIC-029J` J1b — the order pacers of the venues, one per venue and spacing.

The exchange limits the orders of an account, not of a bot (`EPIC-029A` notes: the `ORDERS` rate
limit per 10 seconds), and the bots of a venue share the account. A pacer per bot kept each bot's
orders a spacing apart and nothing between bots, so two bots laying ladders at once doubled the
venue's rate. One pacer per venue keeps the venue's orders a spacing apart whichever bot sends
them, at the cost that a bot waits behind its neighbours' orders (a ladder of 20 orders is 5 s).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.monotonic_order_pacer import (
    MonotonicOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueOrderPacers:
    """Hands every bot of a venue the venue's pacer."""

    def __init__(
        self, build: Callable[[timedelta], IOrderPacer] = MonotonicOrderPacer
    ) -> None:
        self._build = build
        self._lock = threading.Lock()
        self._pacers: dict[tuple[TradingVenue, timedelta], IOrderPacer] = {}

    def of(self, venue: TradingVenue, spacing: timedelta) -> IOrderPacer:
        with self._lock:
            pacer = self._pacers.get((venue, spacing))
            if pacer is None:
                pacer = self._build(spacing)
                self._pacers[(venue, spacing)] = pacer
            return pacer
