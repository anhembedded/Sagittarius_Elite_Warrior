"""`BOT-221` — the shared reading of each symbol's mark price, found by venue and symbol.

One `BoundedAgeReading` per (venue, symbol), made when the first reader of the symbol asks and
kept. `premiumIndex` is one request a symbol, and every running bot read its symbol's mark twice
a beat (its exit watch and its risk watch), so one reading serves both. Two bots never hold one
symbol of a venue (`other_active_bot`), so today the readers sharing a reading are the two
watches of one bot; the key is the symbol so that a second reader of it shares with no change.

The mark guards a stop loss, a take profit and the risk watch, so it is served for at most half a
beat (`SHARED_READING_MAX_AGE_SECONDS`, never older than the one beat a watch may judge on) and
is dropped by any order, cancel or fill on the symbol (`BotAccountReads.account_changed`). A
failed read is never kept.
"""

from __future__ import annotations

import threading
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.bounded_age_reading import (
    BoundedAgeReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.shared_position_reads import (
    SHARED_READING_MAX_AGE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.mark_source_futures import (
    read_mark_price,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class SharedMarkReads:
    """@brief The shared mark-price reading, by venue and symbol."""

    def __init__(
        self,
        ports: IVenueTradingPorts,
        monotonic: IMonotonicClock,
        max_age_seconds: float = SHARED_READING_MAX_AGE_SECONDS,
    ) -> None:
        self._ports = ports
        self._monotonic = monotonic
        self._max_age = max_age_seconds
        self._lock = threading.Lock()
        self._by_symbol: dict[tuple[TradingVenue, str], BoundedAgeReading[Decimal]] = {}

    def of(self, venue: TradingVenue, symbol: str) -> BoundedAgeReading[Decimal]:
        with self._lock:
            reading = self._by_symbol.get((venue, symbol))
            if reading is None:
                terms = self._ports.get(venue).order_entry_terms
                reading = BoundedAgeReading(
                    lambda: read_mark_price(terms, symbol),
                    self._monotonic,
                    self._max_age,
                )
                self._by_symbol[(venue, symbol)] = reading
            return reading
