"""`EPIC-029G` — a bot's own chart: candles, and the bot's overlay drawn over
them (ADR D15, D16; the user, 2026-10-03: "a bot must have its own chart to
draw that bot's own indicators").

@details One class for the three surfaces, each a different source of
candles but the same drawer for the overlay:
- **the planner preview** (`EPIC-029F`): `show_symbol` reads the stored
  history, no network (`BUG-107`);
- **the backtest result** (`EPIC-029D`): `draw_history` draws the candles
  the backtest ran over, and nothing is read or streamed;
- **the running bot** (`EPIC-029E`, `029F`): `show_symbol`, then `follow`
  syncs, streams under the bot's own owner (`bot.<id>`,
  `bot_stream_owner`) and applies the candles of `BotTickFeed`, the bots
  module's one listener to market ticks.

Loading and live candles are `LiveCandleChart`'s, the code a desk's chart
runs; the overlay is drawn by `BotOverlayDrawer`, the one drawer.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_overlay_drawer import (
    BotOverlayDrawer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.overlay_items import (
    OverlayItems,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.empty_chart_notice import (
    EmptyChartNotice,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.price_level_layer import (
    PriceLevelLayer,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartState,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)

#: Room above the highest and below the lowest level, as a fraction of the span.
_FIT_PADDING = 0.05


class BotChart(LiveCandleChart):
    """@brief One bot's `ChartCard`, its candles and its overlay."""

    def __init__(
        self, chart: ChartCard, ports: LiveChartPorts, parent: QObject | None = None
    ) -> None:
        super().__init__(chart, ports, parent)
        self._drawer = BotOverlayDrawer(
            chart, PriceLevelLayer(chart.plot_layout.main_plot)
        )
        self._ticks: BotTickFeed | None = None
        self._overlay = BotOverlay()
        self._notice = EmptyChartNotice(chart)

    def _on_history_drawn(self, klines: Sequence[MarketData]) -> None:
        if klines:
            self._notice.clear()
        else:
            self._notice.show(
                f"No candles are stored for {self.shown_symbol} at "
                f"{self.shown_interval}. Pick another timeframe, or sync this "
                "symbol's history first."
            )

    def show_overlay(self, overlay: BotOverlay) -> OverlayItems:
        """@brief Draws the bot's overlay, replacing the previous one.
        @return The items drawn."""
        self._overlay = overlay
        return self._drawer.draw(overlay)

    def fit_levels(self) -> bool:
        """@brief Scales the price axis to every line and band of the overlay
        (`EPIC-029F`): a level outside the candles' range is otherwise off
        screen (029G). The chart's own reset button returns to following the
        candles. @return `False` when the overlay has nothing to fit."""
        prices = [line.price for line in self._overlay.lines] + [
            edge for band in self._overlay.bands for edge in (band.lower, band.upper)
        ]
        if not prices:
            return False
        self._chart.plot_layout.main_plot.setYRange(
            float(min(prices)), float(max(prices)), padding=_FIT_PADDING
        )
        return True

    def attach_ticks(self, ticks: BotTickFeed) -> None:
        """@brief Listens to `ticks`, so a chart that goes live (the user's
        Go live on a draft, `EPIC-034G` D9, or `follow`) draws what streams.
        Idempotent until the next `shutdown`."""
        if self._ticks is not None:
            return
        self._ticks = ticks
        ticks.candle.connect(self.apply_candle)

    def follow(self, ticks: BotTickFeed) -> None:
        """@brief Goes live, once per `shutdown`: syncs, streams under the
        bot's own owner, and applies the candles `ticks` delivers on the Qt
        thread. Following again before a `shutdown` changes nothing."""
        self.attach_ticks(ticks)
        self.go_live()

    def apply_candle(self, candle: MarketData) -> None:
        """A chart at rest draws no live candle, whoever else streams the
        symbol: its candles are the stored ones until the user goes live."""
        if self.live_state is LiveChartState.HISTORY:
            return
        super().apply_candle(candle)

    def shutdown(self) -> None:
        """@brief Cancels the load in flight, stops applying the Feed's
        candles and releases the bot's stream: a bot's chart is the only
        reader of its own owner's subscription. A later `follow` connects
        once more, so no candle is drawn twice (the PR 321 re-review)."""
        super().shutdown()
        if self._ticks is not None:
            self._ticks.candle.disconnect(self.apply_candle)
            self._ticks = None
        self._go_quiet()
