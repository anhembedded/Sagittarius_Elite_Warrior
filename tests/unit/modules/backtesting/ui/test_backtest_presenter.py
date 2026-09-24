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
from PySide6.QtWidgets import QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest.command import (
    RunHistoricalTickBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import (
    BacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_report_loader import (
    load_backtest_report,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monte_carlo_simulation import (
    MonteCarloSimulationResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
    _FALLBACK_SYMBOL,
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_signal_payloads import (
    BacktestProgress,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestActionKind,
    BacktestActionOutcome,
    BacktestExecutionMode,
    BacktestRunConfig,
    BacktestUiEvent,
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
    ChartDisplayMode,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    LotSizeFilter,
    MetadataVerificationStatus,
    NotionalFilter,
    PriceFilter,
    SymbolMarketMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_metadata_provider import (
    FakeSymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    TREND_ZONE_DOWN,
    TREND_ZONE_UP,
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_type_renderer import (
    CANDLESTICK,
    LINE,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.ema import EMA
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


class _TrendZoneStrategy(BaseStrategy):
    """BOT-113 — classifies purely off `close_price` (no indicator-value
    dependency), so it stays deterministic against `_make_klines()`'s bare
    close ramp without needing a hand-verified EMA sequence."""

    def build_indicators(self):
        return {"ema_fast": EMA(1)}

    def decide(self, context):
        return self.hold()

    def classify_trend_zone(self, context):
        if context.candle.close_price >= 103.0:
            return TREND_ZONE_UP
        return TREND_ZONE_DOWN


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
        self.threshold = self.input_float(
            "threshold", 1.5, label="Threshold", minval=0.0
        )

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
    market_data_sync: FakeMarketDataSync | None = None,
    historical_klines: FakeHistoricalKlines | None = None,
) -> BackTestPresenter:
    """Same wiring as the `mock_container`/`presenter` fixtures, but with a
    caller-supplied `StrategyRegistry` — used by the bot-params tests that
    need more than the shared fixture's single zero-param `_FakeStrategy`.
    `script_registry` (BOT-064) defaults to a fresh empty one, same as the
    shared `indicator_script_registry` fixture."""

    container = Mock()
    resolved_script_registry = script_registry or IndicatorScriptRegistry()
    resolved_sync = market_data_sync or FakeMarketDataSync()
    resolved_history = historical_klines or FakeHistoricalKlines()
    resolved_catalog = FakeSymbolCatalog()
    resolved_coverage = FakeRangeCoverage()

    def resolve_mock(interface):
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            return mock_config
        if interface == StrategyRegistry:
            return registry
        if interface == IStrategyCatalog:
            return StrategyCatalogService(registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(registry)
        if interface == IndicatorScriptRegistry:
            return resolved_script_registry
        if interface == IHistoricalKlines:
            return resolved_history
        if interface == IRangeCoverage:
            return resolved_coverage
        if interface == ISymbolCatalog:
            return resolved_catalog
        if interface == IMarketDataSync:
            return resolved_sync
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
        from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import (
            Trade,
        )

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
    from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade

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
    *,
    realtime: bool = False,
):
    """Answers the one backtest command `_run_backtest` dispatches.

    It used to answer two things — the `BacktestResult` and the chart's
    klines — because both went through the dispatcher and a single
    `mock.return_value` cannot tell them apart. `EPIC-025` PR 1.1 moved the
    klines read onto `IHistoricalKlines`, so a test that needs candles seeds
    the `fake_historical_klines` fixture instead of teaching this stub about a
    query. The `klines=` parameter is gone rather than ignored: a stub that
    silently accepts data it no longer uses is how a test starts asserting
    nothing.

    `realtime=True` answers `RunHistoricalTickBacktestCommand` instead of
    `RunStaticBacktestCommand` (BOT-076 §3.3) — a test must pick the one that
    matches the config's `execution_mode`, since `_run_backtest` dispatches
    exactly one of the two, never both."""

    def side_effect(handler_class, command):
        if not realtime and handler_class is RunStaticBacktestCommand:
            return result
        if realtime and handler_class is RunHistoricalTickBacktestCommand:
            return result
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
        return default

    config.get.side_effect = get_config
    return config


@pytest.fixture
def fake_range_coverage():
    """`EPIC-025` PR 1.2 — the screen probes coverage through
    `IRangeCoverage`, so the container hands out the port's verified fake and
    a test reads the range the screen asked about."""
    return FakeRangeCoverage()


@pytest.fixture
def fake_symbol_catalog():
    """`EPIC-025` PR 1.2 — the symbol picker reads `ISymbolCatalog`, so the
    container hands out the port's verified fake and a test can assert the
    symbols that reached the screen."""
    return FakeSymbolCatalog()


@pytest.fixture
def fake_historical_klines():
    """`EPIC-025` PR 1.1 — the screen reads stored candles through
    `IHistoricalKlines`. The container hands out the port's verified fake, so a
    test can seed candles and assert what the screen drew, where a `MagicMock`
    could only confirm that something was called."""
    return FakeHistoricalKlines()


@pytest.fixture
def fake_market_data_sync():
    """`EPIC-025` PR 0.5 — Backtest asks market_data for a sync through
    `IMarketDataSync`, so the container hands out the port's verified fake.
    The tests below then read *what was asked for* (which start time, which
    end boundary) instead of unpacking a dispatched command."""
    return FakeMarketDataSync()


@pytest.fixture
def mock_container(
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    strategy_registry,
    indicator_script_registry,
    fake_market_data_sync,
    fake_historical_klines,
    fake_symbol_catalog,
    fake_range_coverage,
):
    container = Mock()

    def resolve_mock(interface):

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            return mock_config
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == IStrategyCatalog:
            return StrategyCatalogService(strategy_registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(strategy_registry)
        if interface == IndicatorScriptRegistry:
            return indicator_script_registry
        if interface == IHistoricalKlines:
            return fake_historical_klines
        if interface == IRangeCoverage:
            return fake_range_coverage
        if interface == ISymbolCatalog:
            return fake_symbol_catalog
        if interface == IMarketDataSync:
            return fake_market_data_sync
        # `BUG-127` — named, not left to the `Mock()` below. The real cache is
        # in-memory and free, so `CS-001`'s rule says use it: a `Mock` would
        # answer a truthy object from `get()` and a truthy `is_stale()`, which
        # would silently move every market-rule assertion in this file from
        # UNVERIFIED_MISSING to UNVERIFIED_STALE. The `Mock()` fallthrough is
        # itself what let `BUG-125` ship, so a new port gets a row here.
        if interface == ISymbolMarketMetadataCache:
            return InMemorySymbolMarketMetadataCache()
        if interface == ISymbolMetadataProvider:
            return FakeSymbolMetadataProvider()
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
# Timeframe pin preferences wiring (EPIC-015 Phase 4 follow-up)
# ---------------------------------------------------------------------------


def test_boot_falls_back_to_an_unpersisted_store_when_none_is_registered(
    presenter,
):
    """`mock_container` (every test above using the `presenter` fixture)
    never registers `TimeframePinPreferences` — `container.registrations()`
    on a bare `Mock` returns another `Mock`, not a `Mapping`, so
    `find_timeframe_pin_preferences` must treat that as "nothing
    registered" and the View must still end up with a working, private
    store rather than crashing `boot()`."""
    assert isinstance(
        presenter.view._timeframe_pin_preferences, TimeframePinPreferences
    )


def test_boot_wires_the_container_registered_store_into_the_view(
    qapp,
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    strategy_registry,
    indicator_script_registry,
    request,
):
    """When the container *does* have a registered store — the real
    `app_bootstrapper.py` shape — `boot()` must hand the View that exact
    instance, not a fresh fallback, so Backtest's chart reads/writes the
    same persisted, per-symbol pins Dev Board would."""
    shared_store = TimeframePinPreferences()
    container = Mock()
    container.registrations.return_value = {TimeframePinPreferences: shared_store}

    def resolve_mock(interface):
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            return mock_config
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == IStrategyCatalog:
            return StrategyCatalogService(strategy_registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(strategy_registry)
        if interface == IndicatorScriptRegistry:
            return indicator_script_registry
        if interface == TimeframePinPreferences:
            return shared_store
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = BackTestView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)

    BackTestPresenter(view, container)

    assert view._timeframe_pin_preferences is shared_store


# ---------------------------------------------------------------------------
# Strategy options
# ---------------------------------------------------------------------------


def test_strategy_options_loaded_from_registry_on_init(view_model):
    assert view_model.strategy_params.strategyOptions == [
        {
            "key": "fake_strategy",
            "name": "Fake Strategy",
            "category": "",
            "description": "",
        }
    ]
    assert view_model.strategy_params.selectedStrategyKey == "fake_strategy"


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

    mock_thread_mgr.submit.assert_called_once_with(
        presenter._symbol_options_coordinator._fetch
    )


def test_opening_symbol_picker_again_does_not_refetch_when_already_cached(
    presenter, mock_thread_mgr
):
    presenter._symbol_options_coordinator.on_options_ready(["BTCUSDT", "ETHUSDT"])

    presenter._on_symbol_picker_open_requested()

    mock_thread_mgr.submit.assert_not_called()


def test_fetch_symbol_options_reads_the_catalog_and_populates_the_view_model(
    presenter, view_model, fake_symbol_catalog
):
    """`EPIC-025` PR 1.2 — read off the port. The old version asserted the
    dispatched query's *type* and then that the view model held the list the
    test itself had put in the mock; this asserts the symbols the picker
    shows came from the module."""
    fake_symbol_catalog.seed(["ETHUSDT", "BTCUSDT"])

    presenter._symbol_options_coordinator._fetch()

    assert fake_symbol_catalog.reads == [False]
    assert view_model.symbolOptions == ["BTCUSDT", "ETHUSDT"]


def test_fetch_symbol_options_failure_does_not_cache_and_logs_without_crashing(
    presenter, view_model
):
    def unreachable(*_args, **_kwargs):
        raise RuntimeError("exchange unreachable")

    presenter._symbol_options_coordinator._symbol_catalog.list_symbols = unreachable

    presenter._symbol_options_coordinator._fetch()

    assert presenter._symbol_options_coordinator._symbol_options_cache is None
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
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
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
    qapp,
    mock_container,
    mock_config,
    mock_dispatcher,
    request,
    fake_historical_klines,
):
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": ["BTCUSDT"]}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    presenter = BackTestPresenter(view, mock_container)
    view_model = presenter._view_model
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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


def test_historical_tick_mode_dispatches_run_historical_tick_backtest_command(
    presenter, view_model, mock_dispatcher
):
    """The one thing BOT-074 explicitly left undone: unlocking the QML row
    means nothing if the Presenter still always builds a
    RunStaticBacktestCommand underneath it."""
    view_model.executionMode = "HISTORICAL_TICK"
    # Tick mode rejects the ALL_HISTORY default (unbounded start_time) -
    # see TickModeRequiresBoundedRangeRule.
    view_model.time_range.preset = "7d"
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), realtime=True
    )

    config = _lock_and_get_config(presenter, view_model)
    assert config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK
    presenter._run_backtest(config)

    dispatched_handlers = [
        call[0][0] for call in mock_dispatcher.dispatch.call_args_list
    ]
    assert RunHistoricalTickBacktestCommand in dispatched_handlers
    assert RunStaticBacktestCommand not in dispatched_handlers

    realtime_call = next(
        call
        for call in mock_dispatcher.dispatch.call_args_list
        if call[0][0] is RunHistoricalTickBacktestCommand
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
    assert RunHistoricalTickBacktestCommand not in dispatched_handlers


def test_result_message_labels_realtime_vs_static_truthfully(
    presenter, view_model, mock_dispatcher
):
    """The two engines are allowed to disagree on the same data (BOT-076
    §5) — a result with no mode label is exactly the "looks identical, means
    something different" trap the task's own §3.3 checklist calls out."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"

    view_model.executionMode = "HISTORICAL_TICK"
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    # No picker exists yet (BOT-076 §3.3 scope) — BacktestRunConfig.tick_resolution
    # always defaults to 1s, so that is the value a truthful label must show.
    assert "Realtime" in view_model.run_result.resultText
    assert "tick 1s" in view_model.run_result.resultText

    view_model.executionMode = "BAR_CLOSE"
    presenter._on_backtest_succeeded(result)
    assert "Static" in view_model.run_result.resultText


def test_probe_data_coverage_checks_tick_resolution_for_realtime_mode(
    presenter, view_model, fake_range_coverage
):
    """BOT-076's read asks `IMarketDataRepository` at tick_resolution (e.g.
    1s), never at the strategy interval (e.g. 5m) — checking coverage for the
    wrong one would report "fully covered" while the interval actually read
    was never synced at all.

    `EPIC-025` PR 1.2 — read off `IRangeCoverage`'s own record. The old
    version compared `query.interval` against `config.tick_resolution.value`,
    two strings; the port carries a `TimeFrame`, so the comparison is now
    between the values the screen actually holds.
    """
    view_model.executionMode = "HISTORICAL_TICK"
    view_model.time_range.preset = "7d"
    config = _lock_and_get_config(presenter, view_model)

    presenter._probe_data_coverage(config)

    request = fake_range_coverage.requests[0]
    assert request.interval == config.tick_resolution
    assert request.interval != config.timeframe


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
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter.datetime",
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
    assert view_model.run_result.resultIsError is True
    assert presenter.fsm.current_state == BacktestUiState.IDLE


def test_non_positive_capital_is_rejected(presenter, view_model, mock_thread_mgr):
    view_model.initialCapitalText = "0"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.run_result.resultIsError is True


def test_custom_range_with_invalid_start_is_rejected(
    presenter, view_model, mock_thread_mgr
):
    view_model.time_range.preset = "custom"
    view_model.time_range.customStartText = "not-a-date"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.run_result.resultIsError is True


def test_custom_range_start_after_end_is_rejected(
    presenter, view_model, mock_thread_mgr
):
    view_model.time_range.preset = "custom"
    view_model.time_range.customStartText = "2026-06-01 00:00"
    view_model.time_range.customEndText = "2026-01-01 00:00"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.run_result.resultIsError is True


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
    assert view_model.run_result.resultIsError is False
    assert "ETHUSDT" in view_model.run_result.resultText
    assert "Closed trades: 1" in view_model.run_result.resultText
    assert len(view_model.run_result.primaryStatCards) == 4
    assert (
        len(view_model.run_result.extendedStatCards) == 15
    )  # BOT-106A: +6 risk metrics
    assert (
        view_model.run_result.resultWarningText == ""
    )  # no fee/frequency flags on this result
    assert len(view_model.run_result.limitations) > 0  # BOT-081


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

    assert view_model.run_result.resultWarningText != ""
    assert "Fees account for a large share" in view_model.run_result.resultWarningText


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

    assert view_model.run_result.resultWarningText != ""
    assert "overfit" in view_model.run_result.resultWarningText
    # `BOT-107A`: the two flat-grid extended cards for these same numbers
    # were removed once `OutOfSampleComparisonDialog` shipped a real
    # side-by-side table — showing both would duplicate the figures.
    titles = {card["title"] for card in view_model.run_result.extendedStatCards}
    assert "In-Sample Net Profit" not in titles
    assert "Out-of-Sample Net Profit" not in titles


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

    joined = " ".join(view_model.run_result.limitations)
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

    assert not any(
        "out-of-sample" in note for note in view_model.run_result.limitations
    )


def test_successful_run_with_out_of_sample_validation_draws_the_divider_at_the_split(
    presenter, view_model, mock_dispatcher
):
    """`BOT-107A` — the chart's In-Sample/Out-of-Sample split line is drawn
    at the in-sample half's own last equity-curve point, exactly where the
    out-of-sample half begins."""
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

    divider = presenter.view.chart_cards[0].chart_card.out_of_sample_divider
    assert divider._line.isVisible()
    assert divider._line.value() == result.equity_curve[-1][0].timestamp()


def test_successful_run_without_out_of_sample_validation_clears_a_stale_divider(
    presenter, view_model, mock_dispatcher
):
    """Mutation check: a run with no split must clear whatever divider an
    earlier run in the same session drew — never leave a stale one showing
    a boundary that has nothing to do with the result now on screen."""
    config = _lock_and_get_config(presenter, view_model)
    split_result = _make_result(with_trades=True)
    split_result = replace(
        split_result,
        out_of_sample=OutOfSampleValidation(
            in_sample=split_result, out_of_sample=split_result, in_sample_ratio=0.7
        ),
    )
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(split_result)
    presenter._run_backtest(config)
    divider = presenter.view.chart_cards[0].chart_card.out_of_sample_divider
    assert divider._line.isVisible()

    config = _lock_and_get_config(presenter, view_model)
    unsplit_result = _make_result(with_trades=True)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(unsplit_result)
    presenter._run_backtest(config)

    assert not divider._line.isVisible()


def test_backtest_empty_clears_the_out_of_sample_divider(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    split_result = _make_result(with_trades=True)
    split_result = replace(
        split_result,
        out_of_sample=OutOfSampleValidation(
            in_sample=split_result, out_of_sample=split_result, in_sample_ratio=0.7
        ),
    )
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(split_result)
    presenter._run_backtest(config)
    divider = presenter.view.chart_cards[0].chart_card.out_of_sample_divider
    assert divider._line.isVisible()

    presenter._on_backtest_empty("No historical data", config)

    assert not divider._line.isVisible()


def test_backtest_failed_clears_the_out_of_sample_divider(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    split_result = _make_result(with_trades=True)
    split_result = replace(
        split_result,
        out_of_sample=OutOfSampleValidation(
            in_sample=split_result, out_of_sample=split_result, in_sample_ratio=0.7
        ),
    )
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(split_result)
    presenter._run_backtest(config)
    divider = presenter.view.chart_cards[0].chart_card.out_of_sample_divider
    assert divider._line.isVisible()

    presenter._on_backtest_failed("boom")

    assert not divider._line.isVisible()


# ---------------------------------------------------------------------------
# BOT-107B — Monte Carlo simulation dispatch and result fencing
# ---------------------------------------------------------------------------


def test_run_monte_carlo_requested_dispatches_the_current_results_trades(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)
    presenter._run_backtest(config)
    # `_lock_and_get_config()`'s own `requestRun()` already submitted the
    # backtest run itself — reset so the assertion below is about the
    # Monte Carlo dispatch specifically, not that earlier, unrelated call.
    mock_thread_mgr.submit.reset_mock()

    presenter._on_run_monte_carlo_requested(5000)

    mock_thread_mgr.submit.assert_called_once()
    args = mock_thread_mgr.submit.call_args.args
    assert args[0] == presenter._monte_carlo._run_worker
    assert args[1] == result.trades
    assert args[2] == result.initial_balance
    assert args[3] == 5000
    assert args[4] == presenter._active_monte_carlo_run_id


def test_run_monte_carlo_requested_does_nothing_without_a_completed_run(
    presenter, mock_thread_mgr
):
    presenter._on_run_monte_carlo_requested(5000)

    mock_thread_mgr.submit.assert_not_called()


def test_monte_carlo_completed_stores_the_result_on_the_view_model(
    presenter, view_model
):
    run_id = presenter._claim_monte_carlo_run_id()
    result = MonteCarloSimulationResult(
        iterations=1000,
        median_return_percent=5.0,
        p95_max_drawdown_percent=10.0,
        p99_max_drawdown_percent=15.0,
        risk_of_ruin_50_percent=0.0,
        risk_of_ruin_100_percent=0.0,
        max_drawdowns_percent=(1.0, 2.0),
        sample_equity_curves=((1000.0, 1050.0),),
    )

    presenter._on_monte_carlo_completed(run_id, result)

    assert view_model.run_result.monte_carlo_result() is result


def test_a_stale_monte_carlo_completion_is_ignored(presenter, view_model):
    """Mutation check: without the run-id fence, a slow first simulation
    completing after a second, faster one would silently overwrite the
    newer, still-correct result with a stale one."""
    stale_run_id = presenter._claim_monte_carlo_run_id()
    current_run_id = presenter._claim_monte_carlo_run_id()
    current_result = MonteCarloSimulationResult(
        iterations=1000,
        median_return_percent=5.0,
        p95_max_drawdown_percent=10.0,
        p99_max_drawdown_percent=15.0,
        risk_of_ruin_50_percent=0.0,
        risk_of_ruin_100_percent=0.0,
        max_drawdowns_percent=(1.0,),
        sample_equity_curves=(),
    )
    presenter._on_monte_carlo_completed(current_run_id, current_result)

    stale_result = MonteCarloSimulationResult(
        iterations=2000,
        median_return_percent=99.0,
        p95_max_drawdown_percent=99.0,
        p99_max_drawdown_percent=99.0,
        risk_of_ruin_50_percent=99.0,
        risk_of_ruin_100_percent=99.0,
        max_drawdowns_percent=(99.0,),
        sample_equity_curves=(),
    )
    presenter._on_monte_carlo_completed(stale_run_id, stale_result)

    assert view_model.run_result.monte_carlo_result() is current_result


def test_a_new_backtest_run_invalidates_an_in_flight_monte_carlo_run(
    presenter, view_model, mock_dispatcher
):
    """Should-fix from PR #265's independent review: a new backtest run
    makes any in-flight Monte Carlo worker's eventual result stale (it was
    computed from the PREVIOUS run's trades), the exact same way it already
    fences a stale chart-preview callback via `_active_preview_id = 0` in
    `_start_backtest_run()`. Mutation-verified: removing the
    `_active_monte_carlo_run_id = 0` line there makes this fail — the
    "stale" result silently resurrects instead of staying cleared."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)
    stale_run_id = presenter._claim_monte_carlo_run_id()

    second_config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(second_config)

    stale_result = MonteCarloSimulationResult(
        iterations=5000,
        median_return_percent=99.0,
        p95_max_drawdown_percent=99.0,
        p99_max_drawdown_percent=99.0,
        risk_of_ruin_50_percent=99.0,
        risk_of_ruin_100_percent=99.0,
        max_drawdowns_percent=(99.0,),
        sample_equity_curves=(),
    )
    presenter._on_monte_carlo_completed(stale_run_id, stale_result)

    assert view_model.run_result.monte_carlo_result() is None


def test_monte_carlo_failed_stores_the_error_message(presenter, view_model):
    run_id = presenter._claim_monte_carlo_run_id()

    presenter._on_monte_carlo_failed(run_id, "boom")

    assert view_model.run_result.monte_carlo_error() == "boom"


def test_a_stale_monte_carlo_failure_is_ignored(presenter, view_model):
    stale_run_id = presenter._claim_monte_carlo_run_id()
    presenter._claim_monte_carlo_run_id()

    presenter._on_monte_carlo_failed(stale_run_id, "boom")

    assert view_model.run_result.monte_carlo_error() == ""


def test_the_full_dispatch_to_completion_path_reaches_the_view_model(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    """End-to-end (not just each half in isolation): a real `submit()` call
    that actually runs the task, same as the thread pool would, all the
    way through `MonteCarloCoordinator`'s real domain call and back onto
    the real `_monteCarloCompletedSignal`."""
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)
    presenter._run_backtest(config)
    # Only now, so the backtest run above still goes through this test's
    # own direct `_run_backtest()` call rather than being double-invoked by
    # `_lock_and_get_config()`'s own `requestRun()` submit.
    mock_thread_mgr.submit.side_effect = lambda fn, *a, **kw: fn(*a, **kw)

    presenter._on_run_monte_carlo_requested(1000)

    stored = view_model.run_result.monte_carlo_result()
    assert stored is not None
    assert stored.iterations == 1000


def test_no_historical_data_clears_limitations(presenter, view_model, mock_dispatcher):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert view_model.run_result.limitations == []


def test_qml_limitations_button_opens_without_crashing(
    presenter, view_model, qapp, mock_dispatcher
):
    """BOT-081: the info icon must be a real, clickable button."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)
    qapp.processEvents()

    presenter.view.top_widget._btn_limitations.click()
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
    assert view_model.run_result.resultIsError is False
    assert "No historical data" in view_model.run_result.resultText
    # BOT-059: "no data at all" is exactly the case "Đồng bộ ngay" exists for.
    assert view_model.run_result.needsDataSync is True
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
    assert view_model.run_result.resultIsError is False
    assert "no trades in the selected" in view_model.run_result.resultText
    assert "Closed trades: 0" in view_model.run_result.resultText
    # BOT-055: 0 trades still populates the 4 cards (all reading 0), not an
    # empty panel — only "no historical data at all" clears it.
    assert len(view_model.run_result.primaryStatCards) == 4
    # BOT-059: 0 trades is a real result, not "no data" — must not offer sync.
    assert view_model.run_result.needsDataSync is False


def test_dispatch_exception_reports_error_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert view_model.run_result.resultIsError is True
    assert "boom" in view_model.run_result.resultText


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
    assert view_model.run_result.needsDataSync is True
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
    assert "Missing candles" in view_model.run_result.resultText
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

    assert view_model.run_progress.syncProgressPercent == 45.0
    assert "45/100" in view_model.run_progress.syncProgressText
    presenter._finish_action(sync_action.action_id, BacktestActionOutcome.INVALIDATED)
    presenter._on_sync_progress_for_action(sync_action.action_id, 90, 100)
    assert view_model.run_progress.syncProgressPercent == 45.0


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

    `EPIC-015` Phase 4: `ChartToolbar` is QML-hosted now
    (`TimeframeToolbar.qml`) — this intentionally drives it through its
    `TimeframeVM` (`_vm.choose()`, the same call a real pill click makes)
    rather than a QtWidgets `QPushButton`, keeping the original intent: a
    highlighted pill without a new ViewModel timeframe/preview is a
    user-visible no-op, not a successful interaction.
    """
    mock_thread_mgr.reset_mock()
    toolbar = presenter.view.chart_cards[0].chart_card.toolbar

    toolbar._selection.choose("5m")

    assert view_model.selectedTimeframe == "5m"
    worker, config, preview_id = mock_thread_mgr.submit.call_args.args
    assert worker == presenter._run_chart_preview
    assert config.timeframe is TimeFrame.FIVE_MINUTES
    assert preview_id == presenter._active_preview_id


def test_qml_timeframe_selection_keeps_chart_toolbar_in_sync(presenter, view_model):
    """The QML picker and chart header are one selected-timeframe contract."""
    toolbar = presenter.view.chart_cards[0].chart_card.toolbar

    view_model.selectedTimeframe = "15m"

    assert toolbar._selection.current_code == "15m"


def test_preview_result_updates_coverage_and_chart_but_stale_result_is_fenced(
    presenter, view_model
):
    presenter.view.on_preview_data_ready = Mock()
    presenter._active_preview_id = 2

    presenter._on_preview_data_ready(1, _missing_coverage(), ["old"], [])
    presenter.view.on_preview_data_ready.assert_not_called()

    presenter._on_preview_data_ready(2, _complete_coverage(), ["new"], ["volume"])

    assert view_model.run_result.isDataFullyCovered is True
    assert view_model.run_result.needsDataSync is False
    presenter.view.on_preview_data_ready.assert_called_once_with(["new"], ["volume"])


def test_chart_preview_flag_distinguishes_preview_from_real_backtest_result(
    presenter, view_model
):
    """BUG-032: opening the screen / changing symbol renders real candles via
    `_request_chart_preview()` through the exact same `render_historical_data`
    call a completed backtest uses — nothing told the user the chart was only
    a preview. `isChartPreview` must be True after a preview render and flip
    back to False only once a real `BacktestResult` chart renders."""
    presenter._active_preview_id = 3
    klines = [(1.0, 1.0, 2.0, 0.5, 1.5)]
    volume = [(1.0, 100.0, True)]

    presenter._on_preview_data_ready(3, _complete_coverage(), klines, volume)

    assert view_model.isChartPreview is True

    result = _make_result(with_trades=True)
    presenter._on_chart_data_ready(result, klines, volume)

    assert view_model.isChartPreview is False


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


def test_run_sync_asks_the_market_data_port_for_the_no_data_config(
    presenter, view_model, mock_dispatcher, fake_market_data_sync
):
    """`EPIC-025` PR 0.5: the sync is a call on `IMarketDataSync`, so the
    dispatcher now sees only the coverage re-probe that follows it."""
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_dispatcher.dispatch.side_effect = [_complete_coverage()]

    presenter._run_sync(config)

    request = fake_market_data_sync.requests[0]
    assert request.symbols == (presenter._symbol,)
    assert request.interval == config.timeframe


def test_run_sync_fetches_one_interval_past_the_frozen_probe_boundary(
    presenter, mock_dispatcher, fake_market_data_sync
):
    end_time = datetime(2026, 8, 17, 4, 47, 15, tzinfo=UTC)
    config = replace(presenter._get_current_config(), end_time=end_time)
    action = presenter._begin_action(
        BacktestActionKind.SYNC, config, BacktestUiState.EMPTY_DATA
    )
    mock_dispatcher.dispatch.side_effect = [_complete_coverage()]

    presenter._run_sync(action.config, action.action_id)

    assert fake_market_data_sync.requests[0].end_time == end_time + timedelta(minutes=1)


def test_run_sync_resumes_from_the_coverage_gap_not_the_full_requested_range(
    presenter,
    view_model,
    mock_dispatcher,
    mock_thread_mgr,
    caplog,
    fake_market_data_sync,
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
    mock_dispatcher.dispatch.side_effect = [_complete_coverage()]

    with caplog.at_level(logging.INFO, logger="App.BackTestPresenter"):
        presenter._on_backtest_coverage_missing_for_action(
            action.action_id, config, coverage, True
        )
        # Exercise exactly what was actually submitted to the thread pool —
        # not a hand-built call — so this proves the real wiring, not just a
        # plausible-looking call to _run_sync in isolation.
        submitted_args = mock_thread_mgr.submit.call_args[0][1:]
        presenter._run_sync(*submitted_args)

    request = fake_market_data_sync.requests[0]
    assert request.start_time == coverage.missing_open_times[0]
    assert request.start_time != requested_start
    # Log-proved: the decision (which start it resumed from and why) must be
    # findable in a real session's log, not just inferable from the outcome.
    resolved_lines = [
        r.message for r in caplog.records if "sync_start_resolved" in r.message
    ]
    assert len(resolved_lines) == 1
    assert "source=coverage_gap" in resolved_lines[0]


def test_run_sync_falls_back_to_the_requested_start_with_no_prior_coverage(
    presenter, view_model, mock_dispatcher, caplog, fake_market_data_sync
):
    """The cold-DB case (BUG-017's suggested-fix note): with no coverage
    probe result at all, the full requested range genuinely is missing, so
    falling back to `config.start_time` is correct, not a regression."""
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_dispatcher.dispatch.side_effect = [_complete_coverage()]

    with caplog.at_level(logging.INFO, logger="App.BackTestPresenter"):
        presenter._run_sync(config)

    assert fake_market_data_sync.requests[0].start_time == config.start_time
    resolved_lines = [
        r.message for r in caplog.records if "sync_start_resolved" in r.message
    ]
    assert len(resolved_lines) == 1
    assert "source=requested_range" in resolved_lines[0]


def test_sync_without_the_required_candle_reports_incomplete_and_keeps_retry_available(
    presenter, view_model, mock_dispatcher, mock_thread_mgr, fake_range_coverage
):
    """Regression: transport success is not data coverage success.

    The old flow logged "Đồng bộ dữ liệu thành công", restarted the backtest,
    then immediately emitted the same missing-candle error.  The user must get
    one truthful incomplete-sync result and retain the retry affordance.

    `EPIC-025` PR 1.2 — the re-probe after the sync reads `IRangeCoverage`,
    so the still-incomplete answer is scripted on the port rather than set as
    a dispatcher's return value.
    """
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    fake_range_coverage.answer_with(
        _missing_coverage(), symbol=config.symbol, interval=config.timeframe
    )

    presenter._run_sync(config)

    assert presenter.fsm.current_state is BacktestUiState.ERROR
    assert view_model.run_result.needsDataSync is True
    assert presenter._last_no_data_config == config
    assert "Sync is not sufficient" in view_model.run_result.resultText
    mock_thread_mgr.submit.assert_not_called()


def test_sync_success_clears_the_flag_and_auto_resubmits_the_backtest(
    presenter, view_model, mock_dispatcher, mock_thread_mgr, fake_range_coverage
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    # The worker verifies coverage after the sync, and `EPIC-025` PR 1.2 made
    # that a port call too — so the dispatcher has nothing left to answer
    # here. The resubmitted RunStaticBacktestCommand is never dispatched in
    # this test because mock_thread_mgr is a Mock, not a real thread pool.
    fake_range_coverage.answer_with(
        _complete_coverage(), symbol=config.symbol, interval=config.timeframe
    )

    presenter._run_sync(config)

    assert view_model.run_result.needsDataSync is False
    assert presenter._last_no_data_config is None
    # Auto-resubmitted straight into RUNNING, no click needed.
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_backtest


def test_sync_success_resubmits_with_its_original_config_snapshot(
    presenter, view_model, mock_dispatcher, mock_thread_mgr, fake_range_coverage
):
    """A sync success authorizes only the intent that created that sync.

    It must never infer a fresh action from live toolbar fields; a future
    editable-while-syncing flow must invalidate the old action instead.
    """
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    view_model.initialCapitalText = "500"
    mock_thread_mgr.reset_mock()
    # As above: both the sync and the coverage probe are port calls now.
    fake_range_coverage.answer_with(
        _complete_coverage(), symbol=config.symbol, interval=config.timeframe
    )

    presenter._run_sync(config)

    resubmitted_config = mock_thread_mgr.submit.call_args[0][1]
    assert resubmitted_config.initial_balance == config.initial_balance


def test_sync_failure_keeps_the_flag_and_returns_to_idle(
    presenter, view_model, mock_dispatcher, mock_thread_mgr, fake_market_data_sync
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()

    # The failure is the sync's now, not the dispatcher's: a network error
    # reaches this screen through the port it called.
    def _boom(_request):
        raise RuntimeError("sync boom")

    fake_market_data_sync.sync = _boom

    presenter._run_sync(config)

    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert view_model.run_result.needsDataSync is True
    assert presenter._last_no_data_config is config
    assert view_model.run_result.resultIsError is True
    assert "sync boom" in view_model.run_result.resultText
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
    assert "sync" in view_model.run_result.resultText.lower()


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
    assert "sync cancelled" in view_model.run_result.resultText.lower()


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
# `IRangeCoverage`'s SQL has no lower bound when start_time is
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
    assert view_model.time_range.preset == "all"  # the actual default, unchanged

    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.run_result.resultIsError is True
    assert "All History" in view_model.run_result.resultText
    mock_dispatcher.dispatch.assert_not_called()


def test_all_history_with_bar_close_mode_is_still_allowed(
    presenter, view_model, mock_dispatcher
):
    """The new rule is tick-mode-specific — Static backtests must keep
    being allowed to run over the full local history exactly as before."""
    assert view_model.executionMode == "BAR_CLOSE"
    assert view_model.time_range.preset == "all"
    mock_dispatcher.dispatch.return_value = None

    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING


def test_tick_mode_with_a_bounded_range_is_allowed(
    presenter, view_model, mock_dispatcher
):
    view_model.executionMode = "HISTORICAL_TICK"
    view_model.time_range.preset = "7d"
    mock_dispatcher.dispatch.return_value = None

    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING


def test_qml_sync_button_only_visible_after_no_data_and_click_requests_sync(
    presenter, view_model, mock_dispatcher, qapp, mock_thread_mgr
):
    qapp.processEvents()
    button = presenter.view.top_widget._btn_request_sync
    assert button.isVisible() is False

    _run_to_no_data(presenter, view_model, mock_dispatcher)
    qapp.processEvents()
    mock_thread_mgr.reset_mock()

    assert button.isVisible() is True
    button.click()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()
    assert mock_thread_mgr.submit.call_args[0][0] == presenter._run_sync


def test_qml_sync_button_retries_from_error_when_data_is_still_missing(
    presenter, view_model, mock_dispatcher, qapp, mock_thread_mgr
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
    button = presenter.view.top_widget._btn_request_sync

    assert presenter.fsm.current_state is BacktestUiState.ERROR
    assert button.isVisible() is True
    assert button.isEnabled() is True
    button.click()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()
    assert mock_thread_mgr.submit.call_args[0][0] == presenter._run_sync
    assert presenter.fsm.current_state is BacktestUiState.SYNCING


# ---------------------------------------------------------------------------
# Stat cards (BOT-055)
# ---------------------------------------------------------------------------


def test_a_metric_tile_is_rendered_per_primary_stat_card_after_a_run(
    presenter, view_model, qapp, mock_dispatcher
):
    """Renamed in `EPIC-025` PR 4.3g — the row is QtWidgets again, so "qml
    renders" was no longer what this test checks. The promise is unchanged:
    a completed run puts a tile on screen per primary figure."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)
    qapp.processEvents()

    top_widget = presenter.view.top_widget
    tiles = [
        child
        for child in top_widget._stat_cards_row.findChildren(QWidget)
        if child.objectName().startswith("cardMetric_")
    ]
    assert len(tiles) == len(presenter._view_model.run_result.primaryStatCards)
    assert tiles


def test_qml_documents_load_without_errors(presenter, qapp):
    """No QML left in `BackTestView` at all (EPIC-006E) — kept as a
    construction smoke test."""
    qapp.processEvents()
    assert presenter.view.top_widget is not None
    assert presenter.view.bottom_widget is not None


def test_qml_run_button_click_requests_a_run(
    presenter, view_model, qapp, mock_thread_mgr
):
    qapp.processEvents()

    presenter.view.top_widget._btn_run.click()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()


def test_bot_params_button_is_enabled(presenter, qapp):
    """BOT-047: unlike BOT-022's placeholder, the dialog now renders a real,
    strategy-driven form, so the button no longer needs to stay locked."""
    qapp.processEvents()

    assert presenter.view.top_widget._btn_bot_params.isEnabled() is True


def test_bot_params_schema_is_empty_for_a_strategy_with_no_declared_params(
    view_model,
):
    """`fake_strategy` (the shared fixture's registered strategy) declares
    nothing — the modal must show "no params" rather than crash on an empty
    schema."""
    assert view_model.strategy_params.botParamsGroups == ()


def test_bot_params_schema_reflects_a_strategy_with_declared_params(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request
):
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
    presenter = _build_presenter_with_registry(
        qapp, mock_thread_mgr, mock_dispatcher, mock_config, registry, request
    )
    view_model = presenter._view_model

    groups = view_model.strategy_params.botParamsGroups
    assert len(groups) == 1
    fields = {f.name: f for f in groups[0].fields}
    assert fields["period"].default == 20
    assert fields["period"].value == 20
    assert fields["threshold"].default == 1.5


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
    assert view_model.strategy_params.selectedStrategyKey == "fake_strategy"
    assert view_model.strategy_params.botParamsGroups == ()

    view_model.strategy_params.selectedStrategyKey = "rich_strategy"

    assert len(view_model.strategy_params.botParamsGroups) == 1


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
    assert view_model.strategy_params.botParamsError == ""
    assert saved_signal_calls == [1]
    # Values shown by the (now-refreshed) schema reflect what was just saved.
    fields = {f.name: f for f in view_model.strategy_params.botParamsGroups[0].fields}
    assert fields["period"].value == 50
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
    assert view_model.strategy_params.botParamsError != ""
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

    assert view_model.strategy_params.botParamsError != ""
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
    view_model.strategy_params.selectedStrategyKey = "rich_strategy"
    view_model.requestBotParamsSave({"period": "50", "threshold": "2.5"})
    assert presenter._strategy_params is not None

    view_model.strategy_params.selectedStrategyKey = "fake_strategy"

    assert presenter._strategy_params is None
    assert view_model.strategy_params.botParamsError == ""


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
    """`count` candles **one minute apart**.

    `EPIC-025` PR 1.1 fixed a real defect here: every row used to carry
    `open_time=_T0`, so three "candles" were one candle three times over by
    the store's primary key. Nothing noticed while a stubbed dispatcher handed
    the list straight back; `IHistoricalKlines` reads a store keyed on
    `open_time`, exactly as the real repository is, so the invalid shape
    became visible the moment these rows had to survive a round trip.

    The offsets are chosen so candle 0 closes **exactly at `_T0`**, because
    the chart's x axis is `close_time` (`map_klines`) and `_make_result`'s
    trades enter at `_T0`. Spacing the rows forward from `_T0` instead would
    put the first candle after the entry, and every trade marker would
    silently vanish — which is how this detail was found.

    Built here rather than with `contracts/testing/candles.py`'s published
    builder, and the reason is the epoch: that factory counts from its own
    `T0` (2024-01-01) while this file's trades, equity samples and assertions
    are all pinned to `_T0` (2026-01-01). Candles in one year and trades in
    another cannot align, and markers silently vanish — which is exactly how
    this was found.
    """
    return [
        MarketData(
            symbol="ETHUSDT",
            interval="1m",
            open_time=_T0 + timedelta(minutes=minute - 1),
            open_price=100.0 + minute,
            high_price=100.0 + minute + 5.0,
            low_price=100.0 + minute - 5.0,
            close_price=100.0 + minute,
            volume=10.0,
            close_time=_T0 + timedelta(minutes=minute),
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for minute in range(count)
    ]


def test_successful_run_fetches_klines_and_renders_the_ohlc_chart(
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    assert len(presenter.view._last_klines) == 3
    assert presenter.view.chart_cards[0].chart_card._raw_history
    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type
        == CANDLESTICK
    )


def test_runtime_run_backtest_fetch_render_path_keeps_qquickwidgets_clean_and_chart_usable(
    presenter, view_model, mock_dispatcher, qapp, fake_historical_klines
):
    """Regression harness for the real Backtest runtime path the user hit:
    run backtest -> fetch historical klines -> push them through the chart
    widget composition.

    Existing tests already proved each piece in isolation (use case, query,
    chart widget), but this stitches them together in the
    exact order `_run_backtest()` uses at runtime and asserts the hybrid view
    stays internally consistent after the render burst."""
    config = _lock_and_get_config(presenter, view_model)
    result = _make_result(with_trades=True)
    klines = _make_klines()
    fake_historical_klines.seed(klines)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)

    presenter._run_backtest(config)
    qapp.processEvents()

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
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)

    presenter.view.set_chart_mode(ChartDisplayMode.EQUITY)

    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type == LINE
    )


def test_switching_to_both_mode_adds_an_equity_subplot(
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)

    presenter.view.set_chart_mode(ChartDisplayMode.BOTH)

    assert presenter.view._equity_subplot_added is True
    assert (
        presenter.view.chart_cards[0].chart_card.chart_type_renderer.chart_type
        == CANDLESTICK
    )


def test_switching_away_from_both_mode_removes_the_equity_subplot(
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)
    presenter.view.set_chart_mode(ChartDisplayMode.BOTH)

    presenter.view.set_chart_mode(ChartDisplayMode.OHLC)

    assert presenter.view._equity_subplot_added is False


def test_ema_toggle_is_a_no_op_when_the_strategy_declares_no_indicators(
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    """`_FakeStrategy` (the shared fixture's registered strategy) declares
    no indicators (BOT-060) — proves the toggle path degrades safely
    instead of crashing when there is nothing drawn to show/hide."""
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )
    presenter._run_backtest(config)

    presenter.view.chart_controls.sig_ema_toggled.emit(False)  # must not raise


def test_connect_chart_controls_wires_marker_filter_changed_to_view_refresh(
    qapp, mock_container, request
):
    """`connect_chart_controls()` (`signal_wiring.py`, PROP-004) must connect
    `chart_controls.sig_marker_filter_changed` to
    `view.refresh_trade_flag_filters()` — asserted against the real
    construction-time wiring, not a hand-called method (`testing-rule.md`'s
    wiring-test requirement / rubric E12). `refresh_trade_flag_filters` is
    patched at the *class*, before `BackTestPresenter.__init__()` runs
    `connect_chart_controls()`: Qt binds a signal-to-bound-method connection
    at `.connect()` time, so patching the *instance* afterward is silently
    ignored by the already-connected slot — verified empirically before
    writing this test. Deleting the `.connect(...)` line in
    `signal_wiring.py` leaves this red."""
    with patch.object(BackTestView, "refresh_trade_flag_filters") as refresh_spy:
        view = BackTestView()
        view.resize(1400, 800)
        view.show()
        qapp.processEvents()
        request.addfinalizer(view.deleteLater)
        BackTestPresenter(view, mock_container)

        view.chart_controls.sig_marker_filter_changed.emit()

    refresh_spy.assert_called_once()


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
    presenter, view_model, mock_dispatcher, fake_historical_klines, strategy_registry
):
    """BOT-060: the chart must draw whatever the BACKTESTED strategy itself
    declares via build_indicators() — not a fixed, unrelated indicator
    script (the bug the user reported: Buy/Sell markers not lining up with
    anything drawn)."""
    strategy_registry.register("ema_strategy", _EmaIndicatorStrategy)
    view_model.strategy_params.selectedStrategyKey = "ema_strategy"
    config = _lock_and_get_config(presenter, view_model)
    assert config.strategy_key == "ema_strategy"
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    assert presenter._active_strategy_lines == {"ema_fast", "ema_slow"}
    added_names = {call.args[0] for call in card.add_overlay_indicator.call_args_list}
    assert added_names == {"ema_fast", "ema_slow"}
    updated_names = {call.args[0] for call in card.update_indicator_data.call_args_list}
    assert updated_names == {"ema_fast", "ema_slow"}
    # BOT-111: a strategy that never overrides chart_line_widths() must
    # still draw at the pre-existing fixed width, forwarded explicitly.
    widths = {
        call.args[0]: call.args[2] for call in card.add_overlay_indicator.call_args_list
    }
    assert widths == {"ema_fast": 2, "ema_slow": 2}


def test_successful_run_honors_a_strategys_own_chart_line_widths(
    presenter, view_model, mock_dispatcher, fake_historical_klines, strategy_registry
):
    """BOT-111: EmaTrendPullbackStrategy-style strategies can request a
    different pen width per line (e.g. a thinner entry EMA) — proven here
    through the real presenter wiring, not just the isolated helper."""

    class _WidthOverridingStrategy(_EmaIndicatorStrategy):
        def chart_line_widths(self) -> dict[str, int]:
            return {"ema_fast": 1}  # ema_slow deliberately left at the default

    strategy_registry.register("width_strategy", _WidthOverridingStrategy)
    view_model.strategy_params.selectedStrategyKey = "width_strategy"
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    widths = {
        call.args[0]: call.args[2] for call in card.add_overlay_indicator.call_args_list
    }
    assert widths == {"ema_fast": 1, "ema_slow": 2}


def _make_trend_zone_klines(closes: list[float]) -> list[MarketData]:
    """Same shape as `_make_klines()`, but with an explicit close sequence —
    `compute_strategy_trend_zones()`'s `_MIN_ZONE_BARS` floor (BUG-079)
    needs at least 3 consecutive bars per zone, which `_make_klines()`'s
    single-unit ramp can never produce against `_TrendZoneStrategy`'s fixed
    103.0 threshold (only bar 0 ever lands below it).

    One minute apart, for the reason `_make_klines()` documents: six bars
    sharing one `open_time` are one bar in any real store, and a zone needing
    three consecutive bars could then never form.
    """
    return [
        MarketData(
            symbol="ETHUSDT",
            interval="1m",
            open_time=_T0 + timedelta(minutes=minute - 1),
            open_price=close,
            high_price=close + 5.0,
            low_price=close - 5.0,
            close_price=close,
            volume=10.0,
            close_time=_T0 + timedelta(minutes=minute),
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for minute, close in enumerate(closes)
    ]


def test_successful_run_draws_the_strategys_own_trend_zone_on_the_chart(
    presenter, view_model, mock_dispatcher, fake_historical_klines, strategy_registry
):
    """BOT-113: a strategy that overrides classify_trend_zone() must have
    its background zones drawn on the chart via the same set_script_regions()
    API BOT-032's custom scripts already use — under the fixed
    "strategy_trend_zone" key."""
    strategy_registry.register("trend_zone_strategy", _TrendZoneStrategy)
    view_model.strategy_params.selectedStrategyKey = "trend_zone_strategy"
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.set_script_regions = Mock()
    # 3 bars below the 103.0 threshold then 3 at/above it — each zone clears
    # `_MIN_ZONE_BARS` (BUG-079) so both are actually drawn, not dropped.
    # Seeded in chronological order, which is the only order a store has:
    # the coordinator asks `IHistoricalKlines` for the NEWEST bars (that is
    # how a limit keeps recent data) and reverses them back to chronological
    # before replaying, exactly as production does. The old stub had to be
    # handed a pre-reversed list to fake that; a real store needs no trick.
    klines = _make_trend_zone_klines([90.0, 90.0, 90.0, 110.0, 110.0, 110.0])
    fake_historical_klines.seed(klines)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    # Chronological closes 90/90/90/110/110/110 -> DOWN x3, UP x3 (merged
    # into 2 spans, each clearing the minimum-bar floor).
    card.set_script_regions.assert_called_once()
    key, spans = card.set_script_regions.call_args.args
    assert key == "strategy_trend_zone"
    assert len(spans) == 2
    assert spans[0][2] == BEAR_COLOR
    assert spans[1][2] == BULL_COLOR


def test_realtime_run_draws_its_own_committed_bars_not_a_fresh_kline_query(
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    """BUG-021: a Realtime run only ever syncs/coverage-checks
    `tick_resolution` (1s), never `config.timeframe` — so querying the
    exchange's published candles for the timeframe returned 0 rows and the
    chart came up blank after every tick-based run. It must instead draw the
    bars the run's own engine aggregated from the ticks it actually had
    (`BacktestResult.committed_bars`), which is also the only truthful
    source: those bars carry the tick gaps the published candles don't, so
    markers derived from them would otherwise sit above candles that
    disagree with the decisions actually made.

    The history port is left **empty**, which is the real condition this
    reproduces: nothing is stored for `config.timeframe`, because only
    `tick_resolution` was ever synced. `EPIC-025` PR 1.1a's cleanup also made
    the "never a fresh kline query" half of the name assertable — it is the
    `reads == []` below, where before the move nothing checked it at all and
    the test name promised what only its docstring said.
    """
    committed = _make_klines(count=4)
    result = _make_result(with_trades=True)
    result = replace(result, committed_bars=committed)
    config = _lock_and_get_config(presenter, view_model)
    config = replace(config, execution_mode=BacktestExecutionMode.HISTORICAL_TICK)
    card = presenter.view.chart_cards[0]
    card.render_historical_data = Mock()
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result, realtime=True)

    presenter._run_backtest(config)

    card.render_historical_data.assert_called_once()
    drawn = card.render_historical_data.call_args.args[0]
    assert len(drawn) == len(committed)
    assert fake_historical_klines.reads == [], (
        "a realtime run draws its own bars and must not read stored candles"
    )


def test_static_run_still_queries_klines_when_no_committed_bars(
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    """The BUG-021 fix must stay scoped to engines that build their own bars.
    Static reads its bars straight from storage and reports
    `committed_bars=None`, so it must keep querying — otherwise it would
    silently render an empty chart."""
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.render_historical_data = Mock()
    result = _make_result(with_trades=True)
    assert result.committed_bars is None
    fake_historical_klines.seed(_make_klines(count=3))
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(result)

    presenter._run_backtest(config)

    card.render_historical_data.assert_called_once()
    assert len(card.render_historical_data.call_args.args[0]) == 3


def test_strategy_with_no_trend_zone_override_draws_no_zones(
    presenter, view_model, mock_dispatcher, fake_historical_klines, strategy_registry
):
    """A strategy predating BOT-113 (never overrides classify_trend_zone())
    must still call set_script_regions() — with an empty span list, not skip
    the call — so a stale zone from a previous strategy's run never lingers
    on the chart after switching to one with no zone opinion."""
    strategy_registry.register("ema_strategy", _EmaIndicatorStrategy)
    view_model.strategy_params.selectedStrategyKey = "ema_strategy"
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.set_script_regions = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    card.set_script_regions.assert_called_once_with("strategy_trend_zone", [])


def test_strategy_trend_zone_is_cleared_before_each_new_run(presenter, view_model):
    """Mirrors test_active_strategy_lines_are_cleared_before_each_new_run_not_after
    for the zone key — must clear synchronously on the main thread before the
    background run starts, so a stale zone never survives a switch to a
    strategy with a different (or no) zone opinion."""
    card = presenter.view.chart_cards[0]
    card.clear_script_regions = Mock()

    view_model.requestRun()

    card.clear_script_regions.assert_any_call("strategy_trend_zone")


def test_ema_toggle_shows_and_hides_the_strategys_own_indicator_lines(
    presenter, view_model, mock_dispatcher, fake_historical_klines, strategy_registry
):
    strategy_registry.register("ema_strategy", _EmaIndicatorStrategy)
    view_model.strategy_params.selectedStrategyKey = "ema_strategy"
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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
    qapp,
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    request,
    historical_klines=None,
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
        historical_klines=historical_klines,
    )


def _build_presenter_with_overlay_and_subplot_scripts(
    qapp,
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    request,
    historical_klines=None,
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
        historical_klines=historical_klines,
    )


def test_script_model_is_populated_from_registry_and_default_enabled_scripts_are_checked(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
):
    presenter = _build_presenter_with_script(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )

    assert presenter._view_model.script_model.enabled_keys == ["test_script"]


def test_successful_run_draws_enabled_reference_script_lines_on_the_chart(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
):
    presenter = _build_presenter_with_script(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )
    view_model = presenter._view_model
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    added_names = {call.args[0] for call in card.add_overlay_indicator.call_args_list}
    assert added_names == {"test_script:R"}
    updated_names = {call.args[0] for call in card.update_indicator_data.call_args_list}
    assert updated_names == {"test_script:R"}


def test_disabling_a_script_before_the_next_run_stops_it_from_drawing(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
):
    """BOT-064's own "no retroactive effect" rule: enabled_keys is
    snapshotted at 'Chạy Backtest' click time, in `_start_backtest_run` —
    toggling the checkbox off before the NEXT run must take effect, exactly
    like the Dev Board checklist (TC-GAP-07)."""
    presenter = _build_presenter_with_script(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )
    view_model = presenter._view_model
    view_model.script_model.setEnabled(0, False)
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    card.add_overlay_indicator.assert_not_called()


def test_switching_to_equity_mode_hides_an_overlay_scripts_lines(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
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
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )
    view_model = presenter._view_model
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
):
    """BOT-095F: toggling an indicator script ON after a backtest run dynamically
    draws the curves without rerunning the simulation or marking config dirty."""
    presenter = _build_presenter_with_script(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )
    view_model = presenter._view_model
    view_model.script_model.setEnabled(0, False)
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.add_overlay_indicator = Mock()
    card.update_indicator_data = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
):
    """BOT-095F: toggling an indicator script OFF after a backtest run dynamically
    removes the curves from the chart."""
    presenter = _build_presenter_with_script(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )
    view_model = presenter._view_model
    config = _lock_and_get_config(presenter, view_model)
    card = presenter.view.chart_cards[0]
    card.remove_indicator = Mock()
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    # Toggle the script OFF dynamically
    view_model.script_model.setEnabled(0, False)

    card.remove_indicator.assert_called_with("test_script:R")
    assert "test_script" not in presenter._chart_script_runner.active
    assert not view_model.isConfigDirty


def test_dynamic_script_toggle_on_during_equity_mode_keeps_overlay_hidden(
    qapp, mock_thread_mgr, mock_dispatcher, mock_config, request, fake_historical_klines
):
    """BOT-095F + BOT-065: enabling an overlay script during Equity mode draws it hidden."""
    presenter = _build_presenter_with_script(
        qapp,
        mock_thread_mgr,
        mock_dispatcher,
        mock_config,
        request,
        historical_klines=fake_historical_klines,
    )
    view_model = presenter._view_model
    view_model.script_model.setEnabled(0, False)
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)
    card = presenter.view.chart_cards[0]

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.EQUITY].click()
    qapp.processEvents()

    card.set_indicator_visible = Mock()
    view_model.script_model.setEnabled(0, True)

    card.set_indicator_visible.assert_called_with("test_script:R", False)


def test_mode_buttons_switch_the_chart_mode_end_to_end(
    presenter, view_model, mock_dispatcher, qapp, fake_historical_klines
):
    """Native QPushButton click -> BacktestChartControls signal -> Presenter
    slot -> View render, with no QML/ViewModel involved."""
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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
    presenter, view_model, mock_dispatcher, qapp, fake_historical_klines
):
    """Regression test (found by running the app): the 4 EMA overlay is
    price-scale, exactly like the Buy/Sell flags already handled — left
    plotted through a switch to Equity-solo mode, it stays on the same main
    plot as the equity curve and drags pyqtgraph's auto-range onto price
    values (tens of thousands), squashing the equity curve flat/invisible."""
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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
    presenter, view_model, mock_dispatcher, fake_historical_klines
):
    config = _lock_and_get_config(presenter, view_model)
    fake_historical_klines.seed(_make_klines())
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
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

    assert view_model.trade_log.totalCount == 25
    assert view_model.trade_log.totalPages == 2
    assert len(view_model.trade_log.rows) == 20  # PAGE_SIZE


def test_no_historical_data_clears_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert view_model.trade_log.rows == []
    assert view_model.trade_log.totalCount == 0


def test_failed_run_clears_the_trade_log(presenter, view_model, mock_dispatcher):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")

    presenter._run_backtest(config)

    assert view_model.trade_log.rows == []
    assert view_model.trade_log.totalCount == 0


def test_changing_the_filter_recomputes_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=10, win_count=3)
    )
    presenter._run_backtest(config)

    view_model.trade_log.filter = "win"

    assert view_model.trade_log.totalCount == 3


def test_changing_the_filter_resets_to_page_1(presenter, view_model, mock_dispatcher):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=25, win_count=25)
    )
    presenter._run_backtest(config)
    view_model.trade_log.currentPage = 2

    view_model.trade_log.filter = "loss"  # narrows to 0 rows -> would strand page 2

    assert view_model.trade_log.currentPage == 1


def test_changing_the_search_text_recomputes_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=5, win_count=5)
    )
    presenter._run_backtest(config)

    view_model.trade_log.searchText = "#3"

    assert view_model.trade_log.totalCount == 1


def test_changing_the_current_page_recomputes_the_trade_log(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=25, win_count=25)
    )
    presenter._run_backtest(config)

    view_model.trade_log.currentPage = 2

    assert len(view_model.trade_log.rows) == 5  # 25 - 20 on page 1


def test_export_writes_the_currently_filtered_trades(
    presenter, view_model, mock_dispatcher, tmp_path
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=10, win_count=4)
    )
    presenter._run_backtest(config)
    view_model.trade_log.filter = "win"
    export_path = str(tmp_path / "export.csv")

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=(export_path, "CSV Files (*.csv)"),
    ):
        view_model.trade_log.request_export()

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
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=("", ""),
    ):
        view_model.trade_log.request_export()  # must not raise


def test_export_does_nothing_when_there_are_no_trades_yet(presenter, view_model):
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        view_model.trade_log.request_export()

    mock_dialog.assert_not_called()


def _find_trade_log_row(panel, index: int):
    row_layout = panel._rows_layout
    for i in range(row_layout.count() - 1):
        widget = row_layout.itemAt(i).widget()
        if widget._summary_btn.objectName() == f"rowTradeLog_{index}":
            return widget
    raise AssertionError(f"no trade log row for index {index}")


def test_qml_trade_log_filter_tab_click_updates_the_view_model(
    presenter, view_model, mock_dispatcher, qapp
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=5, win_count=2)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    panel = presenter.view.bottom_widget

    win_button = next(
        b for b in panel._filter_buttons if b.objectName() == "tabTradeLogFilter_win"
    )
    win_button.click()
    qapp.processEvents()

    assert view_model.trade_log.filter == "win"
    assert view_model.trade_log.totalCount == 2


def test_qml_trade_log_export_button_click_requests_export(
    presenter, view_model, mock_dispatcher, qapp
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=3, win_count=3)
    )
    presenter._run_backtest(config)
    qapp.processEvents()

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=("", ""),
    ) as mock_dialog:
        presenter.view.bottom_widget._btn_export.click()
        qapp.processEvents()

    mock_dialog.assert_called_once()


def test_qml_trade_log_search_field_updates_the_view_model(
    presenter, view_model, mock_dispatcher, qapp
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=5, win_count=5)
    )
    presenter._run_backtest(config)
    qapp.processEvents()

    search_field = presenter.view.bottom_widget._search_field
    search_field.setText("#3")
    search_field.textEdited.emit("#3")
    qapp.processEvents()

    assert view_model.trade_log.searchText == "#3"
    assert view_model.trade_log.totalCount == 1


def test_qml_trade_logs_document_loads_without_errors(presenter, qapp):
    """No QML left in `BackTestTradeLogsPanel` (EPIC-006E2) — kept as a
    construction smoke test."""
    qapp.processEvents()
    assert presenter.view.bottom_widget is not None


def test_qml_clicking_a_trade_log_row_toggles_its_detail_section(
    presenter, view_model, mock_dispatcher, qapp
):
    """BOT-045 §2.2: clicking the summary row expands/collapses the entry
    catalyst / exit execution / metadata block below it."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result_with_trades(trade_count=3, win_count=3)
    )
    presenter._run_backtest(config)
    qapp.processEvents()
    panel = presenter.view.bottom_widget

    row = _find_trade_log_row(panel, 1)
    assert row._detail.isVisible() is False

    row._summary_btn.click()
    qapp.processEvents()
    row = _find_trade_log_row(panel, 1)
    assert row._detail.isVisible() is True

    row._summary_btn.click()
    qapp.processEvents()
    row = _find_trade_log_row(panel, 1)
    assert row._detail.isVisible() is False


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
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
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
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
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


def test_backtest_succeeded_sets_the_comparison_snapshot(presenter):
    """`BOT-115D` — `ReportComparisonDialog`'s Column A reads this
    snapshot; it must carry exactly the run's own config and result, not a
    stale or re-derived copy."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    snapshot = vm.run_result.comparison_snapshot()
    assert snapshot is not None
    assert snapshot.run_config == presenter._last_run_config
    assert snapshot.result is result


def test_backtest_empty_clears_the_comparison_snapshot(presenter):
    """Mutation check: without this reset, a comparison snapshot from an
    earlier successful run would stay retained after a run that returned
    no data at all, showing stale Column A data."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    presenter._on_backtest_succeeded(_make_fake_result(trades=[]))
    assert vm.run_result.comparison_snapshot() is not None

    presenter._on_run_backtest()
    cfg = presenter._get_current_config()
    presenter._on_backtest_empty("No historical data", cfg)

    assert vm.run_result.comparison_snapshot() is None


def test_backtest_failed_clears_the_comparison_snapshot(presenter):
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    presenter._on_backtest_succeeded(_make_fake_result(trades=[]))
    assert vm.run_result.comparison_snapshot() is not None

    presenter._on_run_backtest()
    presenter._on_backtest_failed("Connection timed out")

    assert vm.run_result.comparison_snapshot() is None


def test_chart_data_ready_pushes_a_session_run_history_snapshot(presenter, view_model):
    """`BOT-095G` — the one point a complete snapshot (config, result and
    the exact candles drawn) exists at once is `_on_chart_data_ready`, after
    `_on_backtest_succeeded` has already set `_last_run_config`/
    `_last_result`."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    view_model.selectedTimeframe = "1m"
    view_model.initialCapitalText = "10000"
    view_model.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    klines = [(1.0, 1.0, 2.0, 0.5, 1.5)]
    volume = [(1.0, 100.0, True)]
    presenter._on_chart_data_ready(result, klines, volume)

    history = presenter._run_history.get_all()
    assert len(history) == 1
    assert history[0].run_config.strategy_key == "fake_strategy"
    assert history[0].klines == klines
    assert history[0].volume == volume

    ui_entries = view_model.sessionRunHistory
    assert len(ui_entries) == 1
    assert ui_entries[0]["run_id"] == history[0].run_id
    assert "fake_strategy" in ui_entries[0]["label"]


def test_restore_run_requested_redisplays_without_dispatching_a_command(
    presenter, view_model, mock_dispatcher
):
    """A restore must be free — no engine call, no network fetch, matching
    `state_persistence`'s own "opening the screen still runs nothing"
    contract."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    view_model.selectedTimeframe = "1m"
    view_model.initialCapitalText = "10000"
    view_model.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )

    run_id = presenter._run_history.get_all()[0].run_id
    mock_dispatcher.dispatch.reset_mock()

    presenter._on_restore_run_requested(run_id)

    mock_dispatcher.dispatch.assert_not_called()
    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert "fake_strategy" in view_model.lastRunSummary


def test_restore_run_requested_does_not_mark_the_restored_run_dirty(
    presenter, view_model
):
    """`BOT-095G` — restoring applies the remembered form through the same
    ViewModel setters a user typing would, which fire the same `xChanged`
    signals `_on_config_input_changed` listens to. Without the
    `_restoring_state` guard this would immediately flip `isConfigDirty`
    back on against the very run just redisplayed."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    view_model.selectedTimeframe = "1m"
    view_model.initialCapitalText = "10000"
    view_model.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )

    view_model.selectedTimeframe = "5m"
    assert view_model.isConfigDirty is True

    run_id = presenter._run_history.get_all()[0].run_id
    presenter._on_restore_run_requested(run_id)

    assert view_model.isConfigDirty is False
    assert presenter.fsm.current_state == BacktestUiState.COMPLETED


def test_restore_run_requested_with_unknown_id_does_nothing(presenter, view_model):
    before_state = presenter.fsm.current_state
    before_summary = view_model.lastRunSummary

    presenter._on_restore_run_requested("not-a-real-run-id")

    assert presenter.fsm.current_state == before_state
    assert view_model.lastRunSummary == before_summary


def test_restore_run_requested_is_ignored_while_a_run_is_active(presenter, view_model):
    """`BOT-095G` acceptance criterion 4: restoring a snapshot while a new
    run is active must not clobber the in-flight action's state — the FSM
    has no `RUN_RESTORED_FROM_HISTORY` transition from `RUNNING`, and the
    handler must actually check that, not just rely on the toolbar being
    disabled."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    view_model.selectedTimeframe = "1m"
    view_model.initialCapitalText = "10000"
    view_model.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )
    run_id = presenter._run_history.get_all()[0].run_id

    # Start a second run without letting it finish — the FSM is now RUNNING.
    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    summary_before = view_model.lastRunSummary

    presenter._on_restore_run_requested(run_id)

    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert view_model.lastRunSummary == summary_before


def test_trade_logs_panel_selection_signal_is_wired_to_the_presenter(
    presenter, view_model
):
    """`PROP-001` wiring test (`testing-rule.md` §E12): emits the real
    `bottom_widget.selectedTradeChanged` signal rather than calling
    `_on_trade_row_selected` directly, so removing the `.connect(...)` line
    in `signal_wiring.py` makes this fail."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )
    trade = result.trades[0]

    presenter.view.bottom_widget.selectedTradeChanged.emit(1)

    trade_link = presenter.view.chart_cards[0].chart_card.trade_link
    assert trade_link._curve.isVisible()
    x_data, _y_data = trade_link._curve.getData()
    assert list(x_data) == [trade.entry_time.timestamp(), trade.exit_time.timestamp()]


def test_trade_row_selected_draws_the_trade_link_on_the_chart(presenter, view_model):
    """`PROP-001` — picking a Trade Logs row draws a dashed line between
    that trade's entry and exit points."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )
    trade = result.trades[0]

    presenter._on_trade_row_selected(1)

    trade_link = presenter.view.chart_cards[0].chart_card.trade_link
    assert trade_link._curve.isVisible()
    x_data, y_data = trade_link._curve.getData()
    assert list(x_data) == [trade.entry_time.timestamp(), trade.exit_time.timestamp()]
    assert list(y_data) == [trade.entry_price, trade.exit_price]


def test_trade_row_selected_pans_the_chart_to_the_trade_window(presenter, view_model):
    """`PROP-002` — picking a Trade Logs row also pans/zooms the chart so
    the trade's entry/exit window is visible without manual scrolling.
    Klines span the trade's own entry/exit timestamps (`_T0`..`_T1`) so
    `ChartCard._apply_view_bounds()`'s history-derived `setLimits()` does not
    clamp the pan target away — a real chart's loaded history always covers
    every trade drawn on it."""
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    entry_ts, exit_ts = _T0.timestamp(), _T1.timestamp()
    klines = [(entry_ts, 1.0, 2.0, 0.5, 1.5), (exit_ts, 1.0, 2.0, 0.5, 1.5)]
    presenter._on_chart_data_ready(result, klines, [(entry_ts, 100.0, True)])
    trade = result.trades[0]
    chart_card = presenter.view.chart_cards[0].chart_card
    chart_card.plot_layout.main_plot.setXRange(entry_ts, entry_ts + 1.0, padding=0)

    presenter._on_trade_row_selected(1)

    (min_x, max_x), _ = chart_card.plot_layout.main_plot.vb.viewRange()
    assert min_x <= trade.entry_time.timestamp()
    assert max_x >= trade.exit_time.timestamp()


def test_trade_row_deselected_clears_the_trade_link(presenter, view_model):
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )
    presenter._on_trade_row_selected(1)

    presenter._on_trade_row_selected(-1)

    trade_link = presenter.view.chart_cards[0].chart_card.trade_link
    assert not trade_link._curve.isVisible()


def test_trade_row_selected_with_an_out_of_range_index_clears_the_link(
    presenter, view_model
):
    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    presenter._on_run_backtest()
    result = _make_result(with_trades=True)
    presenter._on_backtest_succeeded(result)
    presenter._on_chart_data_ready(
        result, [(1.0, 1.0, 2.0, 0.5, 1.5)], [(1.0, 100.0, True)]
    )
    presenter._on_trade_row_selected(1)

    presenter._on_trade_row_selected(99)

    trade_link = presenter.view.chart_cards[0].chart_card.trade_link
    assert not trade_link._curve.isVisible()


def test_report_export_does_nothing_when_there_is_no_result_yet(presenter):
    """`BOT-115B` — mirrors `test_export_does_nothing_when_there_are_no_trades_yet`:
    the button is disabled until a run completes, but the handler itself must
    also refuse to open the dialog if it somehow fires early."""
    assert presenter._last_result is None

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        presenter._on_report_export_requested()

    mock_dialog.assert_not_called()


def test_report_export_writes_the_completed_run_to_the_chosen_path(presenter, tmp_path):
    """`BOT-115B` — "Save report" exports the exact run behind what's on
    screen (`_last_result`/`_last_run_config`, both set together in
    `_on_backtest_succeeded`), not a dirty toolbar's values."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    dest = tmp_path / "run.sagi-report.json"
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=(str(dest), ""),
    ):
        presenter._on_report_export_requested()

    assert dest.is_file()
    with open(dest, "rb") as report_file:
        loaded = load_backtest_report(
            report_file.read(), valid_strategy_keys={"fake_strategy"}
        )
    assert loaded.is_valid
    assert loaded.report.provenance.strategy_key == "fake_strategy"
    assert loaded.report.result.trades == result.trades


def test_report_export_writes_nothing_when_the_dialog_is_cancelled(presenter):
    """`BOT-115B` — an empty path (`QFileDialog.getSaveFileName`'s Cancel
    return) must not attempt a write."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    presenter._on_backtest_succeeded(_make_fake_result(trades=[]))

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
            "backtest_presenter.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
            "backtest_presenter.write_backtest_report"
        ) as mock_write,
    ):
        presenter._on_report_export_requested()

    mock_write.assert_not_called()


def test_report_export_uses_the_run_that_produced_the_result_not_a_dirty_toolbar(
    presenter, tmp_path
):
    """`BOT-115B` — after `isConfigDirty` goes true (toolbar edited post-run),
    "Save report" must still export `_last_run_config`, the snapshot from the
    run that produced the on-screen result, not the edited toolbar values."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    presenter._on_backtest_succeeded(_make_fake_result(trades=[]))

    vm.selectedTimeframe = "5m"
    assert vm.isConfigDirty is True

    dest = tmp_path / "run.sagi-report.json"
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=(str(dest), ""),
    ):
        presenter._on_report_export_requested()

    with open(dest, "rb") as report_file:
        loaded = load_backtest_report(
            report_file.read(), valid_strategy_keys={"fake_strategy"}
        )
    assert loaded.report.config.timeframe == TimeFrame.ONE_MINUTE


def _export_a_report(presenter, path, *, trades=None):
    """Runs a real backtest end to end and exports it, so import tests
    have a genuine `.sagi-report.json` on disk rather than a hand-built
    payload — the same real-file approach `test_write_backtest_report_
    writes_a_file_that_loads_back` already uses at the `logic/` layer."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD
    presenter._on_run_backtest()
    result = _make_fake_result(trades=trades or [])
    presenter._on_backtest_succeeded(result)
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getSaveFileName",
        return_value=(str(path), ""),
    ):
        presenter._on_report_export_requested()
    return result


def test_report_import_does_nothing_when_the_dialog_is_cancelled(presenter):
    """`BOT-115C` — an empty path (Cancel) must not touch the FSM."""
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ):
        presenter._on_report_import_requested()

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert presenter._last_result is None


def test_report_import_enters_the_viewing_state_with_matching_panels(
    presenter, tmp_path
):
    """`BOT-115C` §5 — importing a valid report enters
    `VIEWING_IMPORTED_REPORT`, `isConfigDirty` is False, and the presented
    result is exactly the exported one."""
    path = tmp_path / "run.sagi-report.json"
    result = _export_a_report(presenter, path)

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        presenter._on_report_import_requested()

    vm = presenter._view_model
    assert presenter.fsm.current_state == BacktestUiState.VIEWING_IMPORTED_REPORT
    assert vm.uiMode == BacktestUiState.VIEWING_IMPORTED_REPORT.value
    assert vm.isConfigDirty is False
    assert presenter._last_result.trades == result.trades
    assert presenter._last_run_config.strategy_key == "fake_strategy"
    assert vm.importedReportBannerText != ""
    assert path.name in vm.importedReportBannerText


def test_report_import_of_a_malformed_file_shows_an_error_and_stays_idle(
    presenter, tmp_path
):
    """`BOT-115C` §5 — a corrupt file must show an error and leave the
    screen exactly as it was, no FSM transition."""
    path = tmp_path / "broken.sagi-report.json"
    path.write_bytes(b"not json at all")

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        presenter._on_report_import_requested()

    vm = presenter._view_model
    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert vm.run_result.resultIsError is True
    assert vm.run_result.resultText != ""


def test_report_import_flags_a_strategy_no_longer_registered(presenter, tmp_path):
    """`BOT-115C` §3 — a report whose strategy was since removed from the
    registry can still be viewed, with the fact surfaced in the warning
    text (task's own combined-badge re-scope, see report_import.py)."""
    path = tmp_path / "run.sagi-report.json"
    _export_a_report(presenter, path)

    with (
        patch.object(presenter._strategy_catalog, "options", return_value=()),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
            "backtest_presenter.QFileDialog.getOpenFileName",
            return_value=(str(path), ""),
        ),
    ):
        presenter._on_report_import_requested()

    vm = presenter._view_model
    assert presenter.fsm.current_state == BacktestUiState.VIEWING_IMPORTED_REPORT
    assert "fake_strategy" in vm.run_result.resultWarningText


def test_exiting_the_imported_report_view_returns_to_idle_and_clears_the_banner(
    presenter, tmp_path
):
    path = tmp_path / "run.sagi-report.json"
    _export_a_report(presenter, path)
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        presenter._on_report_import_requested()
    vm = presenter._view_model
    assert vm.importedReportBannerText != ""

    presenter._on_exit_imported_report_view_requested()

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert vm.importedReportBannerText == ""


def test_run_requested_while_viewing_an_imported_report_starts_a_real_run(
    presenter, tmp_path
):
    """`BOT-115C` §2 — clicking Run while viewing exits the read-only view
    and runs for real, using the toolbar's own live values."""
    path = tmp_path / "run.sagi-report.json"
    _export_a_report(presenter, path)
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        presenter._on_report_import_requested()
    vm = presenter._view_model
    assert presenter.fsm.current_state == BacktestUiState.VIEWING_IMPORTED_REPORT
    vm.strategy_params.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING


def test_config_changed_while_viewing_an_imported_report_marks_it_dirty(
    presenter, tmp_path
):
    path = tmp_path / "run.sagi-report.json"
    _export_a_report(presenter, path)
    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui."
        "backtest_presenter.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        presenter._on_report_import_requested()
    vm = presenter._view_model
    assert presenter.fsm.current_state == BacktestUiState.VIEWING_IMPORTED_REPORT

    vm.selectedTimeframe = "5m"

    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY


def test_dirty_tracking_detects_timeframe_change_after_completed(presenter):
    """Verify changing timeframe when COMPLETED transitions to CONFIG_DIRTY with diff summary."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
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
    assert "Timeframe (1m → 5m)" in vm.configDiffSummary


def test_dirty_tracking_restores_to_completed_when_input_reverted(presenter):
    """Verify reverting modified input returns FSM to COMPLETED and clears diff summary."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
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
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = Currency.USD

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    # Change initial capital
    vm.initialCapitalText = "50000"
    assert presenter.fsm.current_state == BacktestUiState.CONFIG_DIRTY
    assert "Capital (10,000 → 50,000)" in vm.configDiffSummary

    # Change strategy
    vm.strategy_params.selectedStrategyKey = "ema_strategy"
    assert "Strategy (fake_strategy → ema_strategy)" in vm.configDiffSummary


def test_running_from_dirty_state_clears_dirty_state_on_completion(presenter):
    """Verify executing run from CONFIG_DIRTY transitions to RUNNING and on success COMPLETED with new snapshot."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
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
    vm.strategy_params.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    cfg = presenter._get_current_config()
    presenter._on_backtest_empty("No historical data", cfg)

    assert presenter.fsm.current_state == BacktestUiState.EMPTY_DATA
    assert vm.uiMode == BacktestUiState.EMPTY_DATA.value
    assert vm.run_result.needsDataSync is True
    assert presenter._last_no_data_config == cfg
    assert vm.run_result.drawdownPoints == []
    assert vm.run_result.yearlyReturns == []


def test_failed_backtest_transitions_to_idle_with_error(presenter):
    """Verify failed backtest transitions FSM to ERROR and populates error message."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    presenter._on_backtest_failed("Connection timed out")

    assert presenter.fsm.current_state == BacktestUiState.ERROR
    assert vm.uiMode == BacktestUiState.ERROR.value
    assert "Connection timed out" in vm.run_result.resultText
    assert vm.run_result.drawdownPoints == []
    assert vm.run_result.yearlyReturns == []


def test_backtest_succeeded_populates_drawdown_and_yearly_returns(presenter):
    """`BOT-106D` — `_on_backtest_succeeded` feeds the drawdown chart and
    returns heatmap from the same `BacktestResult` the stat cards read,
    then a later empty/failed run clears both again."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)

    assert vm.run_result.drawdownPoints != []
    assert vm.run_result.yearlyReturns != []

    presenter._on_run_backtest()
    presenter._on_backtest_failed("Connection timed out")

    assert vm.run_result.drawdownPoints == []
    assert vm.run_result.yearlyReturns == []


def test_qml_stale_warning_banner_and_button_dirty_rendering(presenter, qapp):
    """`BackTestTopPanel` renders the amber warning banner when
    isConfigDirty is True."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"

    presenter._on_run_backtest()
    result = _make_fake_result(trades=[])
    presenter._on_backtest_succeeded(result)
    qapp.processEvents()

    banner = presenter.view.top_widget._stale_banner
    assert banner.isVisible() is False

    # Modify timeframe -> CONFIG_DIRTY
    vm.selectedTimeframe = "5m"
    qapp.processEvents()

    assert banner.isVisible() is True


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
    assert "Backtest cancelled" in view_model.run_result.resultText


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
    # EPIC-008G §3: một payload có tên thay cho 5 tham số vị trí — hoán nhầm
    # `completed_bars`/`total_bars` giờ không còn lọt qua kiểu.
    presenter._on_backtest_progress_for_action(
        BacktestProgress(
            action_id=action.action_id,
            phase="full",
            completed_bars=50,
            total_bars=100,
            elapsed_seconds=2.0,
        )
    )
    assert view_model.run_progress.backtestProgressPercent == 50.0

    view_model.requestCancelBacktest()
    presenter._on_backtest_progress_for_action(
        BacktestProgress(
            action_id=action.action_id,
            phase="full",
            completed_bars=90,
            total_bars=100,
            elapsed_seconds=3.0,
        )
    )

    assert view_model.run_progress.backtestProgressPercent == 50.0


def test_qml_run_button_requests_cancel_while_backtest_is_running(
    presenter, view_model, qapp
):
    view_model.requestRun()

    presenter.view.top_widget._btn_run.click()
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
    assert view_model.run_result.resultText == "Running backtest..."


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
    assert view_model.run_result.resultText == "Running backtest..."


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
    assert view_model.run_result.resultIsError is True
    assert "boom" in view_model.run_result.resultText


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
    assert view_model.run_result.resultText == "Running backtest..."


def test_invalidated_action_cannot_apply_a_late_failure(presenter, view_model):
    view_model.requestRun()
    action = presenter._active_action
    assert action is not None

    presenter._invalidate_active_action()
    presenter._on_backtest_failed_for_action(action.action_id, "late failure")

    assert presenter._active_action_outcome is BacktestActionOutcome.INVALIDATED
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    assert view_model.run_result.resultText == "Running backtest..."


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
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"

    presets_under_test = ["7d", "30d", "90d", "365d", "all"]
    for preset in presets_under_test:
        vm.time_range.preset = preset
        # Must not raise TypeError — was crashing with missing 'now' arg
        config = presenter._get_current_config()
        assert config is not None, f"Expected config for preset={preset!r}"


def test_get_current_config_custom_preset_parses_dates(presenter):
    """Regression companion: CUSTOM preset path must also work without crash."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.time_range.preset = "custom"
    vm.time_range.customStartText = "2026-01-01"
    vm.time_range.customEndText = "2026-06-30"

    config = presenter._get_current_config()
    assert config is not None


def test_on_backtest_succeeded_does_not_raise_for_preset_ranges(presenter):
    """Regression: _on_backtest_succeeded internally calls _get_current_config
    to snapshot _last_run_config and compute diff — must not crash for
    any non-CUSTOM preset selected in the toolbar when a run completes."""
    vm = presenter._view_model
    vm.strategy_params.selectedStrategyKey = "fake_strategy"
    vm.selectedTimeframe = "1m"
    vm.initialCapitalText = "10000"
    vm.time_range.preset = "30d"  # A preset that requires 'now' in resolve_time_range

    presenter._on_run_backtest()
    assert presenter.fsm.current_state == BacktestUiState.RUNNING

    # Must not raise — was crashing with "missing 1 required positional argument: 'now'"
    result = _make_result(with_trades=False)
    presenter._on_backtest_succeeded(result)

    assert presenter.fsm.current_state == BacktestUiState.COMPLETED
    assert presenter._last_run_config is not None


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
    assert "no metadata" in view_model.marketRuleExplanation


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
    assert "Verified against Binance exchange rules" in view_model.marketRuleExplanation


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
    assert "metadata is stale" in view_model.marketRuleExplanation


def test_strategy_properties_save_applies_leverage_to_the_view_model(
    presenter, view_model
):
    """BOT-105: StrategyPropertiesModal.qml's new leverage spin boxes save
    through the same "properties" payload path pyramiding/slippage already
    use — must reach view_model.broker_sim.longLeverage/shortLeverage, which
    _build_run_config threads into BrokerSimulationConfig."""
    presenter._on_strategy_properties_save_requested(
        {"properties": {"long_leverage": 5, "short_leverage": 3}}
    )

    assert view_model.broker_sim.longLeverage == 5.0
    assert view_model.broker_sim.shortLeverage == 3.0


def test_strategy_properties_save_applies_take_profit_pct_to_the_view_model(
    presenter, view_model
):
    """EPIC-001A: `BrokerSimulationConfig.take_profit_pct` had no UI path at
    all before this — only ever set directly in tests — so a strategy's own
    `take_profit_percent` input never actually triggered a take-profit exit
    in the real app. StrategyPropertiesModal.qml's new checkbox + text field
    save through the same "properties" payload path as leverage."""
    presenter._on_strategy_properties_save_requested(
        {
            "properties": {
                "take_profit_enabled": True,
                "take_profit_pct_text": "2.0",
            }
        }
    )

    assert view_model.broker_sim.takeProfitPctEnabled is True
    assert view_model.broker_sim.takeProfitPctText == "2.0"


def test_build_run_config_sets_take_profit_pct_only_when_enabled(presenter, view_model):
    """`_build_run_config()` must thread the enabled+parsed value into
    `BrokerSimulationConfig.take_profit_pct` — and must leave it `None`
    (BOT-041's own untouched default) when the checkbox is off, even if the
    text field still holds a leftover value from a previous toggle."""
    view_model.broker_sim.takeProfitPctEnabled = True
    view_model.broker_sim.takeProfitPctText = "3.5"
    config = presenter._build_run_config()
    assert config is not None
    assert config.broker_config.take_profit_pct == 3.5

    view_model.broker_sim.takeProfitPctEnabled = False
    config = presenter._build_run_config()
    assert config is not None
    assert config.broker_config.take_profit_pct is None


def test_build_run_config_ignores_malformed_take_profit_pct_text(presenter, view_model):
    """A stray non-numeric or zero/negative value in the text field must not
    crash `_build_run_config()` (`BrokerSimulationConfig` itself raises for
    `take_profit_pct <= 0`) — falls back to disabled, matching the lenient
    fallback this function already uses for `order_size_type`/`commission_type`."""
    view_model.broker_sim.takeProfitPctEnabled = True
    view_model.broker_sim.takeProfitPctText = "not-a-number"
    config = presenter._build_run_config()
    assert config is not None
    assert config.broker_config.take_profit_pct is None


def test_build_run_config_rejection_logs_error_message(presenter, view_model, caplog):
    """When a run configuration is rejected (e.g. tick mode with All History),
    the error message must be printed to the log (at ERROR level) and to the
    event logger, not merely written to the ViewModel run_result."""
    import logging

    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_state import (
        BacktestExecutionMode,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.time_range_preset import (
        TimeRangePreset,
    )

    view_model.strategy_params.selectedStrategyKey = "fake_strategy"
    view_model.initialCapitalText = "10000"
    view_model.executionMode = BacktestExecutionMode.HISTORICAL_TICK.value
    view_model.time_range.preset = TimeRangePreset.ALL_HISTORY.value

    with caplog.at_level(logging.ERROR, logger="App.BackTestPresenter"):
        config = presenter._build_run_config()

    assert config is None
    assert 'Realtime mode (tick-based) does not support "All History"' in caplog.text
    assert view_model.run_result.resultIsError is True
    assert view_model.run_result.resultText != ""
