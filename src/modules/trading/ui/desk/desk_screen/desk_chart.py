"""`EPIC-028K` — a desk's price chart: history, live candles and the armed
strategy's lines, for the desk's own venue's market.

@details The single Trading screen (retired in `EPIC-028M`) drove
`ChartCoordinator` from its presenter; a desk keeps that out of its presenter
so the presenter stays a composition. Three things differ from that screen:
- **its own stream owner** (`stream_owner`): one shared owner made a second
  desk's chart replace the first desk's subscription (the epic review
  of PR 300);
- **its venue's market**: the Futures desk charts Futures candles, so its
  strategy and its order panel see the prices its orders fill at;
- **the last price is published** (`lastPriceChanged`) for the order panel
  and the account tabs, which value orders and holdings with it.

Each of the venue's fills is marked on the chart of its symbol
(`record_fill`, `EPIC-021K` §2.3), kept per symbol so a symbol shown again
shows its fills again; it moved here from the Trading screen in `EPIC-028M`.

Opening a desk reads local history only; `go_live` asks for the stream
(`BUG-107`: opening a screen is not a request to go on the network).
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.chart_coordinator import (
    ChartCoordinator,
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
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

#: The marker layer the venue's fills are drawn on.
FILL_MARKERS_KEY = "live_fills"


class DeskChart(QObject):
    """@brief One desk's `ChartCard`, loaded and kept live."""

    #: The desk symbol's last close (a `Decimal`), after each candle.
    lastPriceChanged = Signal(object)
    #: A line for the desk's log.
    logged = Signal(str)

    _history = Signal(str, list, list, list)
    _candle = Signal(object)

    def __init__(
        self,
        chart: ChartCard,
        ports: DeskChartPorts,
        event_bus: IEventBus,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._chart = chart
        self._symbol = ""
        self._interval = ports.interval
        self._live = False
        self._fills: dict[str, list[MarkerPoint]] = {}
        self._token = CancellationToken()
        self._overlay = StrategyOverlayCoordinator(
            get_chart=lambda: self._chart, chart_overlay=ports.overlay
        )
        self._coordinator = ChartCoordinator(
            thread_manager=ports.thread_manager,
            market_data_sync=ports.market_data_sync,
            historical_klines=ports.historical_klines,
            market_stream=ports.market_stream,
            market=ports.market,
            emit_history_ready=self._history.emit,
            emit_load_finished=lambda: None,
            emit_stream_started=self.logged.emit,
            emit_stream_failed=lambda text: self.logged.emit(f"[ERROR] {text}"),
            emit_log=self.logged.emit,
            stream_owner=ports.stream_owner,
        )
        self._history.connect(self._on_history)
        self._candle.connect(self._on_candle)
        market: MarketType = ports.market
        self._ticks = market_tick_feed(event_bus, lambda: market, self)
        self._ticks.marketTick.connect(self._on_tick)
        chart.toolbar.set_active(self._interval)
        chart.toolbar.sig_timeframe_changed.connect(self._on_timeframe_changed)

    @property
    def shown_symbol(self) -> str:
        return self._symbol

    @property
    def is_live(self) -> bool:
        return self._live

    def show_symbol(self, symbol: str) -> None:
        """Loads `symbol`'s history, live if the desk already went live."""
        if symbol == self._symbol:
            return
        self._symbol = symbol
        self._chart.set_symbol_title(symbol)
        self._draw_fills()
        self._restart()

    def go_live(self) -> None:
        """Asks for the live stream, once (trading enabled on this desk).

        Before a symbol is shown it only marks the chart live, and the first
        `show_symbol` starts live: restarting here would sync and stream the
        empty symbol, a request nobody made (the re-review of PR 308)."""
        if self._live:
            return
        self._live = True
        if self._symbol:
            self._restart()

    def record_fill(self, event: OrderFilledEvent) -> None:
        """Marks one of the venue's fills on its symbol's chart."""
        symbol = event.order.symbol
        self._fills.setdefault(symbol, []).append(order_filled_marker(event))
        if symbol == self._symbol:
            self._draw_fills()

    def set_armed_config(self, config: ArmedStrategyConfig | None) -> None:
        """Draws the armed strategy's own lines over the candles."""
        self._overlay.set_armed_config(config)

    def shutdown(self) -> None:
        """Cancels the load in flight. The stream is left running, as the
        Dev Board leaves its own."""
        self._token.cancel()

    def _restart(self) -> None:
        self._token.cancel()
        self._token = CancellationToken()
        if self._live:
            self._coordinator.stop()
        self._coordinator.start(
            self._symbol, self._interval, self._token, go_live=self._live
        )

    def _draw_fills(self) -> None:
        self._chart.set_script_markers(
            FILL_MARKERS_KEY, self._fills.get(self._symbol, [])
        )

    def _on_timeframe_changed(self, timeframe: str) -> None:
        if timeframe != self._interval:
            self._interval = timeframe
            self._restart()

    def _on_history(
        self, symbol: str, candles: list, volume: list, klines: Sequence[MarketData]
    ) -> None:
        if symbol != self._symbol:
            return
        self._chart.render_historical_data(candles)
        self._chart.render_historical_volume(volume)
        self._overlay.set_history(klines)
        if klines:
            self.lastPriceChanged.emit(Decimal(str(klines[-1].close_price)))

    def _on_tick(self, event: MarketTickEvent) -> None:
        candle = event.market_data
        if candle.symbol == self._symbol and candle.interval == self._interval:
            self._candle.emit(candle)

    def _on_candle(self, candle: MarketData) -> None:
        if candle.symbol != self._symbol:
            return
        t = candle.close_time.timestamp()
        o, h, low, c = (
            float(candle.open_price),
            float(candle.high_price),
            float(candle.low_price),
            float(candle.close_price),
        )
        bullish = c >= o
        if candle.is_closed:
            self._overlay.on_closed_candle(candle)
            self._chart.append_closed_candle(t, o, h, low, c)
            self._chart.append_closed_volume(t, float(candle.volume), bullish)
        else:
            self._chart.update_last_candle(t, o, h, low, c)
            self._chart.update_last_volume(t, float(candle.volume), bullish)
        self.lastPriceChanged.emit(Decimal(str(candle.close_price)))
