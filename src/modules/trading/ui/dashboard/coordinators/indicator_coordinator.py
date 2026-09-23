"""`EPIC-003G` — indicator-script fetch sizing and chart dispatch, pulled out
of `DashboardPresenter`. Mirrors `screens/backtest/coordinators/
indicator_coordinator.py`'s shape: a plain class, chart cards reached
through a getter rather than held (a rebuild replaces the dict's values —
see `DashboardPresenter._ensure_chart_cards()`), and everything the
presenter itself can still override on a test double (`_enabled_script_keys`
in particular, monkeypatched throughout `test_dashboard_presenter.py`) stays
a late-bound callback, never copied in at construction time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.runner import (
    IndicatorScriptRunner,
)

# BOT-034 — how many candles to RENDER is not how many to FETCH: 75 is what
# the chart shows by default (see ChartCard._DEFAULT_INITIAL_VISIBLE_CANDLES,
# a separate, zoom-level concept this doesn't replace), but a script's
# slowest indicator may need far more history than that just to produce its
# first point. `compute_fetch_limit()` reconciles the two.
_RENDER_WINDOW_CANDLES: int = 75
#: User-configurable floor (IConfig key), so a fetch is never smaller than
#: this even with nothing enabled that needs more. Defaults to the render
#: window itself — no extra padding unless the user asks for one.
_MIN_FETCH_CANDLES_CONFIG_KEY: str = "CHART_CARD_MIN_FETCH_CANDLES"
_DEFAULT_MIN_FETCH_CANDLES: int = 75


class IndicatorCoordinator:
    """Which chart card a script's data lands on, and how many candles a
    Load History/Start Live fetch needs to warm every enabled script up."""

    def __init__(
        self,
        script_registry: IndicatorScriptRegistry,
        script_runner: IndicatorScriptRunner,
        config,
        get_active_charts: Callable[[], dict],
        get_active_symbol: Callable[[], str],
        get_enabled_script_keys: Callable[[], list[str]],
        get_script_params: Callable[[str], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self._script_registry = script_registry
        self._script_runner = script_runner
        self._config = config
        self._get_active_charts = get_active_charts
        self._get_active_symbol = get_active_symbol
        self._get_enabled_script_keys = get_enabled_script_keys
        #: `BOT-063` — optional: Backtest's own coordinator has no saved
        #: per-script params to look up, so it never passes this and every
        #: script's warm-up requirement is still read off the class,
        #: exactly as before this parameter existed.
        self._get_script_params = get_script_params or (lambda _key: None)

    def _active_card(self):
        return self._get_active_charts().get(self._get_active_symbol())

    def rebuild_scripts(self) -> None:
        card = self._active_card()
        if card is not None:
            self._script_runner.clear_from_chart(card)
        self._script_runner.rebuild(self._get_enabled_script_keys())

    def compute_fetch_limit(self) -> int:
        """
        @details `max(render window, the slowest enabled script's declared
        warm-up requirement, a user-configurable floor)`. Reads
        `get_enabled_script_keys()` fresh on every call (the same "no
        retroactive effect" contract `rebuild_scripts()` has).

        `BOT-063` — instantiates each enabled script with its saved params
        (falling back to every declared default when none are saved,
        exactly like `IndicatorScriptRunner.rebuild()`) rather than reading
        `min_warmup_bars` off the class: a script that overrides
        `self.min_warmup_bars` in `setup()` from a longer-than-default
        period (`ema_20_script.py` et al.) only reports the true, larger
        figure once it is actually built with that period.
        """
        available = self._script_registry.available()
        warmups: list[int] = []
        for key in self._get_enabled_script_keys():
            if key not in available:
                continue
            try:
                script = self._script_registry.create(key, self._get_script_params(key))
            except ValueError:
                # Saved params are validated at Save time
                # (`IndicatorScriptParamsSink`), never re-validated on load;
                # a script's declared bounds tightening in a later release
                # can strand an old value on disk. Falls back to every
                # declared default rather than taking Load History/Start
                # Live down over one script's stale config — the same
                # fallback `IndicatorScriptRunner.rebuild()` uses.
                script = self._script_registry.create(key)
            warmups.append(script.min_warmup_bars)
        slowest = max(warmups, default=0)
        floor = self._config.get(
            _MIN_FETCH_CANDLES_CONFIG_KEY, _DEFAULT_MIN_FETCH_CANDLES, cast=int
        )
        return max(_RENDER_WINDOW_CANDLES, slowest, floor)

    def on_indicator_data(self, name: str, x_data: list, y_data: list) -> None:
        card = self._active_card()
        if card is not None:
            self._script_runner.draw(card, name, x_data, y_data)

    def on_script_region_data(self, key: str, spans: list) -> None:
        card = self._active_card()
        if card is not None:
            self._script_runner.draw_region(card, key, spans)

    def on_script_info_data(self, key: str, fields: list) -> None:
        card = self._active_card()
        if card is not None:
            self._script_runner.draw_info(card, key, fields)

    def on_script_marker_data(self, key: str, markers: list) -> None:
        card = self._active_card()
        if card is not None:
            self._script_runner.draw_markers(card, key, markers)
