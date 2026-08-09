from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from Binace_Bot.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts import BaseIndicatorScript

#: Separates a script's registry key from its line name in a chart curve name
#: ("ema_cross:EMA 12"). Built-in RSI/EMA/MACD curves carry bare names with no
#: separator, so the two systems can never collide — and neither can two
#: scripts that happen to name a line the same thing.
LINE_SEPARATOR = ":"


def qualified_line_name(script_key: str, line_name: str) -> str:
    return f"{script_key}{LINE_SEPARATOR}{line_name}"


def split_line_name(qualified: str) -> tuple[str, str] | None:
    """Reverses qualified_line_name(); None for a built-in indicator's curve."""
    if LINE_SEPARATOR not in qualified:
        return None
    key, _, line = qualified.partition(LINE_SEPARATOR)
    return key, line


@dataclass
class ActiveScript:
    """
    @brief Bookkeeping for one enabled indicator script.
    @details `series` accumulates the full (x, y) history per line, because
    ChartCard.update_indicator_data() always takes the complete series rather
    than appending. `registered_lines` tracks which curves already exist on the
    chart, so a line is added exactly once no matter how many bars arrive.
    """

    script: BaseIndicatorScript
    overlay: bool
    registered_lines: set = field(default_factory=set)
    series: dict[str, tuple[list, list]] = field(default_factory=dict)

    def record(
        self, line_name: str, timestamp: float, value: float
    ) -> tuple[list, list]:
        """Appends one point and returns that line's full (x, y) series."""
        x_data, y_data = self.series.setdefault(line_name, ([], []))
        x_data.append(timestamp)
        y_data.append(value)
        return x_data, y_data


class IndicatorScriptRunner:
    """
    @brief Owns everything about running custom indicator scripts for one
    chart: which are active, feeding them bars, and getting their lines onto
    the chart.

    @details
    Deliberately a separate collaborator rather than more methods on
    DashboardPresenter (SRP): the presenter already coordinates the FSM, the
    stream workflow, the log and the built-in indicators, and this keeps
    script handling in a file that can be worked on without touching that one.

    Knows nothing about Qt threading. It reports computed lines through the
    `emit_line` callback it was constructed with, so the presenter stays the
    only thing that decides what a signal is — which is what lets the same
    runner serve both the background history replay and main-thread live ticks.
    """

    def __init__(
        self,
        registry: IndicatorScriptRegistry,
        emit_line: Callable[[str, list, list], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._registry = registry
        self._emit_line = emit_line
        self._on_error = on_error
        self.active: dict[str, ActiveScript] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def rebuild(self, enabled_keys: Iterable[str]) -> None:
        """
        @brief Replaces the active set with fresh instances of the enabled scripts.
        @details Always new instances — indicators carry warm-up state and have
        no reset(), the same reason the built-in indicators are rebuilt per run.
        Keys are read once, by the caller, so toggling a script mid-run has no
        retroactive effect.
        """
        active: dict[str, ActiveScript] = {}
        for key in enabled_keys:
            try:
                script = self._registry.create(key)
            except KeyError:
                # A stale key (script removed since it was enabled) must not
                # take the whole Load History down.
                self._on_error(f"Unknown indicator script: {key}")
                continue
            active[key] = ActiveScript(script=script, overlay=script.overlay)
        self.active = active

    def clear_from_chart(self, card) -> None:
        """Removes every script-drawn curve before a rebuild."""
        for key, active in self.active.items():
            for line_name in active.registered_lines:
                card.remove_indicator(qualified_line_name(key, line_name))

    # ------------------------------------------------------------------ #
    # Computation — safe to call from either thread (emits, never draws)
    # ------------------------------------------------------------------ #

    def feed(self, candle: MarketData) -> None:
        """Runs one bar through every active script and reports what it plotted."""
        timestamp = float(candle.close_time.timestamp())
        for key, active in self.active.items():
            for line_name, line in active.script.compute(candle).items():
                x_data, y_data = active.record(line_name, timestamp, line.value)
                self._emit_line(qualified_line_name(key, line_name), x_data, y_data)
            # TODO(BOT-032 Phase 4): active.script.drain_markers() carries the
            # Buy/Sell labels a script asked for. ChartCard has no marker API
            # yet — wire it here once add_markers() exists, and coordinate with
            # BOT-026 so there is only one marker implementation.

    def feed_all(self, candles: Iterable[MarketData]) -> None:
        """Replays a whole history. Used by the background load."""
        for candle in candles:
            self.feed(candle)

    # ------------------------------------------------------------------ #
    # Drawing — main thread only
    # ------------------------------------------------------------------ #

    def draw(self, card, qualified: str, x_data: list, y_data: list) -> bool:
        """
        @brief Puts one script line on the chart, adding the curve on first use.
        @returns False if `qualified` isn't a script line (or its script is no
        longer active), so the caller can fall through to its built-in
        indicator handling.
        """
        split = split_line_name(qualified)
        if split is None:
            return False

        key, line_name = split
        active = self.active.get(key)
        if active is None:
            return False

        color = active.script.line_colors().get(line_name)
        if color is None:
            # line_colors() only fills in once a bar has run through the
            # script, so there is genuinely nothing to colour the curve with yet.
            return False

        if line_name not in active.registered_lines:
            if active.overlay:
                card.add_overlay_indicator(qualified, color)
            else:
                card.add_subplot_indicator(qualified, color)
            active.registered_lines.add(line_name)

        card.update_indicator_data(qualified, x_data, y_data)
        return True
