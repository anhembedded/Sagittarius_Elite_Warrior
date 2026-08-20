"""
Tests for the Backtest Screen's presenter (BOT-022).

Threading contract mirrors DataManagementPresenter/DashboardPresenter:
- IThreadManager is resolved once in __init__.
- Background work is submitted as `self._run_backtest(config)` via
  thread_manager.submit — NOT as an inline closure.
- `_run_backtest` itself is called directly (as the thread pool would call
  it) to test the background path without spinning a real thread; because
  sender and receiver share a thread in these tests, the `_backtest*Signal`s
  it emits execute their connected slots synchronously, so the resulting
  view-model/FSM state can be asserted immediately after the call returns.

Uses a REAL StrategyRegistry (with one fake strategy registered) and a REAL
BackTestViewModel — both are plain state/config holders with no I/O — mocking
only the genuine external dependencies (IDispatcher, IThreadManager, IConfig).
"""

import logging
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_realtime_backtest.command import (
    RunRealtimeBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    BacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.query import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    LotSizeFilter,
    MetadataVerificationStatus,
    NotionalFilter,
    PriceFilter,
    SymbolMarketMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_type_renderer import (
    CANDLESTICK,
    LINE,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    _FALLBACK_SYMBOL,
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
    PythonBacktestChartHost,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestActionKind,
    BacktestActionOutcome,
    BacktestExecutionMode,
    BacktestRunConfig,
    BacktestUiEvent,
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    ChartDisplayMode,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


class _FakeStrategy(BaseStrategy):
    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


class _EmaIndicatorStrategy(BaseStrategy):
    """A strategy that actually declares indicators (BOT-060) — unlike
    `_FakeStrategy`, whose empty `build_indicators()` is deliberate so it
    doesn't perturb tests that don't care about chart overlays."""

    def build_indicators(self):
        return {"ema_fast": EMA(1), "ema_slow": EMA(1)}

    def decide(self, context):
        return self.hold()


class _TestReferenceScript(BaseIndicatorScript):
    """A minimal real indicator script (BOT-064) — `default_enabled = True`
    so `IndicatorScriptListModel.set_available()` auto-enables it the same
    way `Ema20Script`'s shipped default does, no manual toggle needed."""

    title = "Test Reference Script"
    overlay = True
    default_enabled = True

    def setup(self) -> None:
        self.a = self.ema(1)

    def execute(self, candle):
        self.plot(self.a(candle.close_price), "R", color="#8e44ad")


class _TestSubplotScript(BaseIndicatorScript):
    """BOT-065: a subplot script (RSI/MACD-shaped, `overlay = False`) —
    doesn't share the main plot's price-scale axis, so it must stay
    visible through Equity-solo mode, unlike `_TestReferenceScript`."""

    title = "Test Subplot Script"
    overlay = False
    default_enabled = True

    def setup(self) -> None:
        self.a = self.ema(1)

    def execute(self, candle):
        self.plot(self.a(candle.close_price), "S", color="#2980b9")


class _RichParamsStrategy(BaseStrategy):
    """Declares a couple of parameters (BOT-047) — kept out of the shared
    `strategy_registry` fixture so it doesn't perturb `strategyOptions`-
    related assertions elsewhere in this file; used only by the bot-params
    tests below via `_build_presenter_with_registry`."""

    def setup(self) -> None:
        self.period = self.input_int("period", 20, label="Period", minval=1, maxval=200)
        self.threshold = self.input_float("threshold", 1.5, label="Ngưỡng", minval=0.0)

    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


def _build_presenter_with_registry(
    qapp,
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    registry,
    request,
    script_registry: IndicatorScriptRegistry | None = None,
) -> BackTestPresenter:
    """Same wiring as the `mock_container`/`presenter` fixtures, but with a
    caller-supplied `StrategyRegistry` — used by the bot-params tests that
    need more than the shared fixture's single zero-param `_FakeStrategy`.
    `script_registry` (BOT-064) defaults to a fresh empty one, same as the
    shared `indicator_script_registry` fixture."""
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    container = Mock()
    resolved_script_registry = script_registry or IndicatorScriptRegistry()

    def resolve_mock(interface):
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            return mock_config
        if interface == StrategyRegistry:
            return registry
        if interface == IndicatorScriptRegistry:
            return resolved_script_registry
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = BackTestView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return BackTestPresenter(view, container)


def _make_result(with_trades: bool) -> BacktestResult:
    metrics = BacktestMetrics(
        net_profit=10.0 if with_trades else 0.0,
        net_profit_percent=1.0 if with_trades else 0.0,
        gross_profit=10.0 if with_trades else 0.0,
        gross_loss=0.0,
        max_drawdown_percent=0.0,
        total_closed_trades=1 if with_trades else 0,
        percent_profitable=100.0 if with_trades else 0.0,
        profit_factor=1.0,
        avg_trade=0.0,
        avg_winning_trade=0.0,
        avg_losing_trade=0.0,
        largest_winning_trade=0.0,
        largest_losing_trade=0.0,
    )
    trades = []
    if with_trades:
        from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

        trades = [
            Trade(
                symbol="ETHUSDT",
                entry_time=_T0,
                entry_price=100.0,
                exit_time=_T1,
                exit_price=110.0,
                quantity=1.0,
                pnl=10.0,
                pnl_percent=10.0,
                fees_paid=0.0,
            )
        ]
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0 + (10.0 if with_trades else 0.0),
        trades=trades,
        equity_curve=[(_T0, 1000.0), (_T1, 1000.0)],
        metrics=metrics,
    )


def _make_fake_result(trades: list) -> BacktestResult:
    """BOT-095B alias: wraps _make_result for FSM/dirty-tracking tests that
    pass an explicit `trades` list instead of a bool flag."""
    return _make_result(with_trades=len(trades) > 0)


def _make_result_with_trades(trade_count: int, win_count: int) -> BacktestResult:
    """@brief BOT-057: `_make_result`'s `with_trades: bool` only ever makes
    0 or 1 trade — filter/search/pagination tests need a real spread."""
    from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

    trades = [
        Trade(
            symbol="ETHUSDT",
            entry_time=_T0,
            entry_price=100.0,
            exit_time=_T1,
            exit_price=110.0 if i < win_count else 90.0,
            quantity=1.0,
            pnl=10.0 if i < win_count else -10.0,
            pnl_percent=10.0 if i < win_count else -10.0,
            fees_paid=0.0,
        )
        for i in range(trade_count)
    ]
    metrics = BacktestMetrics(
        net_profit=0.0,
        net_profit_percent=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        max_drawdown_percent=0.0,
        total_closed_trades=trade_count,
        percent_profitable=0.0,
        profit_factor=1.0,
        avg_trade=0.0,
        avg_winning_trade=0.0,
        avg_losing_trade=0.0,
        largest_winning_trade=0.0,
        largest_losing_trade=0.0,
    )
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=trades,
        equity_curve=[(_T0, 1000.0), (_T1, 1000.0)],
        metrics=metrics,
    )


def _dispatch_stub(
    result: BacktestResult | None,
    klines: list | None = None,
    *,
    realtime: bool = False,
):
    """`_run_backtest` dispatches 2 different commands (BacktestResult, then
    chart klines) — a single `mock.return_value` can't tell them apart, so
    tests that reach the chart-fetch step need this instead.

    `realtime=True` answers `RunRealtimeBacktestCommand` instead of
    `RunStaticBacktestCommand` (BOT-076 §3.3) — a test must pick the one that
    matches the config's `execution_mode`, since `_run_backtest` dispatches
    exactly one of the two, never both."""

    def side_effect(handler_class, command):
        if not realtime and handler_class is RunStaticBacktestCommand:
            return result
        if realtime and handler_class is RunRealtimeBacktestCommand:
            return result
        if handler_class is GetHistoricalKlinesQuery:
            return klines or []
        raise AssertionError(f"Unexpected dispatch: {handler_class}")

    return side_effect


@pytest.fixture
def strategy_registry():
    registry = StrategyRegistry()
    registry.register("fake_strategy", _FakeStrategy)
    return registry


@pytest.fixture
def indicator_script_registry():
    # Deliberately empty and REAL (not a Mock): IndicatorScriptRunner.rebuild()
    # then hits its own KeyError/on_error path for the unregistered
    # "ema_ribbon" key, exactly as it would for any stale key — no need to
    # register the real script just to prove the chart-data path is safe.
    return IndicatorScriptRegistry()


@pytest.fixture
def mock_thread_mgr():
    return Mock()


@pytest.fixture
def mock_dispatcher():
    return Mock()


@pytest.fixture
def mock_config():
    config = Mock()
    # Empty by default: BOT-058's fallback path (no DEFAULT_SYMBOLS/
    # DEFAULT_INTERVAL configured) — individual tests override
    # get_all.return_value to exercise the config-driven path instead.
    config.get_all.return_value = {}

    def get_config(key, default=None):
        if key == DEV_MODE_CONFIG_KEY:
            return True
        if key == ConfigKeys.BACKTEST_CHART_BACKEND.value:
            return "python"
        return default

    config.get.side_effect = get_config
    return config


@pytest.fixture
def mock_container(
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    strategy_registry,
    indicator_script_registry,
):
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            return mock_config
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == IndicatorScriptRegistry:
            return indicator_script_registry
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return Mock()

    container.resolve.side_effect = resolve_mock
    return container


@pytest.fixture
def presenter(qapp, mock_container, request):
    view = BackTestView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return BackTestPresenter(view, mock_container)


@pytest.fixture
def view_model(presenter):
    return presenter._view_model


# ---------------------------------------------------------------------------
# Strategy options
# ---------------------------------------------------------------------------


def test_strategy_options_loaded_from_registry_on_init(view_model):
    assert view_model.strategyOptions == [
        {
            "key": "fake_strategy",
            "name": "Fake Strategy",
            "category": "",
            "description": "",
        }
    ]
    assert view_model.selectedStrategyKey == "fake_strategy"


# ---------------------------------------------------------------------------
# Symbol picker (BOT-102)
# ---------------------------------------------------------------------------


def test_selected_symbol_defaults_to_the_presenters_configured_symbol(
    presenter, view_model
):
    assert view_model.selectedSymbol == presenter._symbol
    assert view_model.symbolOptions == []


def test_opening_symbol_picker_fetches_options_from_the_exchange(
    presenter, mock_thread_mgr
):
    presenter._on_symbol_picker_open_requested()

    mock_thread_mgr.submit.assert_called_once_with(presenter._fetch_symbol_options)


def test_opening_symbol_picker_again_does_not_refetch_when_already_cached(
    presenter, mock_thread_mgr
):
    presenter._symbol_options_cache = ["BTCUSDT", "ETHUSDT"]

    presenter._on_symbol_picker_open_requested()

    mock_thread_mgr.submit.assert_not_called()


def test_fetch_symbol_options_dispatches_query_and_populates_the_view_model(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = ["BTCUSDT", "ETHUSDT"]

    presenter._fetch_symbol_options()

    handler_class, query = mock_dispatcher.dispatch.call_args[0]
    assert handler_class is ListAvailableSymbolsQuery
    assert isinstance(query, ListAvailableSymbolsQuery)
    assert presenter._symbol_options_cache == ["BTCUSDT", "ETHUSDT"]
    assert view_model.symbolOptions == ["BTCUSDT", "ETHUSDT"]


def test_fetch_symbol_options_failure_does_not_cache_and_logs_without_crashing(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.side_effect = RuntimeError("exchange unreachable")

    presenter._fetch_symbol_options()

    assert presenter._symbol_options_cache is None
    assert view_model.symbolOptions == []
    assert "exchange unreachable" in view_model.log_model._entries[-1].message


def test_selecting_a_symbol_updates_the_presenters_symbol_and_rebuilds_the_chart(
    presenter, view_model
):
    original_symbol = presenter._symbol
    new_symbol = "ETHUSDT" if original_symbol != "ETHUSDT" else "BTCUSDT"

    view_model.selectedSymbol = new_symbol

    assert presenter._symbol == new_symbol
    assert presenter.view._last_symbols == [new_symbol]


def test_selecting_the_already_active_symbol_is_a_no_op(
    presenter, view_model, mock_thread_mgr
):
    mock_thread_mgr.reset_mock()

    view_model.selectedSymbol = presenter._symbol

    mock_thread_mgr.submit.assert_not_called()


def test_selecting_a_symbol_submits_a_fresh_chart_preview_for_it(
    presenter, view_model, mock_thread_mgr
):
    new_symbol = "ETHUSDT" if presenter._symbol != "ETHUSDT" else "BTCUSDT"
    mock_thread_mgr.reset_mock()

    view_model.selectedSymbol = new_symbol

    mock_thread_mgr.submit.assert_called_once()
    worker, config, _preview_id = mock_thread_mgr.submit.call_args[0]
    assert worker == presenter._run_chart_preview
    assert config.symbol == new_symbol


def test_selecting_a_symbol_marks_the_config_dirty_with_a_truthful_diff(
    presenter, view_model
):
    """Mirrors test_dirty_tracking_detects_timeframe_change_after_completed —
    a symbol change must be visible in the diff message too (BOT-102), not
    only detected by equality (which BacktestRunConfig already got for free
    since `symbol` was always a dataclass field, just never surfaced)."""
    view_model.selectedStrategyKey = "fake_strategy"
    view_model.selectedTimeframe = "1m"
    view_model.initialCapitalText = "10000"
    view_model.selectedCurrency = Currency.USD
    original_symbol = presenter._symbol

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    assert presenter.fsm.current_state == BacktestUiState.COMPLETED

    new_symbol = "ETHUSDT" if original_symbol != "ETHUSDT" else "BTCUSDT"
    view_model.selectedSymbol = new_symbol

    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY
    assert f"Symbol ({original_symbol} → {new_symbol})" in view_model.configDiffSummary


def test_dev_mode_enables_fps_overlay_on_the_real_backtest_chart(presenter):
    card = presenter.view.chart_cards[0]

    assert card.chart_card.fps_overlay.is_enabled is True
    assert card.chart_card.fps_overlay.label.isHidden() is False


def test_backtest_opengl_can_be_disabled_by_config(
    qapp, mock_container, mock_config, request
):
    previous_side_effect = mock_config.get.side_effect
    mock_config.get.side_effect = lambda key, default=None: (
        False
        if key == ConfigKeys.BACKTEST_CHART_OPENGL_ENABLED.value
        else previous_side_effect(key, default)
    )
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    BackTestPresenter(view, mock_container)

    assert view.chart_cards[0].chart_card.plot_layout.opengl_requested is False


def test_chart_klines_fetch_limit_covers_a_whole_backtested_range(presenter):
    """The chart must not be truncated to a slice of the run it is drawing.

    This was hardcoded to 5 000. A real session backtested 52 147 candles and
    plotted 960 trade markers across the full range, while the chart held only
    the most recent 5 000 — so panning left ran out of candles and the older
    markers stood over empty space. Per-frame pan cost is flat in history size
    (viewport windowing draws ~200 bars regardless: measured 18.2ms/frame at
    52 147 candles vs 20.9ms at 5 000), so the cap exists for memory only and
    must comfortably exceed a normal run.
    """
    assert presenter._chart_klines_fetch_limit >= 52_147


def test_chart_klines_fetch_limit_is_config_overridable(
    qapp, mock_container, mock_config, request
):
    previous_side_effect = mock_config.get.side_effect
    mock_config.get.side_effect = lambda key, default=None: (
        1234
        if key == ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value
        else previous_side_effect(key, default)
    )
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    built = BackTestPresenter(view, mock_container)

    assert built._chart_klines_fetch_limit == 1234


def test_backtest_cached_interaction_is_disabled_by_default(presenter):
    """BUG-009: the cached-frame preview must not be on by default.

    It previews a pan by translating a snapshot of the last rendered frame,
    which cannot show data past the snapshot's edge, cannot re-autoscale Y,
    and freezes the indicator/volume windows — the user-reported blank band,
    vertical jump on release and missing indicator lines all follow from
    that. Panning natively costs ~32ms/frame and is bounded by
    CHART_CARD_MAX_ZOOM_OUT_CANDLES, so the preview is no longer worth its
    visual cost. It stays available behind the config key.
    """
    assert presenter.view.chart_cards[0].chart_card.cached_interaction is None


def test_backtest_cached_interaction_can_be_re_enabled_by_config(
    qapp, mock_container, mock_config, request
):
    previous_side_effect = mock_config.get.side_effect
    mock_config.get.side_effect = lambda key, default=None: (
        True
        if key == ConfigKeys.BACKTEST_CHART_CACHED_INTERACTION_ENABLED.value
        else previous_side_effect(key, default)
    )
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    BackTestPresenter(view, mock_container)

    assert view.chart_cards[0].chart_card.cached_interaction is not None


# ---------------------------------------------------------------------------
# Config-driven default symbol/interval (BOT-058)
# ---------------------------------------------------------------------------


def test_reads_default_symbol_and_interval_from_config(
    qapp, mock_container, mock_config, request
):
    mock_config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "5m",
    }
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._symbol == "BTCUSDT"
    assert presenter._view_model.selectedTimeframe == "5m"
    assert view.chart_cards[0].chart_card.symbol == "BTCUSDT"


def test_empty_default_symbols_falls_back_to_a_default_symbol(
    qapp, mock_container, mock_config, request
):
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": [], "DEFAULT_INTERVAL": ""}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._symbol == _FALLBACK_SYMBOL


def test_missing_config_keys_fall_back_safely(
    qapp, mock_container, mock_config, request
):
    """A fresh install (Settings never opened) must not crash the screen."""
    mock_config.get_all.return_value = {}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._symbol == _FALLBACK_SYMBOL
    assert presenter._view_model.selectedTimeframe == "1m"


def test_invalid_default_interval_keeps_the_view_models_own_default(
    qapp, mock_container, mock_config, request
):
    """A hand-edited user_config.json with a typo'd interval must not crash
    or silently apply a value the toolbar doesn't offer."""
    mock_config.get_all.return_value = {"DEFAULT_INTERVAL": "999x"}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._view_model.selectedTimeframe == "1m"


def test_run_backtest_and_chart_fetch_use_the_config_driven_symbol(
    qapp, mock_container, mock_config, mock_dispatcher, request
):
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": ["BTCUSDT"]}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    presenter = BackTestPresenter(view, mock_container)
    view_model = presenter._view_model
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    config = _lock_and_get_config(presenter, view_model)
    presenter._run_backtest(config)

    assert mock_dispatcher.dispatch.call_args_list, "dispatch was never called"
    for call in mock_dispatcher.dispatch.call_args_list:
        _handler_class, command = call[0]
        assert command.symbol == "BTCUSDT"


def test_build_run_config_carries_the_presenters_actual_symbol_not_the_dataclass_default(
    qapp, mock_container, mock_config, request
):
    """`BacktestRunConfig.symbol` defaults to "ETHUSDT" (see
    backtest_fsm_matrix.py) — `_build_run_config()` had silently omitted
    `symbol=self._symbol` from its constructor call, so every completed
    run's stored `_last_run_config`/`lastRunSummary`/action-trace log
    silently showed "ETHUSDT" regardless of the real symbol, and Dirty
    Tracking's `symbol` comparison (compute_diff_summary) would spuriously
    fire on every toolbar edit for anyone whose configured symbol isn't
    "ETHUSDT". A test using the fixture's own ETHUSDT fallback default
    could never have caught this — the config here is deliberately anything
    else (BTCUSDT) so the dataclass default cannot coincidentally match."""
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": ["BTCUSDT"]}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    presenter = BackTestPresenter(view, mock_container)
    assert presenter._symbol == "BTCUSDT"

    config = presenter._build_run_config()

    assert config is not None
    assert config.symbol == "BTCUSDT"


# ---------------------------------------------------------------------------
# BOT-076 §3.3 — Realtime execution mode dispatch
# ---------------------------------------------------------------------------


def test_historical_tick_mode_dispatches_run_realtime_backtest_command(
    presenter, view_model, mock_dispatcher
):
    """The one thing BOT-074 explicitly left undone: unlocking the QML row
    means nothing if the Presenter still always builds a
    RunStaticBacktestCommand underneath it."""
    view_model.executionMode = "HISTORICAL_TICK"
    # Tick mode rejects the ALL_HISTORY default (unbounded start_time) -
    # see TickModeRequiresBoundedRangeRule.
    view_model.timeRangePreset = "7d"
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), realtime=True
    )

    config = _lock_and_get_config(presenter, view_model)
    assert config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK
    presenter._run_backtest(config)

    dispatched_handlers = [
        call[0][0] for call in mock_dispatcher.dispatch.call_args_list
    ]
    assert RunRealtimeBacktestCommand in dispatched_handlers
    assert RunStaticBacktestCommand not in dispatched_handlers

    realtime_call = next(
        call
        for call in mock_dispatcher.dispatch.call_args_list
        if call[0][0] is RunRealtimeBacktestCommand
    )
    _handler_class, realtime_command = realtime_call[0]
    assert realtime_command.tick_resolution == config.tick_resolution


def test_bar_close_mode_still_dispatches_run_static_backtest_command(
    presenter, view_model, mock_dispatcher
):
    """Explicit regression pin for the default path, now that dispatch
    branches on execution_mode instead of always building Static."""
    assert view_model.executionMode == "BAR_CLOSE"
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    config = _lock_and_get_config(presenter, view_model)
    presenter._run_backtest(config)

    dispatched_handlers = [
        call[0][0] for call in mock_dispatcher.dispatch.call_args_list
    ]
    assert RunStaticBacktestCommand in dispatched_handlers
    assert RunRealtimeBacktestCommand not in dispatched_handlers


def test_result_message_labels_realtime_vs_static_truthfully(
    presenter, view_model, mock_dispatcher
):
    """The two engines are allowed to disagree on the same data (BOT-076
    §5) — a result with no mode label is exactly the "looks identical, means
    something different" trap the task's own §3.3 checklist calls out."""
    view_model.selectedStrategyKey = "fake_strategy"

    view_model.executionMode = "HISTORICAL_TICK"
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    # No picker exists yet (BOT-076 §3.3 scope) — BacktestRunConfig.tick_resolution
    # always defaults to 1s, so that is the value a truthful label must show.
    assert "Realtime" in view_model.resultText
    assert "tick 1s" in view_model.resultText

    view_model.executionMode = "BAR_CLOSE"
    presenter._on_backtest_succeeded(result)
    assert "Static" in view_model.resultText


def test_probe_data_coverage_checks_tick_resolution_for_realtime_mode(
    presenter, view_model, mock_dispatcher
):
    """BOT-076's handler queries IMarketDataRepository at tick_resolution
    (e.g. 1s), never at the strategy interval (e.g. 5m) — checking coverage
    for the wrong one would report "fully covered" while the interval the
    handler actually reads was never synced at all."""
    view_model.executionMode = "HISTORICAL_TICK"
    view_model.timeRangePreset = "7d"
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = Mock(is_fully_covered=True)

    presenter._probe_data_coverage(config)

    _handler_class, query = mock_dispatcher.dispatch.call_args[0]
    assert query.interval == config.tick_resolution.value
    assert query.interval != config.timeframe.value


# ---------------------------------------------------------------------------
# Validation / dispatch gating
# ---------------------------------------------------------------------------


def test_run_backtest_submits_background_task_and_locks_fsm(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_backtest
    config = call_args[1]
    assert isinstance(config, BacktestRunConfig)
    assert config.strategy_key == "fake_strategy"
    assert config.timeframe == TimeFrame("1m")
    assert config.initial_balance == 10000.0


def test_all_history_run_freezes_its_end_boundary_before_background_work(
    presenter, view_model, mock_thread_mgr
):
    before = datetime.now(UTC)

    view_model.requestRun()

    submitted_config = mock_thread_mgr.submit.call_args[0][1]
    assert submitted_config.end_time is not None
    assert submitted_config.end_time >= before - timedelta(minutes=1)
    assert submitted_config.end_time <= datetime.now(UTC) - timedelta(minutes=1)


def test_all_history_run_ends_one_interval_before_now_to_use_a_published_candle(
    presenter, view_model, mock_thread_mgr
):
    """Regression: a run started immediately after a 1m close must not require
    the just-closed candle before Binance has published it to historical data."""
    frozen_now = datetime(2026, 8, 17, 5, 38, 2, tzinfo=UTC)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now if tz is None else frozen_now.astimezone(tz)

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter.datetime",
        _FixedDateTime,
    ):
        view_model.requestRun()

    submitted_config = mock_thread_mgr.submit.call_args[0][1]
    assert submitted_config.end_time == datetime(2026, 8, 17, 5, 37, 2, tzinfo=UTC)


def test_dev_trace_logs_when_dev_mode_is_enabled(
    presenter, view_model, mock_thread_mgr, caplog
):
    with caplog.at_level(logging.INFO, logger="App.BackTestPresenter"):
        view_model.requestRun()

    messages = [record.getMessage() for record in caplog.records]
    assert any("BACKTEST_TRACE action=run_requested" in message for message in messages)
    assert any(
        "BACKTEST_TRACE action=run_config_built" in message for message in messages
    )
    assert any(
        "BACKTEST_TRACE action=run_worker_submitted" in message for message in messages
    )


def test_invalid_capital_is_rejected_without_submitting(
    presenter, view_model, mock_thread_mgr
):
    view_model.initialCapitalText = "not-a-number"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True
    assert presenter.fsm.current_state == BacktestUiState.IDLE


def test_non_positive_capital_is_rejected(presenter, view_model, mock_thread_mgr):
    view_model.initialCapitalText = "0"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True


def test_custom_range_with_invalid_start_is_rejected(
    presenter, view_model, mock_thread_mgr
):
    view_model.timeRangePreset = "custom"
    view_model.customStartText = "not-a-date"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True


def test_custom_range_start_after_end_is_rejected(
    presenter, view_model, mock_thread_mgr
):
    view_model.timeRangePreset = "custom"
    view_model.customStartText = "2026-06-01 00:00"
    view_model.customEndText = "2026-01-01 00:00"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True


def test_run_backtest_ignored_while_already_running(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()
    mock_thread_mgr.reset_mock()

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Background outcomes (calling _run_backtest directly, as the pool would)
# ---------------------------------------------------------------------------


def _lock_and_get_config(presenter, view_model) -> BacktestRunConfig:
    view_model.requestRun()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    return presenter._build_run_config() or BacktestRunConfig(
        strategy_key="fake_strategy",
        timeframe=TimeFrame("1m"),
        initial_balance=10000.0,
        start_time=None,
        end_time=None,
    )


def test_successful_run_with_trades_updates_view_model_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert view_model.resultIsError is False
    assert "ETHUSDT" in view_model.resultText
    assert "Closed trades: 1" in view_model.resultText
    assert len(view_model.primaryStatCards) == 4
    assert len(view_model.extendedStatCards) == 9  # BOT-079: +Total Fees Paid
    assert view_model.resultWarningText == ""  # no fee/frequency flags on this result
    assert len(view_model.limitations) > 0  # BOT-081


def test_successful_run_with_a_fee_dominant_result_sets_the_warning_text(
    presenter, view_model, mock_dispatcher
):
    """BOT-079 follow-up: the warning is a separate line
    (`resultWarningText`), not folded into the Net PnL badge — verifies the
    Presenter actually wires `build_result_warning_text()` through, not just
    that `performance_metrics_view.py` can compute it in isolation."""
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    fee_dominant_metrics = replace(
        result.metrics, has_high_fee_ratio=True, avg_bars_per_trade=5.0
    )
    result = replace(result, metrics=fee_dominant_metrics)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)

    presenter._run_backtest(config)

    assert view_model.resultWarningText != ""
    assert "Phí giao dịch" in view_model.resultWarningText


def test_successful_run_with_a_diverging_out_of_sample_result_sets_the_warning_text(
    presenter, view_model, mock_dispatcher
):
    """BOT-080: same end-to-end wiring check as the fee-dominant test above,
    for the in-sample/out-of-sample overfitting warning."""
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    result = replace(
        result,
        out_of_sample=OutOfSampleValidation(
            in_sample=replace(
                result, metrics=replace(result.metrics, net_profit_percent=50.0)
            ),
            out_of_sample=replace(
                result, metrics=replace(result.metrics, net_profit_percent=-20.0)
            ),
            in_sample_ratio=0.7,
        ),
    )
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)

    presenter._run_backtest(config)

    assert view_model.resultWarningText != ""
    assert "overfit" in view_model.resultWarningText
    titles = {card["title"] for card in view_model.extendedStatCards}
    assert "In-Sample Net Profit" in titles
    assert "Out-of-Sample Net Profit" in titles


def test_successful_run_populates_limitations_from_the_real_result(
    presenter, view_model, mock_dispatcher
):
    """BOT-081: verifies the Presenter wires build_backtest_limitations()
    through, and that the out-of-sample item is genuinely per-run — this
    result has no out_of_sample (like `_make_result()`'s default), so the
    "no out-of-sample validation" note must appear even though BOT-080
    shipped."""
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)

    presenter._run_backtest(config)

    joined = " ".join(view_model.limitations)
    assert "Stop Loss" in joined
    assert "out-of-sample" in joined  # this specific run has no split


def test_successful_run_omits_the_out_of_sample_note_when_a_split_exists(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    result = replace(
        result,
        out_of_sample=OutOfSampleValidation(
            in_sample=result, out_of_sample=result, in_sample_ratio=0.7
        ),
    )
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)

    presenter._run_backtest(config)

    assert not any("out-of-sample" in note for note in view_model.limitations)


def test_no_historical_data_clears_limitations(presenter, view_model, mock_dispatcher):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert view_model.limitations == []


def test_qml_limitations_button_opens_without_crashing(
    presenter, view_model, qml_item, qapp, mock_dispatcher
):
    """BOT-081: the info icon must be a real `Button` (Python-test-clickable,
    per BOT-057/BOT-083's convention), not a Rectangle+MouseArea."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()

    qml_item(root, "btnBacktestLimitations").clicked.emit()
    qapp.processEvents()


def test_dispatches_run_static_backtest_command_with_the_built_config(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    # First call is the backtest itself — the chart's own klines fetch
    # (GetHistoricalKlinesQuery) happens after, tested separately below.
    handler_class, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert handler_class is RunStaticBacktestCommand
    assert command.symbol == "ETHUSDT"
    assert command.strategy_key == "fake_strategy"
    assert command.interval == TimeFrame("1m")
    assert command.initial_balance == 10000.0


def test_no_historical_data_reports_empty_message_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.EMPTY_DATA
    assert view_model.resultIsError is False
    assert "Không có dữ liệu" in view_model.resultText
    # BOT-059: "no data at all" is exactly the case "Đồng bộ ngay" exists for.
    assert view_model.needsDataSync is True
    assert presenter._last_no_data_config is config


def test_zero_trades_reports_empty_message_with_the_metrics(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=False)
    )

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert view_model.resultIsError is False
    assert "không có giao dịch nào" in view_model.resultText
    assert "Closed trades: 0" in view_model.resultText
    # BOT-055: 0 trades still populates the 4 cards (all reading 0), not an
    # empty panel — only "no historical data at all" clears it.
    assert len(view_model.primaryStatCards) == 4
    # BOT-059: 0 trades is a real result, not "no data" — must not offer sync.
    assert view_model.needsDataSync is False


def test_dispatch_exception_reports_error_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert view_model.resultIsError is True
    assert "boom" in view_model.resultText


# ---------------------------------------------------------------------------
# "Đồng bộ ngay" (BOT-059)
# ---------------------------------------------------------------------------


def _run_to_no_data(presenter, view_model, mock_dispatcher) -> BacktestRunConfig:
    """Drives the presenter into the "no historical data, needsDataSync=True"
    state every sync test starts from."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None
    presenter._run_backtest(config)
    mock_dispatcher.dispatch.reset_mock()
    return config


def _missing_coverage() -> BacktestRangeCoverage:
    return BacktestRangeCoverage(
        is_fully_covered=False,
        first_open_time=None,
        last_open_time=None,
        expected_candles=10,
        actual_candles=0,
        duplicate_candles=0,
        missing_open_times=(_T0,),
        has_unclosed_candle=False,
    )


def _complete_coverage() -> BacktestRangeCoverage:
    return replace(
        _missing_coverage(),
        is_fully_covered=True,
        actual_candles=10,
        missing_open_times=(),
    )


def test_missing_coverage_auto_starts_sync_with_the_run_snapshot(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None
    mock_thread_mgr.reset_mock()

    presenter._on_backtest_coverage_missing_for_action(
        action.action_id, action.config, _missing_coverage(), True
    )

    assert presenter.fsm.current_state is BacktestUiState.SYNCING
    assert presenter._active_action is not None
    assert presenter._active_action.kind is BacktestActionKind.SYNC
    assert presenter._active_action.config == action.config
    assert view_model.needsDataSync is True
    assert mock_thread_mgr.submit.call_args[0][0] == presenter._run_sync


def test_missing_coverage_after_sync_fails_without_sync_loop(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None
    mock_thread_mgr.reset_mock()

    presenter._on_backtest_coverage_missing_for_action(
        action.action_id, action.config, _missing_coverage(), False
    )

    assert presenter.fsm.current_state is BacktestUiState.ERROR
    assert "Thiếu nến" in view_model.resultText
    mock_thread_mgr.submit.assert_not_called()


def test_stale_coverage_result_cannot_start_sync(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()
    old_action = presenter._active_action
    assert old_action is not None
    presenter._begin_action(
        BacktestActionKind.BACKTEST,
        presenter._get_current_config(),
        presenter.fsm.current_state,
    )
    mock_thread_mgr.reset_mock()

    presenter._on_backtest_coverage_missing_for_action(
        old_action.action_id, old_action.config, _missing_coverage(), True
    )

    assert presenter.fsm.current_state is BacktestUiState.RUNNING
    mock_thread_mgr.submit.assert_not_called()


def test_sync_progress_updates_only_the_active_sync_action(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    sync_action = presenter._active_action
    assert sync_action is not None

    presenter._on_sync_progress_for_action(sync_action.action_id, 45, 100)

    assert view_model.syncProgressPercent == 45.0
    assert "45/100" in view_model.syncProgressText
    presenter._finish_action(sync_action.action_id, BacktestActionOutcome.INVALIDATED)
    presenter._on_sync_progress_for_action(sync_action.action_id, 90, 100)
    assert view_model.syncProgressPercent == 45.0


def test_timeframe_change_submits_background_preview_with_snapshot(
    presenter, view_model, mock_thread_mgr
):
    mock_thread_mgr.reset_mock()

    view_model.selectedTimeframe = "5m"

    mock_thread_mgr.submit.assert_called_once()
    worker, config, preview_id = mock_thread_mgr.submit.call_args[0]
    assert worker == presenter._run_chart_preview
    assert config.timeframe is TimeFrame.FIVE_MINUTES
    assert preview_id == presenter._active_preview_id


def test_chart_toolbar_timeframe_click_updates_backtest_data_contract(
    presenter, view_model, mock_thread_mgr
):
    """BUG-008: chart-header timeframe buttons must request new chart data.

    This intentionally clicks the visible QtWidgets control instead of calling
    the presenter slot.  A highlighted button without a new ViewModel
    timeframe/preview is a user-visible no-op, not a successful interaction.
    """
    mock_thread_mgr.reset_mock()
    toolbar = presenter.view.chart_cards[0].chart_card.toolbar

    toolbar._buttons["5m"].click()

    assert view_model.selectedTimeframe == "5m"
    worker, config, preview_id = mock_thread_mgr.submit.call_args.args
    assert worker == presenter._run_chart_preview
    assert config.timeframe is TimeFrame.FIVE_MINUTES
    assert preview_id == presenter._active_preview_id


def test_qml_timeframe_selection_keeps_chart_toolbar_in_sync(presenter, view_model):
    """The QML picker and chart header are one selected-timeframe contract."""
    toolbar = presenter.view.chart_cards[0].chart_card.toolbar

    view_model.selectedTimeframe = "15m"

    assert toolbar._buttons["15m"].isChecked() is True
    assert toolbar._buttons["1m"].isChecked() is False


def test_preview_result_updates_coverage_and_chart_but_stale_result_is_fenced(
    presenter, view_model
):
    presenter.view.on_preview_data_ready = Mock()
    presenter._active_preview_id = 2

    presenter._on_preview_data_ready(1, _missing_coverage(), ["old"], [])
    presenter.view.on_preview_data_ready.assert_not_called()

    presenter._on_preview_data_ready(2, _complete_coverage(), ["new"], ["volume"])

    assert view_model.isDataFullyCovered is True
    assert view_model.needsDataSync is False
    presenter.view.on_preview_data_ready.assert_called_once_with(["new"], ["volume"])


def test_request_sync_ignored_without_a_cached_no_data_config(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestSync()

    mock_thread_mgr.submit.assert_not_called()
    assert presenter.fsm.current_state == BacktestUiState.IDLE


def test_request_sync_transitions_to_syncing_and_submits_background_task(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    mock_thread_mgr.reset_mock()

    view_model.requestSync()

    assert presenter.fsm.current_state == BacktestUiState.SYNCING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_sync
    assert call_args[1] == config
    assert call_args[1] is not config
    assert call_args[3] is presenter._sync_cancellation_token


def test_presenter_shutdown_cancels_inflight_backtest_and_sync_once(presenter):
    backtest_token = CancellationToken()
    sync_token = CancellationToken()
    presenter._backtest_cancellation_token = backtest_token
    presenter._sync_cancellation_token = sync_token

    presenter.shutdown()
    presenter.shutdown()

    assert backtest_token.is_cancelled() is True
    assert sync_token.is_cancelled() is True
    assert presenter._shutdown_requested is True


def test_request_sync_ignored_while_a_backtest_is_already_running(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestRun()  # IDLE -> RUNNING again
    mock_thread_mgr.reset_mock()

    view_model.requestSync()

    mock_thread_mgr.submit.assert_not_called()


def test_run_sync_dispatches_sync_market_data_command_for_the_no_data_config(
    presenter, view_model, mock_dispatcher
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_dispatcher.dispatch.side_effect = [None, _complete_coverage()]

    presenter._run_sync(config)

    handler_class, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert handler_class is SyncMarketDataCommand
    assert command.symbols == [presenter._symbol]
    assert command.interval == config.timeframe


def test_run_sync_fetches_one_interval_past_the_frozen_probe_boundary(
    presenter, mock_dispatcher
):
    end_time = datetime(2026, 8, 17, 4, 47, 15, tzinfo=UTC)
    config = replace(presenter._get_current_config(), end_time=end_time)
    action = presenter._begin_action(
        BacktestActionKind.SYNC, config, BacktestUiState.EMPTY_DATA
    )
    mock_dispatcher.dispatch.side_effect = [None, _complete_coverage()]

    presenter._run_sync(action.config, action.action_id)

    handler_class, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert handler_class is SyncMarketDataCommand
    assert command.end_time == end_time + timedelta(minutes=1)


def test_run_sync_resumes_from_the_coverage_gap_not_the_full_requested_range(
    presenter, view_model, mock_dispatcher, mock_thread_mgr, caplog
):
    """BUG-017 regression: coverage detection correctly finds the real gap
    (`coverage.missing_open_times[0]`), but the sync it triggers must resume
    from THAT point, not silently discard it and re-fetch the entire
    originally requested range from Binance."""
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None
    requested_start = datetime(2020, 1, 1, tzinfo=UTC)  # long before the gap
    config = replace(action.config, start_time=requested_start)
    coverage = _missing_coverage()  # gap at _T0 = 2026-01-01
    assert coverage.missing_open_times[0] != requested_start
    mock_thread_mgr.reset_mock()
    mock_dispatcher.dispatch.side_effect = [None, _complete_coverage()]

    with caplog.at_level(logging.INFO, logger="App.BackTestPresenter"):
        presenter._on_backtest_coverage_missing_for_action(
            action.action_id, config, coverage, True
        )
        # Exercise exactly what was actually submitted to the thread pool —
        # not a hand-built call — so this proves the real wiring, not just a
        # plausible-looking call to _run_sync in isolation.
        submitted_args = mock_thread_mgr.submit.call_args[0][1:]
        presenter._run_sync(*submitted_args)

    _, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert command.start_time == coverage.missing_open_times[0]
    assert command.start_time != requested_start
    # Log-proved: the decision (which start it resumed from and why) must be
    # findable in a real session's log, not just inferable from the outcome.
    resolved_lines = [
        r.message for r in caplog.records if "sync_start_resolved" in r.message
    ]
    assert len(resolved_lines) == 1
    assert "source=coverage_gap" in resolved_lines[0]


def test_run_sync_falls_back_to_the_requested_start_with_no_prior_coverage(
    presenter, view_model, mock_dispatcher, caplog
):
    """The cold-DB case (BUG-017's suggested-fix note): with no coverage
    probe result at all, the full requested range genuinely is missing, so
    falling back to `config.start_time` is correct, not a regression."""
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_dispatcher.dispatch.side_effect = [None, _complete_coverage()]

    with caplog.at_level(logging.INFO, logger="App.BackTestPresenter"):
        presenter._run_sync(config)

    _, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert command.start_time == config.start_time
    resolved_lines = [
        r.message for r in caplog.records if "sync_start_resolved" in r.message
    ]
    assert len(resolved_lines) == 1
    assert "source=requested_range" in resolved_lines[0]


def test_sync_without_the_required_candle_reports_incomplete_and_keeps_retry_available(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    """Regression: transport success is not data coverage success.

    The old flow logged "Đồng bộ dữ liệu thành công", restarted the backtest,
    then immediately emitted the same missing-candle error.  The user must get
    one truthful incomplete-sync result and retain the retry affordance.
    """
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    mock_dispatcher.dispatch.return_value = _missing_coverage()

    presenter._run_sync(config)

    assert presenter.fsm.current_state is BacktestUiState.ERROR
    assert view_model.needsDataSync is True
    assert presenter._last_no_data_config == config
    assert "Đồng bộ chưa đủ" in view_model.resultText
    mock_thread_mgr.submit.assert_not_called()


def test_sync_success_clears_the_flag_and_auto_resubmits_the_backtest(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    # The worker verifies coverage after SyncMarketDataCommand.  The
    # resubmitted RunStaticBacktestCommand is never dispatched in this test
    # because mock_thread_mgr is a Mock, not a real thread pool.
    mock_dispatcher.dispatch.side_effect = [None, _complete_coverage()]

    presenter._run_sync(config)

    assert view_model.needsDataSync is False
    assert presenter._last_no_data_config is None
    # Auto-resubmitted straight into RUNNING, no click needed.
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_backtest


def test_sync_success_resubmits_with_its_original_config_snapshot(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    """A sync success authorizes only the intent that created that sync.

    It must never infer a fresh action from live toolbar fields; a future
    editable-while-syncing flow must invalidate the old action instead.
    """
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    view_model.initialCapitalText = "500"
    mock_thread_mgr.reset_mock()
    # The worker verifies coverage after SyncMarketDataCommand.  The
    # resubmitted RunStaticBacktestCommand is never dispatched in this test
    # because mock_thread_mgr is a Mock, not a real thread pool.
    mock_dispatcher.dispatch.side_effect = [None, _complete_coverage()]

    presenter._run_sync(config)

    resubmitted_config = mock_thread_mgr.submit.call_args[0][1]
    assert resubmitted_config.initial_balance == config.initial_balance


def test_sync_failure_keeps_the_flag_and_returns_to_idle(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    mock_dispatcher.dispatch.side_effect = RuntimeError("sync boom")

    presenter._run_sync(config)

    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert view_model.needsDataSync is True
    assert presenter._last_no_data_config is config
    assert view_model.resultIsError is True
    assert "sync boom" in view_model.resultText
    mock_thread_mgr.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Cancelling a sync (previously: no way to cancel at all - the FSM had no
# (SYNCING, CANCEL_REQUESTED) transition, and _run_sync silently returned on
# a cancelled token without ever emitting a signal, so nothing could ever
# resolve the UI out of SYNCING once cancel was wired to it.)
# ---------------------------------------------------------------------------


def test_cancel_button_cancels_the_sync_token_not_the_backtest_token(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    assert presenter.fsm.current_state == BacktestUiState.SYNCING
    sync_token = presenter._sync_cancellation_token
    assert sync_token is not None
    presenter._backtest_cancellation_token = CancellationToken()

    presenter._on_cancel_backtest()

    assert presenter.fsm.current_state == BacktestUiState.CANCELLING
    assert sync_token.is_cancelled() is True
    assert presenter._backtest_cancellation_token.is_cancelled() is False
    assert "đồng bộ" in view_model.resultText.lower()


def test_run_sync_emits_sync_cancelled_and_resolves_fsm_back_to_idle(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    """End-to-end: _run_sync is called directly (mirrors how every other
    sync test in this file drives the worker synchronously) with an
    already-cancelled token, exactly as it would be after
    _on_cancel_backtest() calls token.cancel() mid-flight. The signal it
    emits is connected with a same-thread DirectConnection, so this single
    call exercises the full round trip: _syncCancelledSignal ->
    _on_sync_cancelled_for_action -> _complete_cancelled_action -> FSM back
    to IDLE."""
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    action_id = presenter._active_action.action_id
    presenter._cancelling_action_id = action_id
    presenter._invalidate_active_action()
    presenter.fsm.dispatch(BacktestUiEvent.CANCEL_REQUESTED)
    assert presenter.fsm.current_state == BacktestUiState.CANCELLING
    token = presenter._sync_cancellation_token
    token.cancel()
    mock_dispatcher.dispatch.return_value = None

    presenter._run_sync(config, action_id, token)

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert presenter._sync_cancellation_token is None
    assert presenter._cancelling_action_id is None
    assert "hủy đồng bộ" in view_model.resultText.lower()


def test_sync_succeeding_right_after_cancel_requested_still_resolves_fsm(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    """The race _on_sync_succeeded_for_action's cancelling-guard exists for:
    a cancel is requested, but the worker was already past its last
    cooperative check and reports success normally instead of going through
    _syncCancelledSignal. Without the guard this left the FSM stuck in
    CANCELLING forever - only _complete_cancelled_action ever resolves it."""
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    action_id = presenter._active_action.action_id
    presenter._on_cancel_backtest()
    assert presenter.fsm.current_state == BacktestUiState.CANCELLING

    presenter._on_sync_succeeded_for_action(action_id)

    assert presenter.fsm.current_state != BacktestUiState.CANCELLING
    assert presenter._cancelling_action_id is None


def test_sync_failing_right_after_cancel_requested_still_resolves_fsm(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    action_id = presenter._active_action.action_id
    presenter._on_cancel_backtest()
    assert presenter.fsm.current_state == BacktestUiState.CANCELLING

    presenter._on_sync_failed_for_action(action_id, "irrelevant, arrived too late")

    assert presenter.fsm.current_state != BacktestUiState.CANCELLING
    assert presenter._cancelling_action_id is None


def test_cancel_ignored_when_nothing_is_active(presenter, view_model):
    assert presenter.fsm.current_state == BacktestUiState.IDLE

    presenter._on_cancel_backtest()

    assert presenter.fsm.current_state == BacktestUiState.IDLE


# ---------------------------------------------------------------------------
# BOT-076 — tick mode rejects an unbounded (ALL_HISTORY) time range.
#
# GetBacktestRangeCoverageQuery's SQL has no lower bound when start_time is
# None, so it scans every 1s-interval row ever synced for the symbol. A real
# session got stuck retrying "Đồng bộ dữ liệu ngay" forever: the coverage
# round-trip got slower every retry as more tick data accumulated, while the
# live-trailing end_time cutoff kept advancing with real time regardless, so
# the two could never converge.
# ---------------------------------------------------------------------------


def test_all_history_with_tick_mode_is_rejected_before_any_dispatch(
    presenter, view_model, mock_dispatcher
):
    view_model.executionMode = "HISTORICAL_TICK"
    assert view_model.timeRangePreset == "all"  # the actual default, unchanged

    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.resultIsError is True
    assert "Toàn bộ lịch sử" in view_model.resultText
    mock_dispatcher.dispatch.assert_not_called()


def test_all_history_with_bar_close_mode_is_still_allowed(
    presenter, view_model, mock_dispatcher
):
    """The new rule is tick-mode-specific — Static backtests must keep
    being allowed to run over the full local history exactly as before."""
    assert view_model.executionMode == "BAR_CLOSE"
    assert view_model.timeRangePreset == "all"
    mock_dispatcher.dispatch.return_value = None

    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING


def test_tick_mode_with_a_bounded_range_is_allowed(
    presenter, view_model, mock_dispatcher
):
    view_model.executionMode = "HISTORICAL_TICK"
    view_model.timeRangePreset = "7d"
    mock_dispatcher.dispatch.return_value = None

    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING


def test_qml_sync_button_only_visible_after_no_data_and_click_requests_sync(
    presenter, view_model, mock_dispatcher, qml_item, qapp, mock_thread_mgr
):
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()
    assert qml_item(root, "btnRequestSync").property("visible") is False

    _run_to_no_data(presenter, view_model, mock_dispatcher)
    qapp.processEvents()
    mock_thread_mgr.reset_mock()

    assert qml_item(root, "btnRequestSync").property("visible") is True
    qml_item(root, "btnRequestSync").clicked.emit()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()
    assert mock_thread_mgr.submit.call_args[0][0] == presenter._run_sync


def test_qml_sync_button_retries_from_error_when_data_is_still_missing(
    presenter, view_model, mock_dispatcher, qml_item, qapp, mock_thread_mgr
):
    """Regression: the visible yellow retry button used to be a dead control.

    QML enabled it in ERROR while the FSM rejected SYNC_REQUESTED, so clicking
    produced no command and no feedback.
    """
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    sync_action = presenter._active_action
    assert sync_action is not None
    presenter._on_sync_failed_for_action(sync_action.action_id, "missing tail")
    qapp.processEvents()
    mock_thread_mgr.reset_mock()
    button = qml_item(presenter.view.top_widget.rootObject(), "btnRequestSync")

    assert presenter.fsm.current_state is BacktestUiState.ERROR
    assert button.property("visible") is True
    assert button.property("enabled") is True
    button.clicked.emit()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()
    assert mock_thread_mgr.submit.call_args[0][0] == presenter._run_sync
    assert presenter.fsm.current_state is BacktestUiState.SYNCING


# ---------------------------------------------------------------------------
# Stat cards (BOT-055)
# ---------------------------------------------------------------------------


def test_qml_renders_a_metric_card_per_primary_stat_card_after_a_run(
    presenter, view_model, qml_item, qapp, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)
    qapp.processEvents()

    root = presenter.view.top_widget.rootObject()
    card = qml_item(root, "cardMetric_0")
    assert card is not None
    assert card.property("value") != ""


# ---------------------------------------------------------------------------
# QML rendering
# ---------------------------------------------------------------------------


def test_qml_documents_load_without_errors(presenter, qapp):
    qapp.processEvents()
    assert presenter.view.top_widget.errors() == []
    assert presenter.view.bottom_widget.errors() == []
    assert presenter.view.overlay_host.quick_widget.errors() == []
    assert presenter.view.top_widget.rootObject() is not None
    assert presenter.view.bottom_widget.rootObject() is not None
    assert presenter.view.overlay_host.quick_widget.rootObject() is not None


def test_qml_run_button_click_requests_a_run(
    presenter, view_model, qml_item, qapp, mock_thread_mgr
):
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()

    qml_item(root, "btnRunBacktest").clicked.emit()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()


def test_bot_params_button_is_enabled(presenter, qml_item, qapp):
    """BOT-047: unlike BOT-022's placeholder, the dialog now renders a real,
    strategy-driven form, so the button no longer needs to stay locked."""
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()

    assert qml_item(root, "btnBacktestBotParams").property("enabled") is True


def test_bot_params_schema_is_empty_for_a_strategy_with_no_declared_params(
    view_model,
):
    """`fake_strategy` (the shared fixture's registered strategy) declares
    nothing — the modal must show "no params" rather than crash on an empty
    schema."""
    assert view_model.botParamsSchema == []


def test_bot_params_schema_reflects_a_strategy_with_declared_params(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model

    schema = view_model.botParamsSchema
    assert len(schema) == 1
    fields = {f["name"]: f for f in schema[0]["fields"]}
    assert fields["period"]["default"] == 20
    assert fields["period"]["value"] == 20
    assert fields["threshold"]["default"] == 1.5


def test_selecting_a_different_strategy_rebuilds_the_schema(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("fake_strategy", _FakeStrategy)
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model
    assert view_model.selectedStrategyKey == "fake_strategy"
    assert view_model.botParamsSchema == []

    view_model.selectedStrategyKey = "rich_strategy"

    assert len(view_model.botParamsSchema) == 1


def test_valid_bot_params_save_updates_params_clears_error_and_reruns(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model
    saved_signal_calls = []
    view_model.botParamsSaved.connect(lambda: saved_signal_calls.append(1))

    view_model.requestBotParamsSave({"period": "50", "threshold": "2.5"})

    assert presenter._strategy_params == {"period": 50, "threshold": 2.5}
    assert view_model.botParamsError == ""
    assert saved_signal_calls == [1]
    # Values shown by the (now-refreshed) schema reflect what was just saved.
    fields = {f["name"]: f for f in view_model.botParamsSchema[0]["fields"]}
    assert fields["period"]["value"] == 50
    mock_thread_mgr.submit.assert_called_once()
    config = mock_thread_mgr.submit.call_args[0][1]
    assert config.strategy_params == {"period": 50, "threshold": 2.5}


def test_invalid_bot_params_save_sets_error_and_does_not_rerun(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model
    saved_signal_calls = []
    view_model.botParamsSaved.connect(lambda: saved_signal_calls.append(1))

    # 500 is above period's declared maxval of 200.
    view_model.requestBotParamsSave({"period": "500", "threshold": "2.5"})

    assert presenter._strategy_params is None
    assert view_model.botParamsError != ""
    assert saved_signal_calls == []
    mock_thread_mgr.submit.assert_not_called()


def test_unparseable_bot_params_value_sets_error_and_does_not_rerun(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model

    view_model.requestBotParamsSave({"period": "not-a-number"})

    assert view_model.botParamsError != ""
    mock_thread_mgr.submit.assert_not_called()


def test_changing_strategy_after_a_save_discards_the_old_params(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("fake_strategy", _FakeStrategy)
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model
    view_model.selectedStrategyKey = "rich_strategy"
    view_model.requestBotParamsSave({"period": "50", "threshold": "2.5"})
    assert presenter._strategy_params is not None

    view_model.selectedStrategyKey = "fake_strategy"

    assert presenter._strategy_params is None
    assert view_model.botParamsError == ""


def test_run_backtest_command_carries_the_saved_strategy_params(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    """End-to-end: a saved param actually reaches the dispatched
    RunStaticBacktestCommand, not just BacktestRunConfig."""
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=False)
    )
    view_model.requestBotParamsSave({"period": "50", "threshold": "2.5"})
    config = mock_thread_mgr.submit.call_args[0][1]

    presenter._run_backtest(config)

    handler_class, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert handler_class is RunStaticBacktestCommand
    assert command.strategy_params == {"period": 50, "threshold": 2.5}


# ---------------------------------------------------------------------------
# Chart canvas (BOT-056)
# ---------------------------------------------------------------------------


def _make_klines(count: int = 3) -> list[MarketData]:
    return [
        MarketData(
            symbol="ETHUSDT",
            interval="1m",
            open_time=_T0,
            open_price=100.0 + i,
            high_price=105.0 + i,
            low_price=95.0 + i,
            close_price=102.0 + i,
            volume=10.0,
            close_time=_T0,
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for i in range(count)
    ]


def test_successful_run_fetches_klines_and_renders_the_ohlc_chart(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    assert len(presenter.view._last_klines) == 3
    assert presenter.view.chart_cards[0].chart_card._raw_history
    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type
        == CANDLESTICK
    )


def test_runtime_run_backtest_fetch_render_path_keeps_qquickwidgets_clean_and_chart_usable(
    presenter, view_model, mock_dispatcher, qapp
):
    """Regression harness for the real Backtest runtime path the user hit:
    run backtest -> fetch historical klines -> push them through the hybrid
    screen's live QQuickWidget + native ChartCard composition.

    Existing tests already proved each piece in isolation (use case, query,
    chart widget, QML parse/load), but this stitches them together in the
    exact order `_run_backtest()` uses at runtime and asserts the hybrid view
    stays internally consistent after the render burst."""
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    klines = _make_klines()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result, klines=klines)

    presenter._run_backtest(config)
    qapp.processEvents()

    assert presenter.view.top_widget.errors() == []
    assert presenter.view.bottom_widget.errors() == []
    assert presenter.view.overlay_host.quick_widget.errors() == []

    assert len(presenter.view._last_klines) == len(klines)
    assert presenter.view._last_volume
    assert presenter.view.chart_cards[0].chart_card._raw_history
    timestamps = [
        candle[0] for candle in presenter.view.chart_cards[0].chart_card._raw_history
    ]
    assert timestamps == sorted(timestamps)

    card = presenter.view.chart_cards[0]
    x_range, y_range = card.chart_card.plot_layout.main_plot.vb.viewRange()
    lows = [candle[3] for candle in card.chart_card._raw_history]
    highs = [candle[2] for candle in card.chart_card._raw_history]
    assert card.widget.width() > 0
    assert card.widget.height() > 0
    assert x_range[1] > x_range[0]
    assert y_range[1] > y_range[0]
    assert y_range[0] <= min(lows)
    assert y_range[1] >= max(highs)
    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type
        == CANDLESTICK
    )


def test_no_klines_leaves_the_chart_unrendered_without_crashing(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    assert presenter.view._last_klines == []


def test_switching_to_equity_mode_renders_a_line_from_the_equity_curve(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.set_chart_mode(ChartDisplayMode.EQUITY)

    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type == LINE
    )


def test_switching_to_both_mode_adds_an_equity_subplot(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.set_chart_mode(ChartDisplayMode.BOTH)

    assert presenter.view._equity_subplot_added is True
    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type
        == CANDLESTICK
    )


def test_switching_away_from_both_mode_removes_the_equity_subplot(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    presenter.view.set_chart_mode(ChartDisplayMode.BOTH)

    presenter.view.set_chart_mode(ChartDisplayMode.OHLC)

    assert presenter.view._equity_subplot_added is False


def test_ema_toggle_is_a_no_op_when_the_strategy_declares_no_indicators(
    presenter, view_model, mock_dispatcher
):
    """`_FakeStrategy` (the shared fixture's registered strategy) declares
    no indicators (BOT-060) — proves the toggle path degrades safely
    instead of crashing when there is nothing drawn to show/hide."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.chart_controls.sig_ema_toggled.emit(False)  # must not raise


def test_active_strategy_lines_are_cleared_before_each_new_run_not_after(
    presenter, view_model
):
    """Regression test (found by running the app, predates BOT-060):
    clearing the previous run's chart overlays must happen synchronously in
    _on_run_backtest (main thread, before the background run even starts).
    Calling it later, after the background thread has already started
    drawing the new run's lines, would race and could remove lines the new
    run just added instead of the old run's stale ones."""
    card = presenter.view.chart_cards[0]
    card.remove_indicator = Mock()
    presenter._active_strategy_lines = {"ema_fast", "ema_slow"}

    view_model.requestRun()

    assert card.remove_indicator.call_count == 2
    card.remove_indicator.assert_any_call("ema_fast")
    card.remove_indicator.assert_any_call("ema_slow")
    assert presenter._active_strategy_lines == set()

    if presenter.fsm.can_dispatch(BacktestUiEvent.BACKTEST_SUCCEEDED):
        presenter.fsm.dispatch(BacktestUiEvent.BACKTEST_SUCCEEDED)
    presenter._active_strategy_lines = {"ema_fast"}
    view_model.requestRun()

    assert card.remove_indicator.call_count == 3
    assert presenter._active_strategy_lines == set()


def test_successful_run_draws_the_strategys_own_indicator_lines_on_the_chart(
    presenter, view_model, mock_dispatcher
):
    """BOT-060: the chart must draw whatever the BACKTESTED strategy itself
    declares via build_indicators() — not a fixed, unrelated indicator
    script (the bug the user reported: Buy/Sell markers not lining up with
    anything drawn)."""
    presenter._strategy_registry.register("ema_strategy", _EmaIndicatorStrategy)
    view_model.selectedStrategyKey = "ema_strategy"
    config = _lock_and_get_config(presenter, view_model)
    assert config.strategy_key == "ema_strategy"
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    assert presenter._active_strategy_lines == {"ema_fast", "ema_slow"}
    added_names = {call.args[0] for call in card.add_overlay_indicator.call_args_list}
    assert added_names == {"ema_fast", "ema_slow"}
    updated_names = {call.args[0] for call in card.update_indicator_data.call_args_list}
    assert updated_names == {"ema_fast", "ema_slow"}


def test_ema_toggle_shows_and_hides_the_strategys_own_indicator_lines(
    presenter, view_model, mock_dispatcher
):
    presenter._strategy_registry.register("ema_strategy", _EmaIndicatorStrategy)
    view_model.selectedStrategyKey = "ema_strategy"
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    card.set_indicator_visible = Mock()

    presenter.view.chart_controls.sig_ema_toggled.emit(False)

    hidden_names = {call.args[0] for call in card.set_indicator_visible.call_args_list}
    assert hidden_names == {"ema_fast", "ema_slow"}
    assert all(
        call.args[1] is False for call in card.set_indicator_visible.call_args_list
    )


# ---------------------------------------------------------------------------
# Reference indicator script picker (BOT-064) — independent of the strategy's
# own lines above; both mechanisms must coexist without name collisions
# (qualified_line_name's ":" vs. the strategy lines' bare names).
# ---------------------------------------------------------------------------


def _build_presenter_with_script(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    script_registry = IndicatorScriptRegistry()
    script_registry.register("test_script", _TestReferenceScript)
    strategy_registry = StrategyRegistry()
    strategy_registry.register("fake_strategy", _FakeStrategy)
    return _build_presenter_with_registry(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        strategy_registry,
        request,
        script_registry=script_registry,
    )


def _build_presenter_with_overlay_and_subplot_scripts(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    script_registry = IndicatorScriptRegistry()
    script_registry.register("test_script", _TestReferenceScript)
    script_registry.register("test_subplot", _TestSubplotScript)
    strategy_registry = StrategyRegistry()
    strategy_registry.register("fake_strategy", _FakeStrategy)
    return _build_presenter_with_registry(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        strategy_registry,
        request,
        script_registry=script_registry,
    )


def test_script_model_is_populated_from_registry_and_default_enabled_scripts_are_checked(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    presenter = _build_presenter_with_script(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )

    assert presenter._view_model.script_model.enabled_keys == ["test_script"]


def test_successful_run_draws_enabled_reference_script_lines_on_the_chart(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    presenter = _build_presenter_with_script(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )
    view_model = presenter._view_model
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    added_names = {call.args[0] for call in card.add_overlay_indicator.call_args_list}
    assert added_names == {"test_script:R"}
    updated_names = {call.args[0] for call in card.update_indicator_data.call_args_list}
    assert updated_names == {"test_script:R"}


def test_disabling_a_script_before_the_next_run_stops_it_from_drawing(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    """BOT-064's own "no retroactive effect" rule: enabled_keys is
    snapshotted at 'Chạy Backtest' click time, in `_start_backtest_run` —
    toggling the checkbox off before the NEXT run must take effect, exactly
    like the Dev Board checklist (TC-GAP-07)."""
    presenter = _build_presenter_with_script(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )
    view_model = presenter._view_model
    view_model.script_model.setEnabled(0, False)
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    card.add_overlay_indicator.assert_not_called()


def test_switching_to_equity_mode_hides_an_overlay_scripts_lines(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    """BOT-065: same bug BOT-060 already fixed for the strategy's own
    lines (test_switching_to_equity_mode_disables_and_hides_the_ema_overlay
    below), reproduced for BOT-064's script-picker lines — left plotted
    through a switch to Equity-solo mode, an overlay script drags
    pyqtgraph's auto-range onto price values, squashing the equity curve
    flat/invisible. Not a rare case: ema_20/50/100/200 are all
    default_enabled + overlay, so this is the very first thing a fresh
    Backtest screen hits switching to "Đường Vốn" once. A subplot script
    (RSI/MACD-shaped) doesn't share that plot, so it must stay visible —
    covered here too, not just the overlay case."""
    presenter = _build_presenter_with_overlay_and_subplot_scripts(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )
    view_model = presenter._view_model
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    card.set_indicator_visible = Mock()

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.EQUITY].click()
    qapp.processEvents()

    card.set_indicator_visible.assert_any_call("test_script:R", False)
    hidden_names = {call.args[0] for call in card.set_indicator_visible.call_args_list}
    assert "test_subplot:S" not in hidden_names
    card.set_indicator_visible.reset_mock()

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.OHLC].click()
    qapp.processEvents()

    card.set_indicator_visible.assert_any_call("test_script:R", True)


def test_dynamic_script_toggle_on_after_run_draws_on_chart_without_rerun(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    """BOT-095F: toggling an indicator script ON after a backtest run dynamically
    draws the curves without rerunning the simulation or marking config dirty."""
    presenter = _build_presenter_with_script(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )
    view_model = presenter._view_model
    view_model.script_model.setEnabled(0, False)
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    card.add_overlay_indicator.assert_not_called()
    assert not view_model.isConfigDirty
    mock_thread_mgr.reset_mock()

    # Now toggle the script ON dynamically
    view_model.script_model.setEnabled(0, True)

    added_names = {call.args[0] for call in card.add_overlay_indicator.call_args_list}
    assert added_names == {"test_script:R"}
    updated_names = {call.args[0] for call in card.update_indicator_data.call_args_list}
    assert updated_names == {"test_script:R"}

    # Must NOT re-submit backtest worker and must NOT dirty the toolbar config
    mock_thread_mgr.submit.assert_not_called()
    assert not view_model.isConfigDirty


def test_dynamic_script_toggle_off_after_run_removes_from_chart(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    """BOT-095F: toggling an indicator script OFF after a backtest run dynamically
    removes the curves from the chart."""
    presenter = _build_presenter_with_script(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )
    view_model = presenter._view_model
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.remove_indicator = Mock()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    # Toggle the script OFF dynamically
    view_model.script_model.setEnabled(0, False)

    card.remove_indicator.assert_called_with("test_script:R")
    assert "test_script" not in presenter._chart_script_runner.active
    assert not view_model.isConfigDirty


def test_dynamic_script_toggle_on_during_equity_mode_keeps_overlay_hidden(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    """BOT-095F + BOT-065: enabling an overlay script during Equity mode draws it hidden."""
    presenter = _build_presenter_with_script(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
    )
    view_model = presenter._view_model
    view_model.script_model.setEnabled(0, False)
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)
    card = presenter.view.chart_cards[0]

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.EQUITY].click()
    qapp.processEvents()

    card.set_indicator_visible = Mock()
    view_model.script_model.setEnabled(0, True)

    card.set_indicator_visible.assert_called_with("test_script:R", False)


def test_mode_buttons_switch_the_chart_mode_end_to_end(
    presenter, view_model, mock_dispatcher, qapp
):
    """Native QPushButton click -> BacktestChartControls signal -> Presenter
    slot -> View render, with no QML/ViewModel involved."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.EQUITY].click()
    qapp.processEvents()

    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type == LINE
    )
    assert presenter.view.chart_controls._trade_flags_check.isEnabled() is False
    assert presenter.view.chart_controls._ema_check.isEnabled() is False


def test_switching_to_equity_mode_disables_and_hides_the_ema_overlay(
    presenter, view_model, mock_dispatcher, qapp
):
    """Regression test (found by running the app): the 4 EMA overlay is
    price-scale, exactly like the Buy/Sell flags already handled — left
    plotted through a switch to Equity-solo mode, it stays on the same main
    plot as the equity curve and drags pyqtgraph's auto-range onto price
    values (tens of thousands), squashing the equity curve flat/invisible."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    presenter._on_ema_toggled = Mock()

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.EQUITY].click()
    qapp.processEvents()

    assert presenter.view.chart_controls._ema_check.isEnabled() is False
    presenter._on_ema_toggled.assert_called_once_with(False)
    presenter._on_ema_toggled.reset_mock()

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.OHLC].click()
    qapp.processEvents()

    assert presenter.view.chart_controls._ema_check.isEnabled() is True
    # The checkbox was never unchecked (only disabled) — back on a
    # price-scale mode, visibility is restored to match its own state.
    presenter._on_ema_toggled.assert_called_once_with(True)


def test_trade_flags_toggle_draws_and_clears_markers(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    card = presenter.view.chart_cards[0]

    presenter.view.set_trade_flags_visible(False)
    assert (
        card.chart_card.indicators._marker_layer._items.get("backtest_trades", []) == []
    )

    presenter.view.set_trade_flags_visible(True)
    marker_layer = card.chart_card.indicators._marker_layer
    # The business contract is that both trade events remain available.
    # Scene-item count is intentionally viewport-dependent (BOT-098A).
    assert marker_layer.stored_marker_count("backtest_trades") == 2
    assert marker_layer.active_marker_count("backtest_trades") > 0


# ---------------------------------------------------------------------------
# Trade Logs table (BOT-057)
# ---------------------------------------------------------------------------


def test_successful_run_populates_the_trade_log_first_page(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=25, win_count=15)
    )

    presenter._run_backtest(config)

    assert view_model.tradeLogTotalCount == 25
    assert view_model.tradeLogTotalPages == 2
    assert len(view_model.tradeLogRows) == 20  # PAGE_SIZE


def test_no_historical_data_clears_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert view_model.tradeLogRows == []
    assert view_model.tradeLogTotalCount == 0


def test_failed_run_clears_the_trade_log(presenter, view_model, mock_dispatcher):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")

    presenter._run_backtest(config)

    assert view_model.tradeLogRows == []
    assert view_model.tradeLogTotalCount == 0


def test_changing_the_filter_recomputes_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=10, win_count=3)
    )
    presenter._run_backtest(config)

    view_model.tradeLogFilter = "win"

    assert view_model.tradeLogTotalCount == 3


def test_changing_the_filter_resets_to_page_1(presenter, view_model, mock_dispatcher):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=25, win_count=25)
    )
    presenter._run_backtest(config)
    view_model.tradeLogCurrentPage = 2

    view_model.tradeLogFilter = "loss"  # narrows to 0 rows -> would strand page 2

    assert view_model.tradeLogCurrentPage == 1


def test_changing_the_search_text_recomputes_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=5, win_count=5)
    )
    presenter._run_backtest(config)

    view_model.tradeLogSearchText = "#3"

    assert view_model.tradeLogTotalCount == 1


def test_changing_the_current_page_recomputes_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=25, win_count=25)
    )
    presenter._run_backtest(config)

    view_model.tradeLogCurrentPage = 2

    assert len(view_model.tradeLogRows) == 5  # 25 - 20 on page 1


def test_export_writes_the_currently_filtered_trades(
    presenter, view_model, mock_dispatcher, tmp_path
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=10, win_count=4)
    )
    presenter._run_backtest(config)
    view_model.tradeLogFilter = "win"
    export_path = str(tmp_path / "export.csv")

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=(export_path, "CSV Files (*.csv)"),
    ):
        view_model.requestTradeLogExport()

    with open(export_path, encoding="utf-8") as f:
        # header + 4 winning trades.
        assert len(f.readlines()) == 5


def test_export_does_nothing_when_the_dialog_is_cancelled(
    presenter, view_model, mock_dispatcher, tmp_path
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=3, win_count=3)
    )
    presenter._run_backtest(config)

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=("", ""),
    ):
        view_model.requestTradeLogExport()  # must not raise


def test_export_does_nothing_when_there_are_no_trades_yet(presenter, view_model):
    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest."
        "backtest_presenter.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        view_model.requestTradeLogExport()

    mock_dialog.assert_not_called()


def test_qml_trade_log_filter_tab_click_updates_the_view_model(
    presenter, view_model, mock_dispatcher, qml_item, qapp
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=5, win_count=2)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    root = presenter.view.bottom_widget.rootObject()

    qml_item(root, "tabTradeLogFilter_win").clicked.emit()
    qapp.processEvents()

    assert view_model.tradeLogFilter == "win"
    assert view_model.tradeLogTotalCount == 2


def test_qml_trade_log_export_button_click_requests_export(
    presenter, view_model, mock_dispatcher, qml_item, qapp
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=3, win_count=3)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    root = presenter.view.bottom_widget.rootObject()

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=("", ""),
    ) as mock_dialog:
        qml_item(root, "btnTradeLogExport").clicked.emit()
        qapp.processEvents()

    mock_dialog.assert_called_once()


def test_qml_trade_log_search_field_updates_the_view_model(
    presenter, view_model, mock_dispatcher, qml_item, qapp
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=5, win_count=5)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    root = presenter.view.bottom_widget.rootObject()

    search_field = qml_item(root, "txtTradeLogSearch")
    search_field.setProperty("text", "#3")
    search_field.textEdited.emit()
    qapp.processEvents()

    assert view_model.tradeLogSearchText == "#3"
    assert view_model.tradeLogTotalCount == 1


def test_qml_trade_logs_document_loads_without_errors(presenter, qapp):
    qapp.processEvents()
    assert presenter.view.bottom_widget.errors() == []


def test_qml_clicking_a_trade_log_row_toggles_its_detail_section(
    presenter, view_model, mock_dispatcher, qml_item, qapp
):
    """BOT-045 §2.2: clicking the summary row expands/collapses the entry
    catalyst / exit execution / metadata block below it."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=3, win_count=3)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    root = presenter.view.bottom_widget.rootObject()

    assert qml_item(root, "detailTradeLog_1").property("visible") is False

    qml_item(root, "rowTradeLog_1").clicked.emit()
    qapp.processEvents()

    assert qml_item(root, "detailTradeLog_1").property("visible") is True

    qml_item(root, "rowTradeLog_1").clicked.emit()
    qapp.processEvents()

    assert qml_item(root, "detailTradeLog_1").property("visible") is False


def test_selected_currency_default_and_change(view_model):
    """Test selectedCurrency defaults to USD and emits signal on change."""
    assert view_model.selectedCurrency == Currency.USD
    assert view_model.currencyOptions == Currency.list_values()

    emitted = False

    def on_changed():
        nonlocal emitted
        emitted = True

    view_model.selectedCurrencyChanged.connect(on_changed)
    view_model.selectedCurrency = Currency.VND

    assert view_model.selectedCurrency == Currency.VND
    assert emitted is True


# ================================================================== #
# BOT-095B: DeclarativeStateMachine & Dirty Tracking Lifecycle Tests
# ================================================================== #


def test_fsm_initializes_with_declarative_state_machine(presenter):
    """Verify FSM is loaded from UI_TRANSITION_MATRIX and bound to ViewModel."""
    assert presenter.fsm is not None
    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert presenter._view_model.uiMode == BacktestUiState.IDLE.value
    assert presenter._view_model.isConfigDirty is False
    assert presenter._view_model.controlsEnabled is True
    assert presenter._view_model.configDiffSummary == ""
    assert presenter._view_model.lastRunSummary == ""


def test_run_backtest_dispatches_run_requested_and_updates_ui_mode(presenter):
    """Verify running backtest transitions FSM to RUNNING and disables toolbar controls."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.initialCapitalText = "10000"

    presenter._on_run_backtest()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert vm.uiMode == BacktestUiState.RUNNING.value
    assert vm.controlsEnabled is False
    assert vm.isConfigDirty is False


def test_backtest_succeeded_transitions_to_completed_and_snapshots_last_run_config(
    presenter,
):
    """Verify successful run transitions to COMPLETED, saves _last_run_config and summary."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert vm.uiMode == BacktestUiState.COMPLETED.value
    assert vm.controlsEnabled is True
    assert vm.isConfigDirty is False
    assert presenter._last_run_config is not None
    assert presenter._last_run_config.strategy_key == "fake_strategy"
    assert presenter._last_run_config.timeframe == TimeFrame.ONE_MINUTE
    assert "fake_strategy" in vm.lastRunSummary
    assert "1m" in vm.lastRunSummary


def test_dirty_tracking_detects_timeframe_change_after_completed(presenter):
    """Verify changing timeframe when COMPLETED transitions to CONFIG_DIRTY with diff summary."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert vm.isConfigDirty is False

    # User modifies timeframe in toolbar
    vm.selectedTimeframe = "5m"

    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY
    assert vm.uiMode == BacktestUiState.CONFIG_DIRTY.value
    assert vm.isConfigDirty is True
    assert vm.controlsEnabled is True
    assert "Khung thời gian (1m → 5m)" in vm.configDiffSummary


def test_dirty_tracking_restores_to_completed_when_input_reverted(presenter):
    """Verify reverting modified input returns FSM to COMPLETED and clears diff summary."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    # Change timeframe -> DIRTY
    vm.selectedTimeframe = "15m"
    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY
    assert vm.isConfigDirty is True

    # Revert timeframe back to 1m -> COMPLETED
    vm.selectedTimeframe = "1m"
    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert vm.uiMode == BacktestUiState.COMPLETED.value
    assert vm.isConfigDirty is False
    assert vm.configDiffSummary == ""


def test_dirty_tracking_detects_capital_and_strategy_changes(presenter):
    """Verify modifying capital or strategy updates diff summary and sets DIRTY."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    # Change initial capital
    vm.initialCapitalText = "50000"
    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY
    assert "Vốn (10,000 → 50,000)" in vm.configDiffSummary

    # Change strategy
    vm.selectedStrategyKey = "ema_strategy"
    assert "Chiến lược (fake_strategy → ema_strategy)" in vm.configDiffSummary


def test_running_from_dirty_state_clears_dirty_state_on_completion(presenter):
    """Verify executing run from CONFIG_DIRTY transitions to RUNNING and on success COMPLETED with new snapshot."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    # Modify timeframe
    vm.selectedTimeframe = "1h"
    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY

    # Click Run again
    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    # Succeeded
    presenter._on_backtest_succeeded(result)
    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert vm.isConfigDirty is False
    assert presenter._last_run_config.timeframe == TimeFrame.ONE_HOUR
    assert "1h" in vm.lastRunSummary


def test_empty_backtest_transitions_to_idle_with_sync_affordance(presenter):
    """Verify empty backtest (no historical data) transitions FSM to EMPTY_DATA and enables sync."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    cfg = presenter._get_current_config()
    presenter._on_backtest_empty("Chưa có dữ liệu lịch sử", cfg)

    assert presenter.fsm.current_state == BacktestUiState.EMPTY_DATA
    assert vm.uiMode == BacktestUiState.EMPTY_DATA.value
    assert vm.needsDataSync is True
    assert presenter._last_no_data_config == cfg


def test_failed_backtest_transitions_to_idle_with_error(presenter):
    """Verify failed backtest transitions FSM to ERROR and populates error message."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    presenter._on_backtest_failed("Connection timed out")

    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert vm.uiMode == BacktestUiState.ERROR.value
    assert "Connection timed out" in vm.resultText


def test_qml_stale_warning_banner_and_button_dirty_rendering(presenter, qml_item, qapp):
    """Verify QML TopPanel renders amber warning banner when isConfigDirty is True."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    qapp.processEvents()

    root = presenter.view.top_widget.rootObject()
    banner = qml_item(root, "backtestStaleWarningBanner")
    assert banner is not None
    assert banner.property("visible") is False

    # Modify timeframe -> CONFIG_DIRTY
    vm.selectedTimeframe = "5m"
    qapp.processEvents()

    assert banner.property("visible") is True
    btn_run = qml_item(root, "btnRunBacktest")
    assert btn_run is not None


# ================================================================== #
# BOT-095H: Action ownership & stale callback fencing
# ================================================================== #


def test_cancel_request_fences_callbacks_and_restores_idle(presenter, view_model):
    view_model.requestRun()
    action = presenter._active_action
    token = presenter._backtest_cancellation_token
    assert action is not None
    assert token is not None

    view_model.requestCancelBacktest()

    assert token.is_cancelled()
    assert presenter.fsm.current_state is BacktestUiState.CANCELLING
    assert presenter._active_action_outcome is BacktestActionOutcome.INVALIDATED

    presenter._on_backtest_cancelled_for_action(
        action.action_id, BacktestCancelled("full", 12, 100)
    )

    assert presenter.fsm.current_state is BacktestUiState.IDLE
    assert presenter._active_action_outcome is BacktestActionOutcome.CANCELLED
    assert "Đã hủy Backtest" in view_model.resultText


def test_cancel_restores_config_dirty_and_late_success_cannot_render(
    presenter, view_model
):
    view_model.requestRun()
    first_action = presenter._active_action
    assert first_action is not None
    presenter._on_backtest_succeeded_for_action(
        first_action.action_id, _make_result(with_trades=True)
    )
    view_model.selectedTimeframe = "5m"
    assert presenter.fsm.current_state is BacktestUiState.CONFIG_DIRTY

    view_model.requestRun()
    action = presenter._active_action
    assert action is not None
    view_model.requestCancelBacktest()

    # A success queued just before cancellation is a stale callback. It may
    # complete the cancellation transition, but it must not render new data.
    presenter._on_backtest_succeeded_for_action(
        action.action_id, _make_result(with_trades=False)
    )

    assert presenter.fsm.current_state is BacktestUiState.CONFIG_DIRTY
    assert presenter._active_action_outcome is BacktestActionOutcome.CANCELLED
    assert len(presenter._all_trades) == 1


def test_progress_updates_are_ignored_after_cancel(presenter, view_model):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None
    presenter._on_backtest_progress_for_action(action.action_id, "full", 50, 100, 2.0)
    assert view_model.backtestProgressPercent == 50.0

    view_model.requestCancelBacktest()
    presenter._on_backtest_progress_for_action(action.action_id, "full", 90, 100, 3.0)

    assert view_model.backtestProgressPercent == 50.0


def test_qml_run_button_requests_cancel_while_backtest_is_running(
    presenter, view_model, qml_item, qapp
):
    view_model.requestRun()
    root = presenter.view.top_widget.rootObject()
    run_button = qml_item(root, "btnRunBacktest")
    assert run_button is not None

    run_button.clicked.emit()
    qapp.processEvents()

    assert presenter.fsm.current_state is BacktestUiState.CANCELLING


def test_superseded_backtest_success_cannot_overwrite_the_new_action(
    presenter, view_model
):
    view_model.requestRun()
    first_action = presenter._active_action
    assert first_action is not None

    second_action = presenter._begin_action(
        BacktestActionKind.BACKTEST,
        presenter._get_current_config(),
        presenter.fsm.current_state,
    )

    presenter._on_backtest_succeeded_for_action(
        first_action.action_id, _make_result(with_trades=True)
    )

    assert presenter._active_action == second_action
    assert presenter._active_action_outcome is BacktestActionOutcome.PENDING
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert view_model.resultText == "Đang chạy backtest..."


def test_superseded_backtest_failure_cannot_overwrite_the_new_action(
    presenter, view_model
):
    view_model.requestRun()
    first_action = presenter._active_action
    assert first_action is not None

    second_action = presenter._begin_action(
        BacktestActionKind.BACKTEST,
        presenter._get_current_config(),
        presenter.fsm.current_state,
    )

    presenter._on_backtest_failed_for_action(first_action.action_id, "old failure")

    assert presenter._active_action == second_action
    assert presenter._active_action_outcome is BacktestActionOutcome.PENDING
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert view_model.resultText == "Đang chạy backtest..."


def test_success_after_failure_for_the_same_action_is_ignored(presenter, view_model):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None

    presenter._on_backtest_failed_for_action(action.action_id, "boom")
    presenter._on_backtest_succeeded_for_action(
        action.action_id, _make_result(with_trades=True)
    )

    assert presenter._active_action_outcome is BacktestActionOutcome.FAILED
    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert view_model.resultIsError is True
    assert "boom" in view_model.resultText


def test_invalidated_action_cannot_apply_a_late_success(presenter, view_model):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None

    presenter._invalidate_active_action()
    presenter._on_backtest_succeeded_for_action(
        action.action_id, _make_result(with_trades=True)
    )

    assert presenter._active_action_outcome is BacktestActionOutcome.INVALIDATED
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert view_model.resultText == "Đang chạy backtest..."


def test_invalidated_action_cannot_apply_a_late_failure(presenter, view_model):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None

    presenter._invalidate_active_action()
    presenter._on_backtest_failed_for_action(action.action_id, "late failure")

    assert presenter._active_action_outcome is BacktestActionOutcome.INVALIDATED
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert view_model.resultText == "Đang chạy backtest..."


def test_action_context_deep_copies_mutable_strategy_params(presenter):
    params = {"periods": [12, 26]}
    config = BacktestRunConfig(
        strategy_key="fake_strategy",
        timeframe=TimeFrame.ONE_MINUTE,
        initial_balance=10000.0,
        start_time=None,
        end_time=None,
        strategy_params=params,
    )

    action = presenter._begin_action(
        BacktestActionKind.BACKTEST, config, presenter.fsm.current_state
    )
    params["periods"].append(50)

    assert action.config.strategy_params == {"periods": [12, 26]}


def test_stale_sync_success_does_not_auto_submit_a_backtest(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    sync_action = presenter._active_action
    assert sync_action is not None
    assert sync_action.kind is BacktestActionKind.SYNC

    presenter._begin_action(
        BacktestActionKind.BACKTEST,
        presenter._get_current_config(),
        presenter.fsm.current_state,
    )
    mock_thread_mgr.reset_mock()

    presenter._on_sync_succeeded_for_action(sync_action.action_id)

    mock_thread_mgr.submit.assert_not_called()
    assert presenter._active_action is not None
    assert presenter._active_action.kind is BacktestActionKind.BACKTEST


# ================================================================== #
# BUG: resolve_time_range() missing 'now' argument regression (BOT-095B)
# Reproduces: "_on_backtest_succeeded: resolve_time_range() missing 1
# required positional argument: 'now'" from production log 2026-08-16.
# ================================================================== #


def test_get_current_config_does_not_raise_for_preset_time_ranges(presenter):
    """Regression: _get_current_config() called resolve_time_range(preset) without
    the required 'now: datetime' argument, crashing on every backtest success/failure
    callback via _on_config_input_changed -> _get_current_config.

    Reproduces: Exception in _on_backtest_succeeded:
        resolve_time_range() missing 1 required positional argument: 'now'
    """
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"

    presets_under_test = ["7d", "30d", "90d", "365d", "all"]
    for preset in presets_under_test:
        vm.timeRangePreset = preset
        # Must not raise TypeError — was crashing with missing 'now' arg
        config = presenter._get_current_config()
        assert config is not None, f"Expected config for preset={preset!r}"


def test_get_current_config_custom_preset_parses_dates(presenter):
    """Regression companion: CUSTOM preset path must also work without crash."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.timeRangePreset = "custom"
    vm.customStartText = "2026-01-01"
    vm.customEndText = "2026-06-30"

    config = presenter._get_current_config()
    assert config is not None


def test_on_backtest_succeeded_does_not_raise_for_preset_ranges(presenter):
    """Regression: _on_backtest_succeeded internally calls _get_current_config
    to snapshot _last_run_config and compute diff — must not crash for
    any non-CUSTOM preset selected in the toolbar when a run completes."""
    vm = presenter._view_model
    vm.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.timeRangePreset = "30d"  # A preset that requires 'now' in resolve_time_range

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    # Must not raise — was crashing with "missing 1 required positional argument: 'now'"
    result = _make_result(with_trades=False)
    presenter._on_backtest_succeeded(result)

    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert presenter._last_run_config is not None


# --------------------------------------------------------------------------
# BOT-098F6D: post-construction native snapshot rejection must fall back to
# the Python host, not silently leave the chart blank (acceptance criterion
# 3). NativeBacktestChartHost is faked here; only the presenter/view fallback
# wiring is under test.
# --------------------------------------------------------------------------

_NATIVE_HOST_TARGET = (
    "Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic."
    "native_backtest_chart_adapter.NativeBacktestChartHost"
)


def _rejecting_native_host_factory():
    """A fake NativeBacktestChartHost whose submit_ohlcv() always reports a
    rejected snapshot — the adapter turns that into NativeUnsupportedFeatureError,
    which the presenter must catch and recover from."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
        ChartCard,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
        NativeBacktestChartHost,
    )

    fake = Mock(spec=NativeBacktestChartHost)
    fake.widget = ChartCard("placeholder")
    fake.submit_ohlcv.return_value = False
    return fake


def test_backtest_data_ready_falls_back_to_python_when_native_rejects_the_snapshot(
    presenter,
):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
        NativeBacktestChartHostAdapter,
    )

    presenter.view.set_chart_backend("native")
    with patch(
        f"{_NATIVE_HOST_TARGET}.create", side_effect=_rejecting_native_host_factory
    ):
        presenter.view.render_symbol_cards([presenter._symbol])
        assert isinstance(presenter.view.chart_cards[0], NativeBacktestChartHostAdapter)

        result = _make_result(with_trades=True)
        klines = [(1.0, 1.0, 2.0, 0.5, 1.5)]
        volume = [(1.0, 100.0, True)]
        presenter._on_chart_data_ready(result, klines, volume)

    # The rejected native snapshot must not leave the chart stuck blank —
    # the presenter rebuilds it with the Python host and re-renders.
    assert isinstance(presenter.view.chart_cards[0], PythonBacktestChartHost)


def test_preview_data_ready_falls_back_to_python_when_native_rejects_the_snapshot(
    presenter,
):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
        NativeBacktestChartHostAdapter,
    )

    presenter.view.set_chart_backend("native")
    with patch(
        f"{_NATIVE_HOST_TARGET}.create", side_effect=_rejecting_native_host_factory
    ):
        presenter.view.render_symbol_cards([presenter._symbol])
        assert isinstance(presenter.view.chart_cards[0], NativeBacktestChartHostAdapter)

        presenter._active_preview_id = 7
        klines = [(1.0, 1.0, 2.0, 0.5, 1.5)]
        volume = [(1.0, 100.0, True)]
        presenter._on_preview_data_ready(7, _complete_coverage(), klines, volume)

    assert isinstance(presenter.view.chart_cards[0], PythonBacktestChartHost)


# --------------------------------------------------------------------------
# Bug report (real run-ui.ps1 session, 2026-08-18): strategy indicator
# lines silently vanished after a chart-mode switch (Nến Nhật -> Đường Vốn ->
# Nến Nhật) while native backend was active, and the very next EMA-visibility
# toggle then crashed (swallowed silently by safe_ui_action outside dev
# mode). Root cause: BackTestView.set_chart_mode() rebuilds the chart host
# from scratch whenever the effective backend changes (BOT-098F6D), but
# BackTestPresenter kept believing its old _active_strategy_lines/
# IndicatorScriptRunner bookkeeping still applied to the brand new, empty
# host. Fix: BackTestPresenter now drops that stale bookkeeping the instant
# it learns a rebuild happened (set_chart_mode()'s new bool return) —
# re-running the backtest already redraws every line from scratch, exactly
# as it did before BOT-098F6D's mode-triggered rebuild existed.
# --------------------------------------------------------------------------


def test_switching_chart_mode_away_and_back_clears_stale_indicator_bookkeeping(
    presenter,
):
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
        ChartDisplayMode,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
        NativeBacktestChartHostAdapter,
    )

    presenter.view.set_chart_backend("native")
    with patch(
        f"{_NATIVE_HOST_TARGET}.create", side_effect=_rejecting_native_host_factory
    ):
        presenter.view.render_symbol_cards([presenter._symbol])

    # Ensure the fake native host actually accepts submissions for this
    # scenario (the "rejecting" factory is reused only for its widget
    # scaffolding here, not its rejection behavior).
    host = presenter.view.chart_cards[0]
    assert isinstance(host, NativeBacktestChartHostAdapter)
    host.native_host.submit_indicators.return_value = True

    presenter._on_chart_strategy_line("ema_9", "#F3BA2F", [1.0, 2.0], [10.0, 11.0])
    assert "ema_9" in presenter._active_strategy_lines
    assert "ema_9" in host._indicator_series

    # Must not raise — on native host, mode switching retains host and toggles indicators cleanly
    presenter._on_chart_mode_changed(ChartDisplayMode.EQUITY.value)
    assert host._indicator_visibility.get("ema_9") is False

    presenter._on_chart_mode_changed(ChartDisplayMode.OHLC.value)
    assert host._indicator_visibility.get("ema_9") is True
    assert presenter.view.chart_cards[0] is host


def test_presenter_constructs_with_auto_backend_by_default(
    qapp, mock_thread_mgr, mock_dispatcher, strategy_registry, request
):
    config = Mock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None: default

    container = Mock()

    def resolve_mock(interface):
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            return config
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == IndicatorScriptRegistry:
            return IndicatorScriptRegistry()
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    fake_native_host = Mock(spec=NativeBacktestChartHost)
    fake_native_host.widget = ChartCard("placeholder")

    with patch(f"{_NATIVE_HOST_TARGET}.create", return_value=fake_native_host):
        presenter = BackTestPresenter(view, container)
        assert presenter._view_model is not None
        assert isinstance(view.chart_cards[0], NativeBacktestChartHostAdapter)


# ---------------------------------------------------------------------------
# Market Metadata & Order Rule Validation (BOT-095E1)
# ---------------------------------------------------------------------------


def test_market_rule_verification_initial_unverified_when_cache_empty(
    presenter, view_model
):
    """BOT-095E1: Without cached exchange metadata, UI truthfully reports UNVERIFIED_MISSING."""
    assert (
        view_model.marketRuleVerificationStatus
        == MetadataVerificationStatus.UNVERIFIED_MISSING.value
    )
    assert "chưa có metadata" in view_model.marketRuleExplanation


def test_market_rule_verification_verified_when_metadata_cached(presenter, view_model):
    """BOT-095E1: When fresh exchange metadata is present, order intent is verified."""
    cache = InMemorySymbolMarketMetadataCache()
    metadata = SymbolMarketMetadata(
        symbol=presenter._symbol,
        status="TRADING",
        base_asset="ETH",
        quote_asset="USDT",
        price_filter=PriceFilter(100.0, 100000.0, 0.01),
        lot_size_filter=LotSizeFilter(0.0001, 100000.0, 0.0001),
        notional_filter=NotionalFilter(5.0, apply_to_market=True),
        fetched_at=datetime.now(UTC),
    )
    cache.put(metadata)
    presenter._market_metadata_cache = cache

    view_model.initialCapitalText = "15000"

    assert (
        view_model.marketRuleVerificationStatus
        == MetadataVerificationStatus.VERIFIED.value
    )
    assert "Đã xác minh theo quy tắc sàn Binance" in view_model.marketRuleExplanation


def test_market_rule_verification_stale_metadata_reported_truthfully(
    presenter, view_model
):
    """BOT-095E1: Stale metadata is flagged as UNVERIFIED_STALE without crashing simulation."""
    cache = InMemorySymbolMarketMetadataCache()
    stale_time = datetime.now(UTC) - timedelta(days=3)
    metadata = SymbolMarketMetadata(
        symbol=presenter._symbol,
        status="TRADING",
        base_asset="ETH",
        quote_asset="USDT",
        price_filter=PriceFilter(0.01, 100000.0, 0.01),
        lot_size_filter=LotSizeFilter(0.0001, 1000.0, 0.0001),
        notional_filter=NotionalFilter(5.0, apply_to_market=True),
        fetched_at=stale_time,
    )
    cache.put(metadata)
    presenter._market_metadata_cache = cache

    view_model.initialCapitalText = "5000"

    assert (
        view_model.marketRuleVerificationStatus
        == MetadataVerificationStatus.UNVERIFIED_STALE.value
    )
    assert "metadata cũ" in view_model.marketRuleExplanation
