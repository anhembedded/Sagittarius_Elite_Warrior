"""`EPIC-022E` — draws the armed strategy's own indicator lines and trend
zones on the live chart.

@details `EPIC-021I` §6.2 recorded this as cut, with the reason: *"Không
có cầu nối nào giữa 6 `Strategy` class và hệ `IndicatorScript`"* — the
signal-producing strategies and the chart-drawing indicator scripts were
two unrelated systems. That was true of the `IndicatorScript` route, and
it stayed true; what it missed is that the Backtest screen never used that
route either. It replays the strategy itself and pushes the result
straight at `ChartCard`.

Using the same computation as Backtest is the point, not a convenience:
the same strategy with the same parameters now necessarily draws the same
lines on both screens. Two implementations would drift, and a user
comparing a backtest against live would have no way to tell which chart
was lying to them.

`EPIC-025` PR 4.3m: the throwaway-strategy build, the registry lookup and
the three compute calls all moved inside `modules/strategy`
(`IStrategyChartOverlay.overlay_for()`, `StrategyChartOverlayService`) —
`trading` no longer imports `modules.strategy.ui.strategy_overlay` or
`modules.strategy.application.services.strategy_registry`
(`architecture-rule.md` §3). This Coordinator now only converts the
port's `StrategyOverlay` data into the calls `ChartCard` already
understood.

@par Never reads the running engine
The armed `StrategyEngine` holds the indicator state that decides real
orders. Everything drawn here comes from a separate, throwaway strategy
instance the port replays over the candle buffer — drawing must not be
able to perturb trading.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)

#: `ChartCard.set_script_regions()` key for this screen's trend shading.
#: Its own key, not shared with the fill markers (`EPIC-021K`) — clearing
#: one must never clear the other.
TREND_ZONE_KEY = "trading_strategy_trend_zone"


class StrategyOverlayCoordinator:
    """@brief Keeps the live chart's strategy lines in step with whatever
    is armed."""

    def __init__(
        self,
        get_chart: Callable[[], Any],
        chart_overlay: IStrategyChartOverlay,
    ) -> None:
        self._get_chart = get_chart
        self._chart_overlay = chart_overlay
        self._candles: list[MarketData] = []
        #: Names currently registered on the chart, so a strategy swap
        #: removes exactly what the previous one added — clearing "all
        #: indicators" would also wipe anything another feature drew.
        self._drawn_line_names: list[str] = []
        self._config: LiveStrategyConfig | None = None

    # ------------------------------------------------------------------ #
    # Data in
    # ------------------------------------------------------------------ #

    def set_history(self, candles: Sequence[MarketData]) -> None:
        """Replaces the candle buffer after a history load."""
        self._candles = list(candles)
        self.redraw()

    def on_closed_candle(self, candle: MarketData) -> None:
        """Appends one CLOSED candle and redraws.

        @details Only closed candles. A strategy's indicator readings only
        advance when a bar closes, so redrawing on every in-progress tick
        would spend an O(N) replay per tick to draw a value that has not
        changed, and would briefly show a line position no strategy ever
        computed.
        """
        if self._candles and self._candles[-1].open_time == candle.open_time:
            self._candles[-1] = candle
        else:
            self._candles.append(candle)
        self.redraw()

    # ------------------------------------------------------------------ #
    # Arming
    # ------------------------------------------------------------------ #

    def set_armed_config(self, config: LiveStrategyConfig | None) -> None:
        """Switches to (or clears) the strategy whose lines are drawn."""
        if config == self._config:
            return
        self._clear_lines()
        self._config = config
        self.redraw()

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #

    def redraw(self) -> None:
        chart = self._get_chart()
        if chart is None or self._config is None or not self._candles:
            return

        overlay = self._chart_overlay.overlay_for(self._config, self._candles)
        for line in overlay.lines:
            if line.name not in self._drawn_line_names:
                chart.add_overlay_indicator(line.name, line.colour, int(line.width))
                self._drawn_line_names.append(line.name)
            chart.update_indicator_data(line.name, list(line.x), list(line.y))

        chart.set_script_regions(
            TREND_ZONE_KEY,
            [
                (zone.start, zone.end, zone.colour, zone.opacity)
                for zone in overlay.zones
            ],
        )

    def _clear_lines(self) -> None:
        chart = self._get_chart()
        if chart is None:
            self._drawn_line_names = []
            return
        for name in self._drawn_line_names:
            chart.remove_indicator(name)
        self._drawn_line_names = []
        chart.set_script_regions(TREND_ZONE_KEY, [])
