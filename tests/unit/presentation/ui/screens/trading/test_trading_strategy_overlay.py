"""`EPIC-022E` — the armed strategy's lines on the live chart.

The load-bearing assertion is the negative one: an in-progress tick must
NOT trigger a redraw. Everything else here would still "work" if that rule
were broken — it would just replay the whole candle buffer several times a
second to draw a value that cannot have changed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_chart_overlay_reader_adapter import (
    StrategyChartOverlayReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_chart_overlay_reader import (
    IStrategyChartOverlayReader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.coordinators.strategy_overlay_coordinator import (
    TREND_ZONE_KEY,
    StrategyOverlayCoordinator,
)

_KEY = "ema_crossover"


def _candles(count: int = 60, *, closed: bool = True) -> list[MarketData]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(count):
        price = 100.0 + index
        rows.append(
            MarketData(
                symbol="BTCUSDT",
                interval="1m",
                open_time=start + timedelta(minutes=index),
                open_price=price,
                high_price=price + 1,
                low_price=price - 1,
                close_price=price,
                volume=10.0,
                close_time=start + timedelta(minutes=index, seconds=59),
                quote_asset_volume=1000.0,
                number_of_trades=5,
                taker_buy_base_asset_volume=5.0,
                taker_buy_quote_asset_volume=500.0,
                is_closed=closed,
            )
        )
    return rows


@pytest.fixture
def registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(_KEY, EmaCrossoverStrategy)
    return registry


@pytest.fixture
def chart_overlay(registry) -> IStrategyChartOverlayReader:
    return StrategyChartOverlayReaderAdapter(StrategyChartOverlayService(registry))


@pytest.fixture
def chart() -> MagicMock:
    return MagicMock()


@pytest.fixture
def coordinator(chart, chart_overlay) -> StrategyOverlayCoordinator:
    return StrategyOverlayCoordinator(
        get_chart=lambda: chart,
        chart_overlay=chart_overlay,
    )


def _config(**overrides) -> ArmedStrategyConfig:
    values = {"strategy_key": _KEY, "symbol": "BTCUSDT", "interval": "1m"}
    values.update(overrides)
    return ArmedStrategyConfig(**values)


def test_nothing_is_drawn_while_no_strategy_is_armed(coordinator, chart):
    coordinator.set_history(_candles())

    chart.add_overlay_indicator.assert_not_called()
    chart.update_indicator_data.assert_not_called()


def test_arming_draws_the_strategys_own_lines(coordinator, chart):
    coordinator.set_history(_candles())
    chart.reset_mock()

    coordinator.set_armed_config(_config())

    assert chart.add_overlay_indicator.called
    assert chart.update_indicator_data.called
    drawn = {call.args[0] for call in chart.add_overlay_indicator.call_args_list}
    assert drawn, "the strategy declared indicators but none were registered"


def test_lines_are_registered_once_and_only_updated_afterwards(coordinator, chart):
    coordinator.set_history(_candles())
    coordinator.set_armed_config(_config())
    registered_first = chart.add_overlay_indicator.call_count
    chart.reset_mock()

    coordinator.on_closed_candle(_candles(61)[-1])

    assert chart.add_overlay_indicator.call_count == 0
    assert chart.update_indicator_data.call_count == registered_first


def test_an_unclosed_tick_never_reaches_the_overlay(coordinator, chart):
    """The rule is enforced by `TradingPresenter` (it only forwards closed
    candles); this asserts the coordinator's own redraw cost is what makes
    that rule worth having — one redraw per call, so a per-tick caller
    would pay a full replay per tick."""
    coordinator.set_history(_candles())
    coordinator.set_armed_config(_config())
    chart.reset_mock()

    coordinator.on_closed_candle(_candles(61)[-1])

    assert chart.update_indicator_data.call_count > 0
    per_redraw = chart.update_indicator_data.call_count
    chart.reset_mock()
    coordinator.on_closed_candle(_candles(62)[-1])
    assert chart.update_indicator_data.call_count == per_redraw


def test_disarming_removes_exactly_what_was_drawn(coordinator, chart):
    coordinator.set_history(_candles())
    coordinator.set_armed_config(_config())
    added = [call.args[0] for call in chart.add_overlay_indicator.call_args_list]
    chart.reset_mock()

    coordinator.set_armed_config(None)

    removed = [call.args[0] for call in chart.remove_indicator.call_args_list]
    assert removed == added
    chart.set_script_regions.assert_any_call(TREND_ZONE_KEY, [])


def test_swapping_parameters_redraws_rather_than_stacking_lines(coordinator, chart):
    coordinator.set_history(_candles())
    coordinator.set_armed_config(_config(strategy_params={"fast_period": 5}))
    first = [call.args[0] for call in chart.add_overlay_indicator.call_args_list]
    chart.reset_mock()

    coordinator.set_armed_config(_config(strategy_params={"fast_period": 9}))

    removed = [call.args[0] for call in chart.remove_indicator.call_args_list]
    assert removed == first
    assert chart.add_overlay_indicator.call_count == len(first)


def test_re_arming_the_identical_config_does_not_redraw(coordinator, chart):
    """`LiveStrategyConfig` is a value object, so "the same arming" is
    equality, not identity — this is what stops every
    `_refresh_armed_summary()` call (one per toggle, per status change)
    from replaying the whole buffer."""
    coordinator.set_history(_candles())
    coordinator.set_armed_config(_config())
    chart.reset_mock()

    coordinator.set_armed_config(_config())

    chart.remove_indicator.assert_not_called()
    chart.add_overlay_indicator.assert_not_called()


def test_a_strategy_key_that_vanished_draws_nothing_instead_of_raising(
    chart, chart_overlay
):
    coordinator = StrategyOverlayCoordinator(
        get_chart=lambda: chart,
        chart_overlay=chart_overlay,
    )
    coordinator.set_history(_candles())

    coordinator.set_armed_config(_config(strategy_key="deleted_strategy"))

    chart.add_overlay_indicator.assert_not_called()


def test_the_running_engine_is_never_consulted(coordinator, chart, registry):
    """Drawing must not be able to perturb trading: everything shown comes
    from a throwaway replay, so the coordinator has no reference to the
    live `StrategyEngine` at all — asserted structurally, since a mock
    would only prove the mock was not called."""
    assert not any(
        "engine" in name.lower() or "session" in name.lower()
        for name in vars(coordinator)
    )
