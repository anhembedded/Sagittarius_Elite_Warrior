"""`BUG-183`: the Trade desks' charts find candles in the booted app, so none
raises a "no candles" message bar when its worker finishes.

A desk reads `IMarketDataSources.ports_for(its venue)`. While only the
default-venue ports were substituted, every desk read an empty store, asked a
sync that fetched nothing, and told so in a bar: up to four, 43 px each, in a
number that depended on which workers had finished, which is the height
`test_workbench_conformance` measures (`trade@1024x700/fits_the_window` failed
at 701 px on one run in CI and passed on the next).
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    SEEDED_SYMBOLS,
)


@pytest.mark.parametrize("market", [MarketType.SPOT, MarketType.FUTURES_USD_M])
@pytest.mark.parametrize("venue", list(MarketDataVenue))
def test_a_venues_ports_hold_the_seeded_candles(
    app_engine, venue: MarketDataVenue, market: MarketType
) -> None:
    sources = app_engine.context.container.resolve(IMarketDataSources)

    candles = sources.ports_for(venue).history.load(
        market, SEEDED_SYMBOLS[1], TimeFrame.ONE_MINUTE, limit=1
    )

    assert candles, f"{venue.value} / {market.value} reads an empty store"
