"""One chart tab of the Market mode (`EPIC-033H`): a symbol's candles, live,
with the indicator scripts the Indicators panel has checked.

The loading and the live candles are `LiveCandleChart`'s, as for a desk's
chart and a bot's (ADR D15). What a Market chart adds is the indicators: an
`IndicatorScriptRunner` of its own, replayed over the history it drew and
fed each closed candle after it. Every call reaches this object on the Qt
thread — the history through `LiveCandleChart`'s signal, a candle through the
presenter's Feed — so the runner draws as it computes.

A chart's own stream owner (`market.<symbol>`) keeps one tab's subscription
from replacing another's (the epic review of PR 300 found that with desks).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.runner import (
    IndicatorScriptRunner,
)

from .market_dependencies import MarketDependencies


def stream_owner_for(symbol: str) -> str:
    """The chart's own owner on `IMarketStream`, one per open symbol."""
    return f"market.{symbol}"


class MarketChart(LiveCandleChart):
    """@brief One open symbol's `ChartCard`, loaded, live, with indicators."""

    def __init__(
        self,
        chart: ChartCard,
        dependencies: MarketDependencies,
        feed: ICandleFeed,
        symbol: str,
        parent: QObject | None = None,
    ) -> None:
        """`feed` is the candles of the market the mode shows (`EPIC-033Q`):
        a chart lives in one market, and a new market is a new chart."""
        super().__init__(
            chart,
            LiveChartPorts(
                thread_manager=dependencies.thread_manager,
                feed=feed,
                stream_owner=stream_owner_for(symbol),
                interval=dependencies.interval,
            ),
            parent,
        )
        self._scripts: IndicatorScriptRegistry = dependencies.scripts
        self._runner = IndicatorScriptRunner(
            registry=dependencies.scripts,
            emit_line=self._draw_line,
            emit_region=lambda key, spans: self._runner.draw_region(chart, key, spans),
            emit_info=lambda key, fields: self._runner.draw_info(chart, key, fields),
            emit_markers=lambda key, points: self._runner.draw_markers(
                chart, key, points
            ),
            on_error=self.logged.emit,
            get_params=dependencies.script_params,
        )
        self._indicators: tuple[str, ...] = ()
        self._klines: list[MarketData] = []

    @property
    def chart(self) -> ChartCard:
        return self._chart

    @property
    def indicators(self) -> tuple[str, ...]:
        """The scripts drawn on this chart, in the order they were checked."""
        return self._indicators

    def show_indicators(self, keys: Iterable[str]) -> None:
        """Draws exactly `keys`, recomputed over the candles already drawn."""
        wanted = tuple(keys)
        if wanted == self._indicators:
            return
        self._indicators = wanted
        self._replay()

    def _on_history_drawn(self, klines: Sequence[MarketData]) -> None:
        self._klines = list(klines)
        self._replay()

    def _on_candle_drawn(self, candle: MarketData) -> None:
        if not candle.is_closed:
            return
        self._klines.append(candle)
        self._runner.feed(candle)

    def _draw_line(self, name: str, x_data: list, y_data: list) -> None:
        self._runner.draw(self._chart, name, x_data, y_data)

    def _replay(self) -> None:
        # Scripts carry warm-up state and have no reset: a new set is new
        # instances, fed the whole history (`IndicatorScriptRunner.rebuild`).
        self._runner.clear_from_chart(self._chart)
        self._runner.rebuild(self._indicators)
        self._runner.feed_all(self._klines)
