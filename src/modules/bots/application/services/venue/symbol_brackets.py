"""`EPIC-039H` — a Futures symbol's leverage brackets, read once and kept.

@details A bracket table changes rarely (Binance revises it now and then), and it is asked at
every budget registration, which a running bot makes after each restart, gap, resume and stop. One
network read per symbol is kept; `refresh` reads it again, and a start does, because the plan-time
guard judges the ladder against the table as it is then.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class BracketsUnavailableError(RuntimeError):
    """The venue has no leverage brackets to read (it is not a leveraged market)."""


class SymbolBrackets:
    """Reads and keeps each symbol's brackets, per venue."""

    def __init__(self, ports: IVenueTradingPorts) -> None:
        self._ports = ports
        self._kept: dict[tuple[TradingVenue, str], LeverageBrackets] = {}
        self._lock = threading.Lock()

    def get(self, venue: TradingVenue, symbol: str) -> LeverageBrackets:
        """@raise BracketsUnavailableError The venue has no brackets.
        @raise AccountControlUnavailableError The exchange never answered."""
        with self._lock:
            kept = self._kept.get((venue, symbol))
        return kept if kept is not None else self.refresh(venue, symbol)

    def refresh(self, venue: TradingVenue, symbol: str) -> LeverageBrackets:
        """Read the table from the exchange again and keep it.
        @raise BracketsUnavailableError The venue has no brackets."""
        read = self._ports.get(venue).order_entry_terms.leverage_brackets_for(symbol)
        if isinstance(read, NotApplicable):
            raise BracketsUnavailableError(
                f"{venue.display_name} has no leverage brackets"
            )
        with self._lock:
            self._kept[(venue, symbol)] = read
        return read
