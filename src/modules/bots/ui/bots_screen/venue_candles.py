"""The Spot candles each venue's bots read: a bot's chart and its backtests
(`EPIC-029F`, `BUG-172`).

Moved out of `BotsPresenter` (the 400-line ceiling, `EPIC-033D`): resolving
market data's ports and building one `MarketDataCandleFeed` over Spot is one
step of the presenter's construction, with no state of the presenter's own in it.

A bot's chart shows the market its orders fill in: a Spot Testnet bot charts
`testnet.binance.vision`, a Spot Mainnet bot the public mainnet. So the candles
are built **per venue**, from that venue's `MarketDataPorts`, the first time a
bot of the venue is selected.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
        TradingVenue,
    )
    from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True, slots=True)
class VenueCandles:
    """A venue's sync port, which the backtests need on its own, and its Spot
    candle feed."""

    sync: IMarketDataSync
    feed: MarketDataCandleFeed


def venue_candles(container: IContainer) -> Callable[[TradingVenue], VenueCandles]:
    """Each venue's `VenueCandles`, built on first ask and the same on every
    call: a stream owner and the sync of the same bot must agree on the venue."""
    sources = container.resolve(IMarketDataSources)
    built: dict[TradingVenue, VenueCandles] = {}

    def candles_of(venue: TradingVenue) -> VenueCandles:
        candles = built.get(venue)
        if candles is None:
            ports = sources.ports_for(venue.market_data_venue)
            candles = VenueCandles(
                ports.sync,
                # A Grid is a Spot kind: Spot candles of the bot's own venue.
                MarketDataCandleFeed(
                    ports.sync, ports.history, ports.stream, MarketType.SPOT
                ),
            )
            built[venue] = candles
        return candles

    return candles_of
