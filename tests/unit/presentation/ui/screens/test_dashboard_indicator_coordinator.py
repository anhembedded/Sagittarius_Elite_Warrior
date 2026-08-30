"""`EPIC-003G` — `IndicatorCoordinator`, extracted out of `DashboardPresenter`.

Chart cards and the active symbol are read through the presenter's own
callbacks (not held), the same reasoning `screens/backtest/coordinators/
indicator_coordinator.py`'s docstring gives — the chart-card dict is
reassigned wholesale on a rebuild, so a coordinator holding a stale
reference would silently stop finding the right card.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.coordinators.indicator_coordinator import (
    IndicatorCoordinator,
)


class _FakeScriptClass:
    def __init__(self, min_warmup_bars: int) -> None:
        self.min_warmup_bars = min_warmup_bars


@pytest.fixture
def active_charts() -> dict:
    return {}


@pytest.fixture
def script_registry() -> Mock:
    registry = Mock()
    registry.available.return_value = {
        "ema_ribbon": _FakeScriptClass(min_warmup_bars=200),
        "rsi": _FakeScriptClass(min_warmup_bars=50),
    }
    return registry


@pytest.fixture
def script_runner() -> Mock:
    return Mock()


@pytest.fixture
def coordinator(active_charts, script_registry, script_runner) -> IndicatorCoordinator:
    return IndicatorCoordinator(
        script_registry=script_registry,
        script_runner=script_runner,
        config=Mock(get=lambda key, default=None, cast=None: default),
        get_active_charts=lambda: active_charts,
        get_active_symbol=lambda: "BTCUSDT",
        get_enabled_script_keys=list,
    )


def test_rebuild_scripts_clears_the_active_symbols_chart_then_rebuilds(
    coordinator, active_charts, script_runner
):
    card = MagicMock()
    active_charts["BTCUSDT"] = card

    coordinator.rebuild_scripts()

    script_runner.clear_from_chart.assert_called_once_with(card)
    script_runner.rebuild.assert_called_once_with([])


def test_rebuild_scripts_with_no_active_card_still_rebuilds(coordinator, script_runner):
    """No card for the active symbol yet (screen just opened) — must not
    raise, and must still tell the runner what is enabled."""
    coordinator.rebuild_scripts()

    script_runner.clear_from_chart.assert_not_called()
    script_runner.rebuild.assert_called_once_with([])


def test_compute_fetch_limit_defaults_to_the_render_window_with_nothing_enabled(
    coordinator,
):
    assert coordinator.compute_fetch_limit() == 75


def test_compute_fetch_limit_grows_for_an_enabled_scripts_warmup(
    active_charts, script_registry, script_runner
):
    coordinator = IndicatorCoordinator(
        script_registry=script_registry,
        script_runner=script_runner,
        config=Mock(get=lambda key, default=None, cast=None: default),
        get_active_charts=lambda: active_charts,
        get_active_symbol=lambda: "BTCUSDT",
        get_enabled_script_keys=lambda: ["ema_ribbon"],
    )

    assert coordinator.compute_fetch_limit() == 200


def test_compute_fetch_limit_honors_a_higher_config_floor(
    active_charts, script_registry, script_runner
):
    coordinator = IndicatorCoordinator(
        script_registry=script_registry,
        script_runner=script_runner,
        config=Mock(
            get=lambda key, default=None, cast=None: (
                500 if key == "CHART_CARD_MIN_FETCH_CANDLES" else default
            )
        ),
        get_active_charts=lambda: active_charts,
        get_active_symbol=lambda: "BTCUSDT",
        get_enabled_script_keys=list,
    )

    assert coordinator.compute_fetch_limit() == 500


def test_compute_fetch_limit_ignores_a_config_floor_lower_than_the_render_window(
    active_charts, script_registry, script_runner
):
    coordinator = IndicatorCoordinator(
        script_registry=script_registry,
        script_runner=script_runner,
        config=Mock(
            get=lambda key, default=None, cast=None: (
                10 if key == "CHART_CARD_MIN_FETCH_CANDLES" else default
            )
        ),
        get_active_charts=lambda: active_charts,
        get_active_symbol=lambda: "BTCUSDT",
        get_enabled_script_keys=list,
    )

    assert coordinator.compute_fetch_limit() == 75


def test_on_indicator_data_draws_on_the_active_symbols_card(
    coordinator, active_charts, script_runner
):
    card = MagicMock()
    active_charts["BTCUSDT"] = card

    coordinator.on_indicator_data("EMA(20)", [1.0], [100.0])

    script_runner.draw.assert_called_once_with(card, "EMA(20)", [1.0], [100.0])


def test_on_indicator_data_with_no_active_card_is_a_silent_no_op(
    coordinator, script_runner
):
    coordinator.on_indicator_data("EMA(20)", [1.0], [100.0])

    script_runner.draw.assert_not_called()


def test_on_indicator_data_ignores_a_different_symbols_card(
    coordinator, active_charts, script_runner
):
    """The coordinator is scoped to whatever `get_active_symbol()` returns
    right now — a card under a different key must not receive this data."""
    active_charts["ETHUSDT"] = MagicMock()

    coordinator.on_indicator_data("EMA(20)", [1.0], [100.0])

    script_runner.draw.assert_not_called()


def test_on_script_region_data_draws_on_the_active_symbols_card(
    coordinator, active_charts, script_runner
):
    card = MagicMock()
    active_charts["BTCUSDT"] = card

    coordinator.on_script_region_data("ema_ribbon", [{"start": 0, "end": 1}])

    script_runner.draw_region.assert_called_once_with(
        card, "ema_ribbon", [{"start": 0, "end": 1}]
    )


def test_on_script_info_data_draws_on_the_active_symbols_card(
    coordinator, active_charts, script_runner
):
    card = MagicMock()
    active_charts["BTCUSDT"] = card

    coordinator.on_script_info_data("ema_ribbon", [{"label": "x"}])

    script_runner.draw_info.assert_called_once_with(
        card, "ema_ribbon", [{"label": "x"}]
    )


def test_on_script_marker_data_draws_on_the_active_symbols_card(
    coordinator, active_charts, script_runner
):
    card = MagicMock()
    active_charts["BTCUSDT"] = card

    coordinator.on_script_marker_data("ema_ribbon", [{"x": 1, "y": 2}])

    script_runner.draw_markers.assert_called_once_with(
        card, "ema_ribbon", [{"x": 1, "y": 2}]
    )


def test_get_enabled_script_keys_is_read_late_not_captured(
    active_charts, script_registry, script_runner
):
    """The presenter monkeypatches `_enabled_script_keys` on itself after
    construction throughout `test_dashboard_presenter.py` — the coordinator
    must call the callback fresh each time, never cache its first result."""
    keys = ["rsi"]
    coordinator = IndicatorCoordinator(
        script_registry=script_registry,
        script_runner=script_runner,
        config=Mock(get=lambda key, default=None, cast=None: default),
        get_active_charts=lambda: active_charts,
        get_active_symbol=lambda: "BTCUSDT",
        get_enabled_script_keys=lambda: keys,
    )

    assert coordinator.compute_fetch_limit() == 75  # rsi warmup=50 < window=75

    keys.append("ema_ribbon")

    assert coordinator.compute_fetch_limit() == 200
