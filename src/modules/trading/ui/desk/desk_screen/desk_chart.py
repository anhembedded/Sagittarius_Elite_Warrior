"""`EPIC-028K` — a desk's price chart: history, live candles and the armed
strategy's lines, for the desk's own venue's market.

@details The loading and the live candles are `LiveCandleChart`'s, shared
with a bot's chart (`EPIC-029G`). What a desk adds:
- **its own stream owner** (`stream_owner`): one shared owner made a second
  desk's chart replace the first desk's subscription (the epic review
  of PR 300);
- **its venue's market**: the Futures desk charts Futures candles, so its
  strategy and its order panel see the prices its orders fill at;
- **the last price is published** (`lastPriceChanged`) for the order panel
  and the account tabs, which value orders and holdings with it;
- **the armed strategy's lines** (`StrategyOverlayCoordinator`), replayed
  over the history and advanced on each closed candle.

Each of the venue's fills is marked on the chart of its symbol
(`record_fill`, `EPIC-021K` §2.3), kept per symbol so a symbol shown again
shows its fills again; it moved here from the Trading screen in `EPIC-028M`.

Ticks come from market_data's `MarketTickFeed`, through the one crossing
`market_ticks.py` keeps, filtered to the desk's market.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart_ports import (
    DeskChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.strategy_overlay_coordinator import (
    StrategyOverlayCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market_ticks import (
    market_tick_feed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_fill_marker import (
    order_filled_marker,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.marker_layer import (
    MarkerPoint,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

#: The marker layer the venue's fills are drawn on.
FILL_MARKERS_KEY = "live_fills"


class DeskChart(LiveCandleChart):
    """@brief One desk's `ChartCard`, loaded and kept live."""

    #: The desk symbol's last close (a `Decimal`), after each candle.
    lastPriceChanged = Signal(object)

    _candle = Signal(object)

    def __init__(
        self,
        chart: ChartCard,
        ports: DeskChartPorts,
        event_bus: IEventBus,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            chart,
            LiveChartPorts(
                thread_manager=ports.thread_manager,
                feed=MarketDataCandleFeed(
                    ports.market_data_sync,
                    ports.historical_klines,
                    ports.market_stream,
                    ports.market,
                ),
                stream_owner=ports.stream_owner,
                interval=ports.interval,
            ),
            parent,
        )
        self._fills: dict[str, list[MarkerPoint]] = {}
        self._overlay = StrategyOverlayCoordinator(
            get_chart=lambda: self._chart, chart_overlay=ports.overlay
        )
        self._candle.connect(self.apply_candle)
        market: MarketType = ports.market
        self._ticks = market_tick_feed(event_bus, lambda: market, self)
        self._ticks.marketTick.connect(self._on_tick)

    def record_fill(self, event: OrderFilledEvent) -> None:
        """Marks one of the venue's fills on its symbol's chart."""
        symbol = event.order.symbol
        self._fills.setdefault(symbol, []).append(order_filled_marker(event))
        if symbol == self._symbol:
            self._draw_fills()

    def set_armed_config(self, config: ArmedStrategyConfig | None) -> None:
        """Draws the armed strategy's own lines over the candles."""
        self._overlay.set_armed_config(config)

    def _on_symbol_shown(self, symbol: str) -> None:
        self._draw_fills()

    def _on_history_drawn(self, klines: Sequence[MarketData]) -> None:
        self._overlay.set_history(klines)
        if klines:
            self.lastPriceChanged.emit(Decimal(str(klines[-1].close_price)))

    def _on_candle_drawn(self, candle: MarketData) -> None:
        if candle.is_closed:
            self._overlay.on_closed_candle(candle)
        self.lastPriceChanged.emit(Decimal(str(candle.close_price)))

    def _draw_fills(self) -> None:
        self._chart.set_script_markers(
            FILL_MARKERS_KEY, self._fills.get(self._symbol, [])
        )

    def _on_tick(self, event: MarketTickEvent) -> None:
        candle = event.market_data
        if candle.symbol == self._symbol and candle.interval == self._interval:
            self._candle.emit(candle)
