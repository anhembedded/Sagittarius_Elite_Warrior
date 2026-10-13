"""`EPIC-039G` — reads a Futures symbol's funding rate and next funding time.

@details Public market data (`GET /fapi/v1/premiumIndex`), so no credentials.
A Spot `VenueContext` holds no implementation: Spot has no funding, and the
query answers `NotApplicable.ON_THIS_VENUE` from that absence, never a zero
rate that a cost model would add up as "free".

Plausible extensions, each one implementation or one method here: the funding
history (`GET /fapi/v1/fundingRate`) for the backtest (`EPIC-039K`); a reader
fed by the `@markPrice` stream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.funding_rate import (
    FundingRate,
)


class IFundingReader(ABC):
    """One Futures venue's funding rates, read from the exchange."""

    @abstractmethod
    def funding_rate(self, symbol: str) -> FundingRate:
        """@brief `symbol`'s funding rate and next funding time now.
        @throws MarketPriceUnavailableError The exchange did not answer, does
        not list `symbol`, or answered without a funding rate."""
