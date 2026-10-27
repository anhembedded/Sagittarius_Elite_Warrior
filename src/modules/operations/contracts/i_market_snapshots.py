"""`EPIC-047H` — port: the live prices and forming candles the host holds, to be written to its market-data file.

@details The read side of the recorder, as `IHostHeldFacts` is for the facts: the publisher of the file asks it
and the exchange is asked nothing. A snapshot is a value; equal snapshots are one fact.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    SymbolMarket,
)


class IMarketSnapshots(ABC):
    @abstractmethod
    def snapshot(self) -> tuple[SymbolMarket, ...]:
        """Every symbol with a price or a mark, ordered by venue then symbol. Costs the exchange nothing."""
