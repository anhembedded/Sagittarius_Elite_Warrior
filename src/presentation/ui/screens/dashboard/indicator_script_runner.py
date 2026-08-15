from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    BaseIndicatorScript,
    InfoField,
)
from sagittarius_engine.runtime.tasks import ResourceScope

from .script_region_tracker import RegionSpan, ScriptRegionTracker

#: One marker as forwarded to the chart: (x, y, text, color, direction).
MarkerPoint = tuple[float, float, str, str, str]

#: Separates a script's registry key from its line name in a chart curve name
#: ("ema_cross:EMA 12"). Built-in RSI/EMA/MACD curves carry bare names with no
#: separator, so the two systems can never collide — and neither can two
#: scripts that happen to name a line the same thing.
LINE_SEPARATOR = ":"

#: Used to convert a bar's close timestamp into a span end (see
#: ScriptRegionTracker). "1m" matches DashboardPresenter's _DEFAULT_INTERVAL_STR
#: — if the Dev Board ever supports other intervals, this needs to become a
#: constructor parameter fed from the same place that decides the interval,
#: rather than a second hard-coded assumption of what it is.
_DEFAULT_BAR_WIDTH_SECONDS = 60.0


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
    `region_tracker` and `latest_info` are the same idea applied to a script's
    background tint and status panel (BOT-032) — one timeline / one snapshot
    per script, not per line.
    """

    script: BaseIndicatorScript
    overlay: bool
    region_tracker: ScriptRegionTracker
    registered_lines: set = field(default_factory=set)
    #: BOT-067 — tracks the chart curves this run has added, so clearing them
    #: is a property of this ActiveScript instead of a hand-written loop over
    #: `registered_lines` (the exact mechanism `5a063b5` had to fix by hand).
    scope: ResourceScope = field(default_factory=ResourceScope)
    series: dict[str, tuple[list, list]] = field(default_factory=dict)
    latest_info: list[InfoField] = field(default_factory=list)
    #: Every marker ever produced this run — unlike latest_info (only the most
    #: recent bar's snapshot matters), markers stay on the chart at the bar
    #: they fired on, so this only ever grows.
    markers: list[MarkerPoint] = field(default_factory=list)

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
    chart: which are active, feeding them bars, and getting their lines,
    background tints, and status panel onto the chart.

    @details
    Deliberately a separate collaborator rather than more methods on
    DashboardPresenter (SRP): the presenter already coordinates the FSM, the
    stream workflow, the log and the built-in indicators, and this keeps
    script handling in a file that can be worked on without touching that one.

    Knows nothing about Qt threading. It reports computed output through the
    `emit_*` callbacks it was constructed with, so the presenter stays the
    only thing that decides what a signal is — which is what lets the same
    runner serve both the background history replay and main-thread live ticks.
    """

    def __init__(
        self,
        registry: IndicatorScriptRegistry,
        emit_line: Callable[[str, list, list], None],
        emit_region: Callable[[str, list[RegionSpan]], None],
        emit_info: Callable[[str, list[InfoField]], None],
        emit_markers: Callable[[str, list[MarkerPoint]], None],
        on_error: Callable[[str], None],
        bar_width_seconds: float = _DEFAULT_BAR_WIDTH_SECONDS,
    ) -> None:
        self._registry = registry
        self._emit_line = emit_line
        self._emit_region = emit_region
        self._emit_info = emit_info
        self._emit_markers = emit_markers
        self._on_error = on_error
        self._bar_width_seconds = bar_width_seconds
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
            active[key] = ActiveScript(
                script=script,
                overlay=script.overlay,
                region_tracker=ScriptRegionTracker(self._bar_width_seconds),
            )
        self.active = active

    def clear_from_chart(self, card) -> None:
        """Removes every script-drawn curve, background tint, and status
        panel row before a rebuild. Curve removal goes through each
        ActiveScript's own ResourceScope (BOT-067) rather than this run's
        `card` parameter directly — a curve is always disposed via the exact
        card object it was drawn onto, which is what `dispose_all()` already
        captured at `draw()` time, so a run's curves can never be cleared
        against the wrong (or already-replaced) card. Main thread only, same
        as `draw()` — every `dispose` callable this scope holds ultimately
        calls a `ChartCard`/pyqtgraph method (BOT-068 will add an enforced
        guard for this; today it's this docstring)."""
        for key, active in self.active.items():
            active.scope.dispose_all()
            card.clear_script_regions(key)
            card.clear_script_info(key)
            card.clear_script_markers(key)

    # ------------------------------------------------------------------ #
    # Computation — safe to call from either thread (emits, never draws)
    # ------------------------------------------------------------------ #

    def feed(self, candle: MarketData, *, emit: bool = True) -> None:
        """
        @brief Runs one bar through every active script and reports what it produced.
        @param emit When False, computes and accumulates exactly as normal but stays
        silent — the caller then owes a `_flush()` once it has fed everything. Only
        `feed_all()` passes False; the live-tick path (DashboardPresenter's
        `_on_ui_chart_update`) keeps the default True so a real-time bar still
        reaches the chart the moment it closes.
        """
        timestamp = float(candle.close_time.timestamp())
        for key, active in self.active.items():
            for line_name, line in active.script.compute(candle).items():
                x_data, y_data = active.record(line_name, timestamp, line.value)
                if emit:
                    self._emit_line(qualified_line_name(key, line_name), x_data, y_data)

            active.region_tracker.record(timestamp, active.script.drain_region())
            if emit:
                self._emit_region(key, list(active.region_tracker.spans))

            active.latest_info = active.script.drain_info()
            if emit:
                self._emit_info(key, active.latest_info)

            new_markers = active.script.drain_markers()
            if new_markers:
                active.markers.extend(
                    (
                        timestamp,
                        marker.value,
                        marker.text,
                        marker.color,
                        marker.direction,
                    )
                    for marker in new_markers
                )
                if emit:
                    self._emit_markers(key, list(active.markers))

    def _flush(self, key: str, active: ActiveScript) -> None:
        """
        @brief Emits one snapshot per output channel for a script fed silently
        via `feed(..., emit=False)`.
        @details Mirrors exactly what `feed()` would have emitted on its LAST bar —
        same payload shapes, just once instead of once per bar. A separate method
        (not inlined into `feed_all`) so it can be tested on its own and so
        `feed_all` stays readable.
        """
        for line_name, (x_data, y_data) in active.series.items():
            self._emit_line(qualified_line_name(key, line_name), x_data, y_data)

        self._emit_region(key, list(active.region_tracker.spans))
        self._emit_info(key, active.latest_info)

        # Same guard feed() applies: a script that never produced a marker must
        # not suddenly receive an empty-list emission it never used to get.
        if active.markers:
            self._emit_markers(key, list(active.markers))

    def feed_all(self, candles: Iterable[MarketData]) -> None:
        """
        @brief Replays a whole history.
        @details BOT-036: emits once per output channel at the END instead of once
        per bar. With N bars the old per-bar emit re-sent an ever-growing series
        every single bar (O(N^2) of data crossing the callback boundary); the chart
        only ever needed the final, complete series. `_on_history_prepended` makes
        this especially costly — it replays the whole accumulated history on the
        MAIN thread on every scroll-back, so each emit was a synchronous pyqtgraph
        re-render.
        """
        fed_any = False
        for candle in candles:
            self.feed(candle, emit=False)
            fed_any = True

        if not fed_any:
            return

        for key, active in self.active.items():
            self._flush(key, active)

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
            active.scope.add(
                qualified, dispose=functools.partial(card.remove_indicator, qualified)
            )

        card.update_indicator_data(qualified, x_data, y_data)
        return True

    def draw_region(self, card, key: str, spans: list[RegionSpan]) -> None:
        """
        @brief Puts a script's background tint spans on the chart.
        @details No "is this mine" check like draw() needs: regions and info
        have no built-in-indicator equivalent to fall back to, so the caller
        never has ambiguity about whether this signal was meant for the runner.
        """
        if key not in self.active:
            return
        card.set_script_regions(key, spans)

    def draw_info(self, card, key: str, fields: list[InfoField]) -> None:
        """Puts a script's status-panel rows on the chart."""
        if key not in self.active:
            return
        card.set_script_info(key, fields)

    def draw_markers(self, card, key: str, markers: list[MarkerPoint]) -> None:
        """Puts a script's Buy/Sell-style labelled markers on the chart."""
        if key not in self.active:
            return
        card.set_script_markers(key, markers)
