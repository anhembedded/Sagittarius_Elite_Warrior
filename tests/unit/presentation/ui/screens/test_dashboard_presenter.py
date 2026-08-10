"""
Tests for DashboardPresenter (BOT-030 Phase 4 — hybrid QML/Widgets).

Key design points this file pins down:
- IThreadManager resolved once in __init__.
- _on_load_history/_on_start_stream submit dedicated background methods to
  the thread manager — no inline closures, no direct dispatch on the main
  thread.
- Indicator toggles/periods are now read from DashboardQmlViewModel
  (presenter._view_model), not from IndicatorControlCard widgets — a real
  DashboardView is used (not a MagicMock) because BasePresenter's FSM/UI
  matrix wiring does `hasattr(view, "control_card")` checks that a
  MagicMock always satisfies (auto-attribute creation), which would
  silently mask the fact that the real DashboardView has no `control_card`
  anymore.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_thread_mgr():
    return MagicMock()


@pytest.fixture
def mock_dispatcher():
    return MagicMock()


@pytest.fixture
def mock_container(mock_thread_mgr, mock_dispatcher):
    container = MagicMock()

    from Binace_Bot.src.application.services.indicator_script_registry import (
        IndicatorScriptRegistry,
    )
    from Binace_Bot.src.domain.indicator_scripts import (
        EmaCrossScript,
        EmaRibbonScript,
    )
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    # A real registry with the real scripts — they are pure state with no
    # I/O, so mocking them would only test the mock (ui_architecture.md S10).
    script_registry = IndicatorScriptRegistry()
    script_registry.register("ema_ribbon", EmaRibbonScript)
    script_registry.register("ema_cross", EmaCrossScript)

    mock_config = MagicMock()
    mock_config.get.return_value = False
    mock_config.get_all.return_value = {}

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IndicatorScriptRegistry:
            return script_registry
        return MagicMock()

    container.resolve.side_effect = resolve_side_effect
    return container


@pytest.fixture
def view(qapp):
    v = DashboardView()
    v.resize(1200, 800)
    v.show()
    qapp.processEvents()
    return v


@pytest.fixture
def presenter(view, mock_container):
    return DashboardPresenter(view, mock_container)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_initialization(presenter, view, mock_container):
    assert presenter.view == view
    assert presenter.container == mock_container
    assert presenter.fsm.current_state.name == "IDLE"


# ---------------------------------------------------------------------------
# _on_load_history — must NOT block the main thread
# ---------------------------------------------------------------------------


def test_on_load_history_submits_background_task(presenter, mock_thread_mgr):
    """_on_load_history submits _run_load_history to thread manager — no direct dispatch."""
    presenter._on_load_history()

    assert mock_thread_mgr.submit.call_count == 1
    submit_args = mock_thread_mgr.submit.call_args[0]

    # First arg must be the dedicated background method, not a closure
    assert submit_args[0] == presenter._run_load_history


def test_on_load_history_does_not_dispatch_on_main_thread(presenter, mock_dispatcher):
    """_on_load_history must NOT call dispatcher directly — that belongs in the background."""
    presenter._on_load_history()
    mock_dispatcher.dispatch.assert_not_called()


def test_run_load_history_dispatches_query_per_symbol(presenter, mock_dispatcher):
    """_run_load_history (background) dispatches one GetHistoricalKlinesQuery per symbol."""
    mock_kline = MagicMock()
    mock_kline.close_time.timestamp.return_value = 1700000000.0
    mock_kline.open_price = 40000
    mock_kline.high_price = 41000
    mock_kline.low_price = 39000
    mock_kline.close_price = 40500
    mock_kline.volume = 12.5

    mock_dispatcher.dispatch.return_value = [mock_kline]

    symbols = ["BTCUSDT", "ETHUSDT"]
    presenter._run_load_history(symbols, "1m", 5000)

    assert mock_dispatcher.dispatch.call_count == 2
    for i, call_args in enumerate(mock_dispatcher.dispatch.call_args_list):
        dispatched_type, dispatched_query = call_args[0]
        assert dispatched_type == GetHistoricalKlinesQuery
        assert dispatched_query.symbol == symbols[i]
        assert dispatched_query.interval == "1m"
        assert dispatched_query.limit == 5000
        assert dispatched_query.order_by_desc is True


def test_run_load_history_handles_exception_per_symbol(presenter, mock_dispatcher):
    """An exception for one symbol must not abort the rest of the load."""
    mock_dispatcher.dispatch.side_effect = [
        Exception("DB error"),
        [MagicMock()],
    ]

    logs = []
    presenter.ui_log_signal.connect(logs.append)

    # Should not raise
    presenter._run_load_history(["BTCUSDT", "ETHUSDT"], "1m", 100)

    assert any("BTCUSDT" in log for log in logs)


# ---------------------------------------------------------------------------
# _on_start_stream — submits full sync+stream workflow to background
# ---------------------------------------------------------------------------


def test_on_start_stream_locks_ui_and_submits_task(presenter, mock_thread_mgr):
    """_on_start_stream must lock FSM and submit _run_sync_and_start."""
    presenter._on_start_stream()

    assert presenter.fsm.current_state.name == "LOCKED"
    assert mock_thread_mgr.submit.call_count == 1

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_sync_and_start


def test_run_sync_and_start_full_workflow(presenter, mock_dispatcher):
    """_run_sync_and_start dispatches Sync → HistoricalKlines → StartLiveStream in order."""
    mock_dispatcher.dispatch.return_value = []

    from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

    presenter._run_sync_and_start(["BTCUSDT"], TimeFrame("1m"), "1m", 5000)

    call_types = [args[0][0] for args in mock_dispatcher.dispatch.call_args_list]
    assert SyncMarketDataCommand in call_types
    assert GetHistoricalKlinesQuery in call_types
    assert StartLiveStreamCommand in call_types

    # Order matters: Sync first, then Query, then Stream
    sync_idx = call_types.index(SyncMarketDataCommand)
    query_idx = call_types.index(GetHistoricalKlinesQuery)
    stream_idx = call_types.index(StartLiveStreamCommand)
    assert sync_idx < query_idx < stream_idx


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------


def test_on_load_history_exception_is_caught_by_safe_ui_action(presenter):
    """@safe_ui_action catches exceptions from _ensure_chart_cards without crashing."""
    presenter._ensure_chart_cards = MagicMock(side_effect=ValueError("Test Exception"))

    logs = []
    presenter.ui_log_signal.connect(logs.append)

    presenter._on_load_history()

    assert any(
        "Test Exception" in log or "_on_load_history failed" in log for log in logs
    )


# ---------------------------------------------------------------------------
# Indicator control — reads DashboardQmlViewModel's rsi/ema/macd properties,
# computes via BOT-020's RSI/EMA/MACD, and pushes series onto the chart.
# ---------------------------------------------------------------------------


def _make_kline(timestamp: float, close_price: float) -> MagicMock:
    kline = MagicMock()
    kline.close_time.timestamp.return_value = timestamp
    kline.close_price = close_price
    return kline


def test_build_active_indicators_returns_empty_dict_when_none_checked(presenter):
    """The view model's toggles default to unchecked — no indicators built."""
    assert presenter._build_active_indicators() == {}


def test_build_active_indicators_builds_enabled_indicators_with_configured_periods(
    presenter,
):
    presenter._view_model.rsiEnabled = True
    presenter._view_model.rsiPeriod = 21
    presenter._view_model.macdEnabled = True

    indicators = presenter._build_active_indicators()

    assert set(indicators.keys()) == {"RSI(21)", "MACD"}
    assert indicators["RSI(21)"].kind == "subplot"
    assert indicators["MACD"].kind == "subplot"


def test_on_load_history_builds_active_indicators_from_current_view_model_state(
    presenter,
):
    presenter._view_model.emaEnabled = True
    presenter._view_model.emaPeriod = 50

    presenter._on_load_history()

    assert "EMA(50)" in presenter.active_indicators
    assert presenter.active_indicators["EMA(50)"].kind == "overlay"


def test_compute_indicator_series_emits_signal_once_warmed_up(presenter):
    """A short RSI period warms up quickly — the emitted series must be
    non-empty and shorter than the input (None outputs during warm-up are
    dropped, matching IIndicator's own warm-up contract from BOT-020)."""
    presenter._view_model.rsiEnabled = True
    presenter._view_model.rsiPeriod = 2
    presenter.active_indicators = presenter._build_active_indicators()

    emitted = []
    presenter.ui_indicator_data_signal.connect(
        lambda name, x, y: emitted.append((name, x, y))
    )

    klines = [_make_kline(1000.0 + i, 100.0 + i) for i in range(5)]
    presenter._compute_indicator_series(klines)

    assert len(emitted) == 1
    name, x_data, y_data = emitted[0]
    assert name == "RSI(2)"
    assert len(x_data) == len(y_data) > 0
    assert len(y_data) < len(klines)  # fewer points than input (warm-up dropped)


def test_on_indicator_data_registers_overlay_once_then_only_updates(presenter):
    """First call registers the overlay curve; subsequent calls must not
    re-register it (would create duplicate curves on the real chart)."""
    from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
        _ActiveIndicator,
    )

    active_indicator = _ActiveIndicator(
        indicator=MagicMock(), extract_value=lambda v: v, kind="overlay", color="#fff"
    )
    presenter.active_indicators = {"EMA(20)": active_indicator}
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}

    presenter._on_indicator_data("EMA(20)", [1.0], [100.0])
    presenter._on_indicator_data("EMA(20)", [1.0, 2.0], [100.0, 101.0])

    mock_card.add_overlay_indicator.assert_called_once_with("EMA(20)", "#fff")
    assert mock_card.update_indicator_data.call_count == 2
    mock_card.update_indicator_data.assert_called_with(
        "EMA(20)", [1.0, 2.0], [100.0, 101.0]
    )


def test_update_indicators_on_closed_candle_appends_and_pushes_to_chart(presenter):
    """A live closed candle must append to the running series (not replace
    it) and push the full accumulated series to the chart."""
    from Binace_Bot.src.domain.indicators.ema import EMA
    from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
        _ActiveIndicator,
    )

    # period=1 warms up on the very first update() call.
    active_indicator = _ActiveIndicator(
        indicator=EMA(period=1),
        extract_value=lambda v: v,
        kind="overlay",
        color="#e67e22",
        x_data=[1000.0],
        y_data=[100.0],
    )
    presenter.active_indicators = {"EMA(1)": active_indicator}
    mock_card = MagicMock()

    presenter._update_indicators_on_closed_candle(mock_card, 1060.0, 105.0)

    assert active_indicator.x_data == [1000.0, 1060.0]
    assert active_indicator.y_data == [100.0, 105.0]
    mock_card.add_overlay_indicator.assert_called_once_with("EMA(1)", "#e67e22")
    mock_card.update_indicator_data.assert_called_once_with(
        "EMA(1)", [1000.0, 1060.0], [100.0, 105.0]
    )


# ---------------------------------------------------------------------------
# ViewModel bridging — top bar / WS badge / log panel
# ---------------------------------------------------------------------------


def test_price_ticker_updates_on_chart_tick(presenter):
    presenter.active_charts = {"ETHUSDT": MagicMock()}

    presenter._on_ui_chart_update("ETHUSDT", 1.0, 100.0, 101.0, 99.0, 100.5, 5.0, True)

    assert "ETHUSDT" in presenter._view_model.priceTickerText
    assert "100.50" in presenter._view_model.priceTickerText


def test_ws_status_badge_reflects_fsm_state(presenter):
    from Binace_Bot.src.presentation.ui.constants import UIMode

    presenter.fsm.transition_to(UIMode.LOCKED)

    assert presenter._view_model.wsStatusText == "WS: SYNCING"


# ---------------------------------------------------------------------------
# Custom indicator scripts (BOT-032) — presenter side only.
# The runner's own behaviour is covered in test_indicator_script_runner.py.
# ---------------------------------------------------------------------------


def _make_market_data(close: float, index: int):
    """A real MarketData — scripts take the whole candle, so a MagicMock would
    not exercise the real path."""
    from datetime import UTC, datetime, timedelta

    from Binace_Bot.src.domain.entities.market_data import MarketData

    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=open_time,
        open_price=close,
        high_price=close + 1,
        low_price=close - 1,
        close_price=close,
        volume=10.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
    )


def test_presenter_owns_a_script_runner_wired_to_its_signals(presenter):
    assert presenter._script_runner is not None
    # Emitting through the runner's callback must reach the presenter's signal,
    # which is what keeps script output on the existing thread-safe path.
    emitted = []
    presenter.ui_indicator_data_signal.connect(lambda name, x, y: emitted.append(name))
    presenter._script_runner._emit_line("ema_ribbon:EMA 20", [1.0], [2.0])

    assert emitted == ["ema_ribbon:EMA 20"]


def test_no_scripts_run_until_the_ui_enables_one(presenter):
    """Registering a script must not silently draw it — the user opts in."""
    presenter._rebuild_scripts()

    assert presenter._script_runner.active == {}


def test_script_lines_are_routed_to_the_runner_not_the_builtin_path(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]
    presenter._rebuild_scripts()
    active = presenter._script_runner.active["ema_ribbon"]
    # line_colors() only fills in after a bar has run through the script.
    active.script.compute(_make_market_data(100.0, 0))

    presenter._on_indicator_data("ema_ribbon:EMA 20", [1.0], [100.0])

    mock_card.add_overlay_indicator.assert_called_once_with(
        "ema_ribbon:EMA 20", "#e74c3c"
    )


def test_built_in_indicator_curves_still_route_the_old_way(presenter):
    """The `:` separator is the only thing distinguishing the two systems —
    a bare name must never be mistaken for a script line."""
    from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
        _ActiveIndicator,
    )

    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter.active_indicators = {
        "EMA(20)": _ActiveIndicator(
            indicator=MagicMock(),
            extract_value=lambda v: v,
            kind="overlay",
            color="#fff",
        )
    }

    presenter._on_indicator_data("EMA(20)", [1.0], [100.0])

    mock_card.add_overlay_indicator.assert_called_once_with("EMA(20)", "#fff")
