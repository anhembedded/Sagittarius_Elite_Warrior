"""`EPIC-022E` — draws the armed strategy's own indicator lines and trend
zones on the live chart.

@details `EPIC-021I` §6.2 recorded this as cut, with the reason: *"Không
có cầu nối nào giữa 6 `Strategy` class và hệ `IndicatorScript`"* — the
signal-producing strategies and the chart-drawing indicator scripts were
two unrelated systems. That was true of the `IndicatorScript` route, and
it stayed true; what it missed is that the Backtest screen never used that
route either. It replays the strategy itself
(`compute_strategy_indicator_lines`/`compute_strategy_trend_zones`) and
pushes the result straight at `ChartCard`. `EPIC-022C` moved those two
functions into `components/strategy_overlay/`, so the bridge that had to
be "a new subsystem" is now an import.

Using the *same* two functions as Backtest is the point, not a
convenience: the same strategy with the same parameters now necessarily
draws the same lines on both screens. Two implementations would drift, and
a user comparing a backtest against live would have no way to tell which
chart was lying to them.

@par Never reads the running engine
The armed `StrategyEngine` holds the indicator state that decides real
orders. Everything drawn here comes from a separate, throwaway strategy
instance replayed over the candle buffer — the same discipline
`IndicatorCoordinator._throwaway_strategy` follows on the Backtest side.
Drawing must not be able to perturb trading.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.ui.strategy_overlay import (
    assign_strategy_line_colors,
    compute_strategy_indicator_lines,
    compute_strategy_trend_zones,
)

logger = logging.getLogger("App.TradingStrategyOverlay")

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
        available_strategies: Callable[[], Mapping[str, type]],
    ) -> None:
        self._get_chart = get_chart
        self._available_strategies = available_strategies
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
        advance when a bar closes — `StrategyEngine.on_tick()` accepts
        nothing else — so redrawing on every in-progress tick would spend
        an O(N) replay per tick to draw a value that has not changed, and
        would briefly show a line position no strategy ever computed.
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
        if chart is None:
            return
        strategy = self._build_throwaway_strategy()
        if strategy is None or not self._candles:
            return

        lines = compute_strategy_indicator_lines(strategy, self._candles)
        colors = assign_strategy_line_colors(list(lines), strategy.chart_line_colors())
        widths = strategy.chart_line_widths()
        for name, (x_data, y_data) in lines.items():
            if name not in self._drawn_line_names:
                chart.add_overlay_indicator(
                    name, colors.get(name, ""), int(widths.get(name, 2))
                )
                self._drawn_line_names.append(name)
            chart.update_indicator_data(name, x_data, y_data)

        chart.set_script_regions(
            TREND_ZONE_KEY, compute_strategy_trend_zones(strategy, self._candles)
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

    def _build_throwaway_strategy(self):
        """@returns A fresh instance of the armed strategy, or `None`.

        @details Rebuilt on every redraw rather than kept: these replay
        functions feed indicators bar by bar from scratch, so a retained
        instance would carry the previous redraw's state into the next one
        and produce readings for candles it had already consumed.
        """
        if self._config is None:
            return None
        strategy_cls = self._available_strategies().get(self._config.strategy_key)
        if strategy_cls is None:
            return None
        try:
            return strategy_cls(dict(self._config.strategy_params))
        except ValueError:
            # The armed config was validated by `ArmStrategyCommand`
            # before it ever got here, so this is close to unreachable —
            # but a drawing failure must never take the trading screen
            # down with it.
            logger.warning(
                "Could not build a strategy copy '%s' to draw the chart.",
                self._config.strategy_key,
            )
            return None
