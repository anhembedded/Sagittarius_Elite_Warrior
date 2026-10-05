"""The Spot candle feed the Bots screen's chart and its kinds' backtests
share (`EPIC-029F`).

Moved out of `BotsPresenter` (the 400-line ceiling, `EPIC-033D`): resolving
market data's three ports and building one `MarketDataCandleFeed` over Spot is
one step of the presenter's construction, with no state of the presenter's
own in it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer


def spot_candle_feed(
    container: IContainer,
) -> tuple[IMarketDataSync, MarketDataCandleFeed]:
    """The sync port and a Spot candle feed over market data's ports; the
    backtests need the sync port on its own as well."""
    sync = container.resolve(IMarketDataSync)
    feed = MarketDataCandleFeed(
        sync,
        container.resolve(IHistoricalKlines),
        container.resolve(IMarketStream),
        MarketType.SPOT,
    )
    return sync, feed
