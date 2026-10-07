"""`EPIC-028K` — what a desk's chart needs, as one value (`code/quality.md`
§7: more than four related arguments become a parameter object)."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_chart_overlay_reader import (
    IStrategyChartOverlayReader,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@dataclass(frozen=True)
class DeskChartPorts:
    """The market-data ports, the overlay reader and the desk's identity on
    the stream."""

    thread_manager: IThreadManager
    market_data_sync: IMarketDataSync
    historical_klines: IHistoricalKlines
    market_stream: IMarketStream
    overlay: IStrategyChartOverlayReader
    #: The desk's venue's market: what the chart syncs, reads and streams.
    market: MarketType
    #: The desk's own owner on `IMarketStream` (`LiveChartCoordinator`).
    stream_owner: str
    #: The timeframe the chart opens on.
    interval: str
    #: Where the chart tells a failed sync or stream (`BOT-169`).
    notifier: INotifier
    #: The desk's mode, whose message bar shows that failure.
    scope: str
