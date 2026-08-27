"""`ChartRenderCoordinator` — no presenter, no Qt slots, no thread manager.

The toolbar preview moved to `test_chart_preview_coordinator.py` with the
coordinator itself (`EPIC-013D`); the fake View/card/ViewModel they both use
live in `conftest.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    ChartRenderCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    ChartDisplayMode,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    FakeBacktestView,
    FakeChartCard,
    FakeChartViewModel,
    InMemoryScreenState,
)


def _build(*, card=None, ema_checked=True):
    """Returns the coordinator plus everything a test asserts against."""
    view = FakeBacktestView(card, ema_checked)
    view_model = FakeChartViewModel()
    lines: set[str] = set()
    state = InMemoryScreenState(symbol="BTCUSDT", active_strategy_lines=lines)
    calls = SimpleNamespace(verify=0, strategy_visible=[], overlay_visible=[])
    coordinator = ChartRenderCoordinator(
        view=view,
        state=state,
        view_model=view_model,
        logger_=SimpleNamespace(log_klines_loaded=lambda *a: None),
        refresh_market_rule_verification=lambda: setattr(
            calls, "verify", calls.verify + 1
        ),
        log_dev_trace=lambda *a, **k: None,
        set_strategy_lines_visible=calls.strategy_visible.append,
        set_script_overlay_lines_visible=calls.overlay_visible.append,
    )
    return SimpleNamespace(
        c=coordinator, view=view, vm=view_model, lines=lines, calls=calls, state=state
    )


def test_a_strategy_line_is_added_once_then_only_updated() -> None:
    """Adding the overlay twice stacks duplicate curves on the same plot."""
    card = FakeChartCard()
    ctx = _build(card=card)

    ctx.c.on_strategy_line("ema20", "#fff", [1, 2], [3, 4])
    ctx.c.on_strategy_line("ema20", "#fff", [1, 2, 3], [3, 4, 5])

    assert card.overlays == [("ema20", "#fff", 2)]
    assert card.data == [("ema20", 2), ("ema20", 3)]


def test_real_run_data_clears_the_preview_badge() -> None:
    """BUG-032: the badge is set by the preview path and only a real result
    takes it down."""
    ctx = _build(card=FakeChartCard())

    ctx.c.on_data_ready(SimpleNamespace(trades=[]), [1, 2], [3], raw_klines=[9])

    assert ctx.vm.preview_mode == [False]
    assert ctx.state.current_raw_klines == [9]
    assert ctx.calls.verify == 1


def test_equity_mode_disables_and_hides_both_price_scale_overlays() -> None:
    """Left plotted through Equity-solo mode, a price-scale overlay drags the
    shared plot's auto-range onto price and flattens the equity curve."""
    ctx = _build(card=FakeChartCard())

    ctx.c.on_mode_changed(ChartDisplayMode.EQUITY.value)

    assert ctx.view.chart_controls.flags_enabled == [False]
    assert ctx.view.chart_controls.ema_enabled == [False]
    assert ctx.calls.strategy_visible == [False]
    assert ctx.calls.overlay_visible == [False]


def test_price_mode_restores_the_ema_only_if_it_was_checked() -> None:
    ctx = _build(card=FakeChartCard(), ema_checked=False)

    ctx.c.on_mode_changed(ChartDisplayMode.OHLC.value)

    assert ctx.calls.strategy_visible == [False]
    assert ctx.calls.overlay_visible == [True]


def test_nothing_is_drawn_before_a_chart_card_exists() -> None:
    ctx = _build(card=None)

    ctx.c.on_strategy_line("ema20", "#fff", [1], [2])
    ctx.c.on_strategy_region([1, 2])

    assert ctx.lines == set()
