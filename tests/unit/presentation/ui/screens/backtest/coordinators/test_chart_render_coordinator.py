"""`ChartRenderCoordinator` — no presenter, no Qt slots, no thread manager."""

from __future__ import annotations

from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    ChartRenderCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    ChartDisplayMode,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    InMemoryScreenState,
)


class _Card:
    def __init__(self) -> None:
        self.overlays: list[tuple[str, str, int]] = []
        self.data: list[tuple[str, int]] = []
        self.regions: list[tuple[str, int]] = []

    def add_overlay_indicator(self, name, color, width):
        self.overlays.append((name, color, width))

    def update_indicator_data(self, name, x, y):
        self.data.append((name, len(x)))

    def set_script_regions(self, key, spans):
        self.regions.append((key, len(spans)))


class _Controls:
    def __init__(self, ema_checked=True) -> None:
        self.flags_enabled: list[bool] = []
        self.ema_enabled: list[bool] = []
        self._ema_checked = ema_checked

    def set_trade_flags_enabled(self, v):
        self.flags_enabled.append(v)

    def set_ema_enabled(self, v):
        self.ema_enabled.append(v)

    def is_ema_checked(self):
        return self._ema_checked


class _View:
    def __init__(self, card=None, ema_checked=True) -> None:
        self.chart_cards = [card] if card else []
        self.chart_controls = _Controls(ema_checked)
        self.modes: list = []
        self.backtest_data: list = []
        self.preview_data: list = []

    def set_chart_mode(self, mode):
        self.modes.append(mode)

    def on_backtest_data_ready(self, result, klines, volume):
        self.backtest_data.append((len(klines), len(volume)))

    def on_preview_data_ready(self, klines, volume):
        self.preview_data.append((len(klines), len(volume)))


class _ViewModel:
    def __init__(self) -> None:
        self.preview_mode: list[bool] = []
        self.coverage: list[tuple[bool, str]] = []
        self.needs_sync: list[bool] = []
        self.timeRangePreset = "1M"

    def set_chart_preview_mode(self, v):
        self.preview_mode.append(v)

    def set_data_coverage(self, ok, message):
        self.coverage.append((ok, message))

    def set_needs_data_sync(self, v):
        self.needs_sync.append(v)


def _build(*, card=None, ema_checked=True, active_preview_id=1, busy=False):
    view = _View(card, ema_checked)
    view_model = _ViewModel()
    lines: set[str] = set()
    state = InMemoryScreenState(
        symbol="BTCUSDT",
        active_strategy_lines=lines,
        chart_klines_fetch_limit=500,
        active_preview_id=active_preview_id,
    )
    calls = SimpleNamespace(
        verify=0, strategy_visible=[], overlay_visible=[], previews=[]
    )
    coordinator = ChartRenderCoordinator(
        view=view,
        view_model=view_model,
        state=state,
        dispatcher=SimpleNamespace(dispatch=lambda *a: None),
        thread_manager=SimpleNamespace(submit=lambda *a: calls.previews.append(a)),
        logger_=SimpleNamespace(log_klines_loaded=lambda *a: None),
        refresh_market_rule_verification=lambda: setattr(
            calls, "verify", calls.verify + 1
        ),
        log_dev_trace=lambda *a, **k: None,
        format_coverage_message=lambda _c: "thiếu dữ liệu",
        set_strategy_lines_visible=calls.strategy_visible.append,
        set_script_overlay_lines_visible=calls.overlay_visible.append,
        get_current_config=lambda: SimpleNamespace(
            start_time=None, end_time=None, timeframe=SimpleNamespace(value="1m")
        ),
        is_busy=lambda: busy,
        next_preview_id=lambda: 2,
        emit_preview_ready=lambda *a: None,
        run_preview_worker=lambda *a: None,
    )
    return SimpleNamespace(
        c=coordinator, view=view, vm=view_model, lines=lines, calls=calls, state=state
    )


def test_a_strategy_line_is_added_once_then_only_updated() -> None:
    """Adding the overlay twice stacks duplicate curves on the same plot."""
    card = _Card()
    ctx = _build(card=card)

    ctx.c.on_strategy_line("ema20", "#fff", [1, 2], [3, 4])
    ctx.c.on_strategy_line("ema20", "#fff", [1, 2, 3], [3, 4, 5])

    assert card.overlays == [("ema20", "#fff", 2)]
    assert card.data == [("ema20", 2), ("ema20", 3)]


def test_real_run_data_clears_the_preview_badge() -> None:
    """BUG-032: the badge is set by the preview path and only a real result
    takes it down."""
    ctx = _build(card=_Card())

    ctx.c.on_data_ready(SimpleNamespace(trades=[]), [1, 2], [3], raw_klines=[9])

    assert ctx.vm.preview_mode == [False]
    assert ctx.state.current_raw_klines == [9]
    assert ctx.calls.verify == 1


def test_equity_mode_disables_and_hides_both_price_scale_overlays() -> None:
    """Left plotted through Equity-solo mode, a price-scale overlay drags the
    shared plot's auto-range onto price and flattens the equity curve."""
    ctx = _build(card=_Card())

    ctx.c.on_mode_changed(ChartDisplayMode.EQUITY.value)

    assert ctx.view.chart_controls.flags_enabled == [False]
    assert ctx.view.chart_controls.ema_enabled == [False]
    assert ctx.calls.strategy_visible == [False]
    assert ctx.calls.overlay_visible == [False]


def test_price_mode_restores_the_ema_only_if_it_was_checked() -> None:
    ctx = _build(card=_Card(), ema_checked=False)

    ctx.c.on_mode_changed(ChartDisplayMode.OHLC.value)

    assert ctx.calls.strategy_visible == [False]
    assert ctx.calls.overlay_visible == [True]


def test_a_stale_preview_is_dropped_rather_than_drawn() -> None:
    """The generation id is what fences rapid toolbar changes; without the
    check an older, slower query overwrites a newer one."""
    ctx = _build(card=_Card(), active_preview_id=5)

    ctx.c.on_preview_data_ready(
        4, SimpleNamespace(is_fully_covered=True), [1], [2], [3]
    )

    assert ctx.view.preview_data == []
    assert ctx.vm.preview_mode == []


def test_the_current_preview_is_drawn_and_flagged() -> None:
    ctx = _build(card=_Card(), active_preview_id=5)

    ctx.c.on_preview_data_ready(
        5, SimpleNamespace(is_fully_covered=True), [1], [2], [3]
    )

    assert ctx.view.preview_data == [(1, 1)]
    assert ctx.vm.preview_mode == [True]
    assert ctx.vm.needs_sync == [False]


def test_incomplete_coverage_asks_for_a_sync_with_a_reason() -> None:
    ctx = _build(card=_Card(), active_preview_id=5)

    ctx.c.on_preview_data_ready(
        5, SimpleNamespace(is_fully_covered=False), [1], [2], None
    )

    assert ctx.vm.coverage == [(False, "thiếu dữ liệu")]
    assert ctx.vm.needs_sync == [True]


def test_no_preview_is_requested_while_a_run_is_in_flight() -> None:
    """A preview during a run races the run's own writes to the same chart."""
    ctx = _build(card=_Card(), busy=True)

    ctx.c.request_preview()

    assert ctx.calls.previews == []


def test_nothing_is_drawn_before_a_chart_card_exists() -> None:
    ctx = _build(card=None)

    ctx.c.on_strategy_line("ema20", "#fff", [1], [2])
    ctx.c.on_strategy_region([1, 2])

    assert ctx.lines == set()
