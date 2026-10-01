"""`EPIC-028O` — reads a Futures symbol's mark price.

@details Public market data (`GET /fapi/v1/premiumIndex`), so no
credentials. A Spot `VenueContext` holds no implementation: Spot has no mark
price, and the query answers `NotApplicable` from that absence, never a
Spot last price passed off as a mark.

Plausible extensions, each one implementation or one method here: the
funding rate and next funding time from the same answer; a reader fed by the
`@markPrice` stream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)


class IMarkPriceReader(ABC):
    """One Futures venue's mark prices, read from the exchange."""

    @abstractmethod
    def mark_price(self, symbol: str) -> MarkPrice:
        """@brief `symbol`'s mark price now.
        @throws MarketPriceUnavailableError The exchange did not answer, or
        does not list `symbol`."""
