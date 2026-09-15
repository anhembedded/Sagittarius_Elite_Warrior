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

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY

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
def mock_config():
    config = MagicMock()
    # Key-aware, not a blanket stub: a blanket `return_value = False` used to
    # be harmless (only _compute_fetch_limit's floor read it, and
    # max(75, slowest, 0) doesn't care) but BOT-034's fallback_seconds read
    # made it a real bug — False * 1000 == 0, so AutoStartController's
    # fallback timer fired almost immediately instead of never, racing the
    # test body's own action against a background _load_history() call it
    # never expected. Falling through to the caller's own `default` matches
    # what the real ConfigManager.get() does for an unset key — in
    # particular, `DEV_BOARD_AUTOSTART_ENABLED` falls through to
    # `dashboard_presenter.py`'s own `_DEFAULT_AUTOSTART_ENABLED = False`
    # (BOT-062), so auto-start is off here same as the real default.
    # BOT-066: dev.mode on for the whole suite, so any exception a
    # @safe_ui_action-decorated slot swallows re-raises instead of passing
    # a test that should have failed.
    config.get.side_effect = lambda key, default=None, cast=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    config.get_all.return_value = {}
    return config


@pytest.fixture
def equity_recorder():
    """`EPIC-023B` — a real, empty recorder by default (same shape
    `test_trading_presenter_equity.py`'s own fixture has): `.samples` must
    be a real iterable, not a `MagicMock` attribute, for
    `equity_samples_to_candles()` to accept it."""
    from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
        EquityCurveRecorder,
    )

    return EquityCurveRecorder()


@pytest.fixture
def strategy_registry():
    """`EPIC-023C` — a real registry, same shape
    `test_trading_presenter_toggle.py`'s own fixture has: `restore_into_
    view_model()` calls `sorted(self._available_strategies())`, which a bare
    `MagicMock` cannot satisfy."""
    from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
        StrategyRegistry,
    )
    from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
        EmaCrossoverStrategy,
    )

    registry = StrategyRegistry()
    registry.register("ema_crossover", EmaCrossoverStrategy)
    return registry


@pytest.fixture
def strategy_session(strategy_registry):
    """A real session over a real registry, with only the network-facing
    collaborators mocked — same fixture Trading's own tests use."""
    from Sagittarius_Elite_Warrior.src.application.services.live_strategy_factory import (
        LiveStrategyFactory,
    )
    from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
        LiveStrategySession,
    )

    factory = LiveStrategyFactory(
        strategy_registry, MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    return LiveStrategySession(factory)


@pytest.fixture
def session_state():
    """`EPIC-023D` — a real `TradingSessionState`, same reasoning
    `test_trading_presenter_toggle.py`'s own fixture documents: plain
    mutable state with no I/O, and `_refresh_session_stats()` calls
    `len(session_state.known_open_symbols)`, which a bare `MagicMock`
    cannot satisfy."""
    from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
        TradingSessionState,
    )

    return TradingSessionState()


@pytest.fixture
def fake_historical_klines():
    """`EPIC-025` PR 1.1 — the screen reads stored candles through
    `IHistoricalKlines`. The container hands out the port's verified fake, so a
    test can seed candles and assert what the screen drew, where a `MagicMock`
    could only confirm that something was called."""
    return FakeHistoricalKlines()


@pytest.fixture
def fake_market_data_sync():
    """`EPIC-025` PR 0.5 — Dev Board asks for a sync through
    `IMarketDataSync`. The container hands out the port's verified fake, not a
    `MagicMock`: the tests below assert *what was asked for*, which a mock
    cannot answer."""
    return FakeMarketDataSync()


@pytest.fixture
def mock_container(
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    equity_recorder,
    strategy_registry,
    strategy_session,
    session_state,
    fake_market_data_sync,
    fake_historical_klines,
):
    container = MagicMock()

    from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
        EquityCurveRecorder,
    )
    from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
        IndicatorScriptRegistry,
    )
    from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
        LiveStrategySession,
    )
    from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
        StrategyRegistry,
    )
    from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
        TradingSessionState,
    )
    from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
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

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == LiveStrategySession:
            return strategy_session
        if interface == IndicatorScriptRegistry:
            return script_registry
        if interface == EquityCurveRecorder:
            return equity_recorder
        if interface == TradingSessionState:
            return session_state
        if interface == IHistoricalKlines:
            return fake_historical_klines
        if interface == IMarketDataSync:
            return fake_market_data_sync
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
def presenter(view, mock_container, mock_thread_mgr):
    """
    @details BOT-034's auto-start (AutoStartController.begin() calling
    _on_start_stream(), which submits a background task and locks the FSM)
    is config-gated (BOT-062, `DEV_BOARD_AUTOSTART_ENABLED`) and off by
    default — `mock_config.get`'s side_effect (see `mock_container` above)
    falls through to that same off-by-default, so construction here never
    auto-starts: the FSM stays IDLE and no background task is submitted.
    `mock_thread_mgr.submit.reset_mock()` is kept anyway so this fixture
    stays correct even if some *other* construction step starts submitting
    — see test_autostart_controller_integration.py and the dedicated
    auto-start tests below for auto-start's own effect on a freshly-
    constructed presenter (with the config explicitly turned on).
    """
    p = DashboardPresenter(view, mock_container)
    mock_thread_mgr.submit.reset_mock()
    return p


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_initialization(presenter, view, mock_container):
    assert presenter.view == view
    assert presenter.container == mock_container
    assert presenter.fsm.current_state.name == "IDLE"


# ---------------------------------------------------------------------------
# Timeframe pin preferences wiring (EPIC-015 Phase 4 follow-up)
# ---------------------------------------------------------------------------


def test_boot_falls_back_to_an_unpersisted_store_when_none_is_registered(
    presenter, view
):
    """`mock_container` never registers `TimeframePinPreferences` —
    construction must still leave the View with a working, private store
    rather than crashing."""
    assert isinstance(view._timeframe_pin_preferences, TimeframePinPreferences)


def test_boot_wires_the_container_registered_store_into_the_view(
    qapp,
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    strategy_registry,
    strategy_session,
    fake_market_data_sync,
    fake_historical_klines,
):
    """When the container *does* have a registered store — the real
    `app_bootstrapper.py` shape — construction must hand the View that
    exact instance, so a Dev Board symbol-list rebuild reads/writes the
    same persisted, per-symbol pins as any other screen."""
    from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
        EquityCurveRecorder,
    )
    from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
        IndicatorScriptRegistry,
    )
    from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
        LiveStrategySession,
    )
    from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
        StrategyRegistry,
    )
    from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
        TradingSessionState,
    )
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    shared_store = TimeframePinPreferences()
    container = Mock()
    container.registrations.return_value = {TimeframePinPreferences: shared_store}

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == LiveStrategySession:
            return strategy_session
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IndicatorScriptRegistry:
            return IndicatorScriptRegistry()
        if interface == TimeframePinPreferences:
            return shared_store
        if interface == EquityCurveRecorder:
            return EquityCurveRecorder()
        if interface == TradingSessionState:
            return TradingSessionState()
        if interface == IHistoricalKlines:
            return fake_historical_klines
        if interface == IMarketDataSync:
            return fake_market_data_sync
        return Mock()

    container.resolve.side_effect = resolve_side_effect

    view = DashboardView()
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()

    DashboardPresenter(view, container)

    assert view._timeframe_pin_preferences is shared_store


def test_dashboard_presenter_enforces_zoom_limit(presenter):
    """
    Test that the config CHART_CARD_MAX_ZOOM_OUT_CANDLES is applied to chart cards
    both on creation and when timeframe changes.
    """
    presenter.config.get.side_effect = lambda key, default=None, cast=None: (
        1000 if key == "CHART_CARD_MAX_ZOOM_OUT_CANDLES" else default
    )

    from enum import Enum

    class PyQtGraphStateKey(str, Enum):
        LIMITS = "limits"
        X_RANGE = "xRange"

    # 1. On creation (_ensure_chart_cards)
    presenter._active_interval = "1m"
    cards = presenter._ensure_chart_cards(["BTCUSDT"])
    card = cards[0]

    # 1000 candles * 60 seconds = 60000.0
    assert (
        card.plot_layout.main_plot.getViewBox().state[PyQtGraphStateKey.LIMITS.value][
            PyQtGraphStateKey.X_RANGE.value
        ][1]
        == 60000.0
    )

    # 2. On timeframe changed
    # Mock stream controller to avoid triggering unwanted side-effects during this test
    presenter._stream_controller = MagicMock()
    presenter._on_timeframe_changed("1h")
    # The active chart card should have its limits updated in-place
    assert (
        card.plot_layout.main_plot.getViewBox().state[PyQtGraphStateKey.LIMITS.value][
            PyQtGraphStateKey.X_RANGE.value
        ][1]
        == 3600000.0
    )


def test_the_toolbars_more_button_opens_the_full_picker_on_a_real_dev_board_card(
    presenter, qapp
):
    """`EPIC-015` Phase 4 screen-level check for Dev Board: through the same
    real `ChartCard` `_ensure_chart_cards()` builds and wires
    `sig_timeframe_changed` to `_on_timeframe_changed` on, opening the "…"
    picker and choosing a card still reaches the presenter — not just
    `ChartToolbar` in isolation (`test_chart_toolbar.py` covers that
    thoroughly already)."""
    presenter._stream_controller = MagicMock()
    cards = presenter._ensure_chart_cards(["BTCUSDT"])
    card = cards[0]

    card.toolbar._open_picker()
    qapp.processEvents()
    picker = card.toolbar._picker
    assert picker is not None
    assert picker._widget_vm is card.toolbar._vm

    picker._widget_vm.choose("3d")
    qapp.processEvents()

    presenter._stream_controller._on_timeframe_changed.assert_called_once_with("3d")
    assert not picker.isVisible()


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


def test_on_load_history_does_not_touch_the_database_on_the_main_thread(
    presenter, mock_dispatcher, fake_historical_klines
):
    """The click handler submits and returns; the reading happens in the
    background.

    `EPIC-025` PR 1.1a's cleanup renamed this and added the second
    assertion. `dispatch.assert_not_called()` alone had stopped meaning
    anything once the candle read moved onto `IHistoricalKlines`: the
    handler could read every candle on disk on the main thread — freezing
    the window, which is the whole point of the test — and still dispatch
    nothing.
    """
    presenter._on_load_history()

    assert fake_historical_klines.reads == []
    mock_dispatcher.dispatch.assert_not_called()


def test_run_load_history_reads_every_symbol_in_one_call(
    presenter, fake_historical_klines
):
    """One `load_many()` for the whole symbol list, not one `load()` each.

    `EPIC-025` PR 1.1 — this is the only genuine multi-symbol reader in the
    app, and asking per symbol would serialise what the implementation is
    allowed to fetch concurrently. The old assertion said
    `dispatch.call_count == 1`; the port's own record says the same thing
    without naming the plumbing.
    """
    symbols = ["BTCUSDT", "ETHUSDT"]

    presenter._run_load_history(symbols, "1m", 5000, presenter._cancellation_token)

    assert len(fake_historical_klines.reads) == 1
    read = fake_historical_klines.reads[0]
    assert read.symbols == ("BTCUSDT", "ETHUSDT")
    assert read.interval == TimeFrame("1m")
    assert read.limit == 5000
    assert read.newest_first is True


class _RunnerThatFailsOnTheFirstSymbol:
    """A script runner that raises the first time it is fed.

    The per-symbol `try/except` inside `_run_load_history`'s loop exists for
    exactly this shape of failure: mapping the rows or feeding the scripts can
    blow up for one symbol, and a Dev Board showing four charts must still
    draw the other three. Injected as a fake rather than a `Mock` with a
    `side_effect` list, because the fake also records what it was fed and the
    test asserts on that.
    """

    def __init__(self) -> None:
        self.fed: list[int] = []
        self.active: list[str] = []

    def feed_all(self, klines) -> None:
        self.fed.append(len(klines))
        if len(self.fed) == 1:
            raise RuntimeError("script runner blew up on the first symbol")

    def rebuild(self, _klines) -> None:
        """Part of the runner's surface; unused by this path."""


def test_run_load_history_keeps_going_after_one_symbol_raises(
    presenter, fake_historical_klines
):
    """An exception for one symbol must not abort the rest of the load.

    `EPIC-025` PR 1.1 rewrote this test, and the old shape is worth naming:
    it made the *dispatcher* return a dict missing the failing symbol, which
    was never an exception at all — and after the move onto
    `IHistoricalKlines` it could not even be that, because the port promises
    every symbol asked for appears in the answer. So the failure is now
    injected where one can really happen: inside the loop, after the read.

    Remove the `try/except` in `_run_load_history` and this test errors out
    rather than failing softly, which is the point.
    """
    fake_historical_klines.seed(
        [
            _make_stored_kline(1000.0, symbol="BTCUSDT"),
            _make_stored_kline(1000.0, symbol="ETHUSDT"),
        ]
    )
    runner = _RunnerThatFailsOnTheFirstSymbol()
    presenter._stream_controller._script_runner = runner
    logs: list[str] = []
    reloaded: list[str] = []
    presenter.ui_log_signal.connect(logs.append)
    presenter.ui_history_reloaded_signal.connect(
        lambda symbol, _candles, _volume: reloaded.append(symbol)
    )

    presenter._run_load_history(
        ["BTCUSDT", "ETHUSDT"], "1m", 100, presenter._cancellation_token
    )

    assert any("Exception while loading history for BTCUSDT" in log for log in logs)
    # Both charts drew: the loop reaches `_emit_history_reloaded` *before*
    # feeding the scripts, so the symbol that raised still shows its candles
    # and only loses its indicator lines — the degradation the per-symbol
    # `try/except` is there to keep local.
    assert reloaded == ["BTCUSDT", "ETHUSDT"]
    assert runner.fed == [1, 1], (
        "the second symbol was still fed after the first raised"
    )


def test_run_load_history_logs_a_symbol_with_nothing_stored_and_loads_the_rest(
    presenter, fake_historical_klines
):
    """The ordinary case the old exception test was actually exercising: a
    symbol the user has never synced. It is not an error — the port answers
    for every symbol asked about, with an empty tuple — so the screen says so
    for that one and draws the others.
    """
    fake_historical_klines.seed([_make_stored_kline(1000.0, symbol="ETHUSDT")])
    logs: list[str] = []
    reloaded: list[str] = []
    presenter.ui_log_signal.connect(logs.append)
    presenter.ui_history_reloaded_signal.connect(
        lambda symbol, _candles, _volume: reloaded.append(symbol)
    )

    presenter._run_load_history(
        ["BTCUSDT", "ETHUSDT"], "1m", 100, presenter._cancellation_token
    )

    assert any("No historical data found for BTCUSDT." in log for log in logs)
    assert reloaded == ["ETHUSDT"]


# ---------------------------------------------------------------------------
# _compute_fetch_limit (BOT-034) — render window decoupled from fetch amount
# ---------------------------------------------------------------------------


def _use_real_config_defaults(presenter) -> None:
    """The shared mock_config fixture stubs .get() to always return False —
    fine for the boolean checks elsewhere, but _compute_fetch_limit needs a
    config that actually honors the `default` argument it's passed."""
    presenter.config.get.side_effect = lambda key, default=None, cast=None: default


def test_fetch_limit_defaults_to_the_render_window_with_nothing_enabled(presenter):
    _use_real_config_defaults(presenter)

    assert presenter._compute_fetch_limit() == 75


def test_fetch_limit_grows_for_an_enabled_scripts_warmup(presenter):
    """ema_ribbon's slowest line is EMA 200 — min_warmup_bars=200 must win
    over the 75-candle render window."""
    _use_real_config_defaults(presenter)
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]

    assert presenter._compute_fetch_limit() == 200


def test_fetch_limit_honors_a_higher_config_floor(presenter):
    presenter.config.get.side_effect = lambda key, default=None, cast=None: (
        500 if key == "CHART_CARD_MIN_FETCH_CANDLES" else default
    )

    assert presenter._compute_fetch_limit() == 500


def test_fetch_limit_ignores_a_config_floor_lower_than_the_render_window(presenter):
    presenter.config.get.side_effect = lambda key, default=None, cast=None: (
        10 if key == "CHART_CARD_MIN_FETCH_CANDLES" else default
    )

    assert presenter._compute_fetch_limit() == 75


def test_on_load_history_submits_the_computed_fetch_limit(presenter, mock_thread_mgr):
    _use_real_config_defaults(presenter)
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]

    presenter._on_load_history()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[3] == 200  # limit positional arg


# ---------------------------------------------------------------------------
# Symbol / Start-End date (BOT-033 Phase 2) — read from the ViewModel and
# validated before anything is dispatched, instead of a hard-coded symbol
# and an ignored date range.
# ---------------------------------------------------------------------------


def test_on_load_history_uses_the_view_models_symbol(presenter, mock_thread_mgr):
    presenter._view_model.symbol = "BTCUSDT"

    presenter._on_load_history()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[1] == ["BTCUSDT"]  # symbols positional arg
    assert presenter._active_symbol == "BTCUSDT"


def test_on_load_history_normalizes_the_symbol(presenter, mock_thread_mgr):
    """Lowercase/whitespace input is corrected, not rejected — matches every
    other symbol entry point in this codebase (CLI handlers,
    SyncMarketDataCommand's own validator)."""
    presenter._view_model.symbol = "  btcusdt  "

    presenter._on_load_history()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[1] == ["BTCUSDT"]


def test_on_load_history_rejects_an_invalid_symbol(presenter, mock_thread_mgr):
    presenter._view_model.symbol = "BT"  # too short to be a real pair

    presenter._on_load_history()

    assert mock_thread_mgr.submit.call_count == 0
    assert presenter._view_model.log_model.entries[-1].level == "error"


def test_on_load_history_rejects_an_unparseable_date(presenter, mock_thread_mgr):
    presenter._view_model.startDate = "not a date"

    presenter._on_load_history()

    assert mock_thread_mgr.submit.call_count == 0
    assert presenter._view_model.log_model.entries[-1].level == "error"


def test_on_load_history_rejects_a_start_date_not_before_end_date(
    presenter, mock_thread_mgr
):
    presenter._view_model.startDate = "2024-01-02 00:00"
    presenter._view_model.endDate = "2024-01-01 00:00"

    presenter._on_load_history()

    assert mock_thread_mgr.submit.call_count == 0
    assert presenter._view_model.log_model.entries[-1].level == "error"


def test_on_load_history_submits_the_parsed_date_range(presenter, mock_thread_mgr):
    from datetime import datetime

    presenter._view_model.startDate = "2024-01-01 00:00"
    presenter._view_model.endDate = "2024-01-02 00:00"

    presenter._on_load_history()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[5] == datetime(2024, 1, 1, tzinfo=UTC)  # start_time
    assert submit_args[6] == datetime(2024, 1, 2, tzinfo=UTC)  # end_time


def test_run_load_history_gives_the_port_the_picked_date_range(
    presenter, fake_historical_klines
):
    """`EPIC-025` PR 1.1 — the same guarantee, read off the port instead of a
    dispatched query object. It is the other half of `BUG-106`: the Data Range
    picker must bound what the chart *reads* while never bounding the sync."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 2, tzinfo=UTC)

    presenter._run_load_history(
        ["BTCUSDT"], "1m", 100, presenter._cancellation_token, start, end
    )

    read = fake_historical_klines.reads[0]
    assert read.start_time == start
    assert read.end_time == end


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


def test_on_start_stream_submits_the_computed_fetch_limit(presenter, mock_thread_mgr):
    _use_real_config_defaults(presenter)
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]

    presenter._on_start_stream()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[4] == 200  # limit positional arg


def test_run_sync_and_start_full_workflow(
    presenter, mock_dispatcher, fake_market_data_sync, fake_historical_klines
):
    """Sync → read history → start the stream, **in that order**.

    The order is the guarantee, not the three calls: a stream opened before
    the history read would draw live ticks onto a chart with no candles
    behind them, and a history read before the sync finished would draw
    yesterday's data and then never refresh it.

    `EPIC-025` PR 0.5 moved the sync onto a port and PR 1.1a the history
    read, so the three steps now happen through three different mechanisms
    and no single call list can order them. PR 1.1a's cleanup restored the
    assertion with the journal below — for one revision the test asserted
    only that all three had happened, while its own name still said "in
    order".
    """
    mock_dispatcher.dispatch.return_value = []
    journal: list[str] = []
    sync_request = fake_market_data_sync.sync
    history_read = fake_historical_klines.load_many

    def record_sync(request):
        journal.append("sync")
        return sync_request(request)

    def record_read(*args, **kwargs):
        journal.append("history")
        return history_read(*args, **kwargs)

    def record_dispatch(command_type, command):
        if command_type is StartLiveStreamCommand:
            journal.append("stream")
        return []

    fake_market_data_sync.sync = record_sync
    fake_historical_klines.load_many = record_read
    mock_dispatcher.dispatch.side_effect = record_dispatch

    from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

    # Real callers only ever reach this method after _on_start_stream() has
    # already moved the FSM to LOCKED (BOT-066: dev-mode re-raise surfaced
    # that the blanket `[]` dispatch stub above makes StartLiveStreamCommand
    # look like a failure, driving _on_stream_start_failed's IDLE->ERROR —
    # invalid from the presenter fixture's default IDLE, only from here).
    presenter.fsm.transition_to(UIMode.LOCKED)

    presenter._run_sync_and_start(
        ["BTCUSDT"], TimeFrame("1m"), "1m", 5000, presenter._cancellation_token
    )

    assert journal == ["sync", "history", "stream"]
    # And each step was about the symbol asked for, which the journal alone
    # cannot say.
    assert fake_market_data_sync.was_asked_for("BTCUSDT")
    assert fake_historical_klines.was_read_for("BTCUSDT")


def test_on_start_stream_uses_the_view_models_symbol(presenter, mock_thread_mgr):
    presenter._view_model.symbol = "BTCUSDT"

    presenter._on_start_stream()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[1] == ["BTCUSDT"]  # symbols positional arg
    assert presenter._active_symbol == "BTCUSDT"


def test_on_start_stream_rejects_an_invalid_symbol_without_locking_the_fsm(
    presenter, mock_thread_mgr
):
    presenter._view_model.symbol = "!!"

    presenter._on_start_stream()

    assert mock_thread_mgr.submit.call_count == 0
    assert presenter.fsm.current_state.name == "IDLE"
    assert presenter._view_model.log_model.entries[-1].level == "error"


def test_on_start_stream_rejects_a_start_date_not_before_end_date(
    presenter, mock_thread_mgr
):
    presenter._view_model.startDate = "2024-01-02 00:00"
    presenter._view_model.endDate = "2024-01-01 00:00"

    presenter._on_start_stream()

    assert mock_thread_mgr.submit.call_count == 0
    assert presenter.fsm.current_state.name == "IDLE"


def test_on_start_stream_submits_the_parsed_date_range(presenter, mock_thread_mgr):
    from datetime import datetime

    presenter._view_model.startDate = "2024-01-01 00:00"
    presenter._view_model.endDate = "2024-01-02 00:00"

    presenter._on_start_stream()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[6] == datetime(2024, 1, 1, tzinfo=UTC)  # start_time
    assert submit_args[7] == datetime(2024, 1, 2, tzinfo=UTC)  # end_time


def test_run_sync_and_start_never_forwards_the_date_range_to_the_sync(
    presenter, mock_dispatcher, fake_market_data_sync
):
    """`BUG-106`: the Data Range picker's start/end must bound only what
    `_run_load_history` shows on the chart (a cheap local DB read) — never
    what `SyncMarketDataCommand` fetches from the exchange. A wide picked
    range (here 1 day, but the reported case was a 7-day default combined
    with a `1s` default interval) handed straight to the sync command made
    it fetch every candle across the whole range instead of just the delta
    since the latest locally known one."""
    from datetime import datetime

    from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

    mock_dispatcher.dispatch.return_value = []
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 2, tzinfo=UTC)

    # See test_run_sync_and_start_full_workflow — real callers reach this
    # only after the FSM is already LOCKED.
    presenter.fsm.transition_to(UIMode.LOCKED)

    presenter._run_sync_and_start(
        ["BTCUSDT"],
        TimeFrame("1m"),
        "1m",
        5000,
        presenter._cancellation_token,
        start,
        end,
    )

    request = fake_market_data_sync.requests[0]
    assert request.start_time is None
    assert request.end_time is None


def test_run_sync_and_start_still_loads_history_for_the_picked_date_range(
    presenter, fake_historical_klines, mock_dispatcher
):
    """The other half of `BUG-106`'s fix: `_run_load_history` (the chart's
    local-DB read) must keep honouring the picked range exactly as before —
    only the network sync step changed."""
    from datetime import datetime

    from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

    mock_dispatcher.dispatch.return_value = []
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 2, tzinfo=UTC)
    presenter.fsm.transition_to(UIMode.LOCKED)

    presenter._run_sync_and_start(
        ["BTCUSDT"],
        TimeFrame("1m"),
        "1m",
        5000,
        presenter._cancellation_token,
        start,
        end,
    )

    # `BUG-106`'s other half, now read off the port: the picked range must
    # bound the local history read even though the sync above was deliberately
    # given `None`. One range, two different answers, which is the whole point
    # of the bug.
    read = fake_historical_klines.reads[0]
    assert read.start_time == start
    assert read.end_time == end


# ---------------------------------------------------------------------------
# Cancellation token (BOT-034) — cooperative early-exit for background work,
# so a torn-down chart/view is never touched after the user has stopped.
# ---------------------------------------------------------------------------


def test_run_load_history_does_nothing_with_an_already_cancelled_token(
    presenter, mock_dispatcher
):
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

    token = CancellationToken()
    token.cancel()

    presenter._run_load_history(["BTCUSDT"], "1m", 100, token)

    mock_dispatcher.dispatch.assert_not_called()


def test_run_sync_and_start_stops_after_step_1_when_cancelled(
    presenter, mock_dispatcher, fake_market_data_sync
):
    """Sync (Step 1) always runs — cancellation is checked *between* steps,
    not before the first one — but History (Step 2) and Start Stream
    (Step 3) must not run once cancelled."""
    from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

    token = CancellationToken()
    token.cancel()
    mock_dispatcher.dispatch.return_value = []

    presenter._run_sync_and_start(["BTCUSDT"], TimeFrame("1m"), "1m", 5000, token)

    # The sync ran (step 1) and nothing after it: no history read, no stream.
    assert len(fake_market_data_sync.requests) == 1
    assert mock_dispatcher.dispatch.call_args_list == []


def test_stop_stream_cancels_the_current_token_and_issues_a_fresh_one(presenter):
    old_token = presenter._cancellation_token
    # Real callers only reach Stop once already LIVE (BOT-066: dev-mode
    # re-raise surfaced that _on_stop_stream()'s success path unconditionally
    # transitions to IDLE, invalid from this fixture's default IDLE state).
    presenter.fsm.transition_to(UIMode.LOCKED)
    presenter.fsm.transition_to(UIMode.LIVE)

    presenter._on_stop_stream()

    assert old_token.is_cancelled()
    assert presenter._cancellation_token is not old_token
    assert not presenter._cancellation_token.is_cancelled()


def test_stop_stream_from_locked_returns_to_idle_instead_of_raising(presenter):
    """BOT-123: Stop (and the progress banner's Cancel, which fires the same
    request) is now enabled while `LOCKED` — a sync in progress — not just
    `LIVE`, specifically so a user can cancel it. The comment on the test
    above already documented that `_on_stop_stream()`'s unconditional
    `fsm.transition_to(UIMode.IDLE)` is only valid from `LIVE`; `LOCKED` was
    never added to the transition matrix because nothing could reach Stop
    from `LOCKED` before this task. Without `LOCKED -> IDLE` declared, the
    very first legitimate click during a sync raises
    `InvalidStateTransitionError` (caught by `safe_ui_action` in production,
    but re-raised under dev.mode), and — worse — the transition never
    happens, so `uiMode` stays stuck at `LOCKED` with every Dev Board control
    disabled until the app is restarted, even though the sync's
    cancellation token really was cancelled."""
    presenter.fsm.transition_to(UIMode.LOCKED)

    presenter._on_stop_stream()

    assert presenter.fsm.current_state == UIMode.IDLE


def test_stop_stream_is_a_no_op_once_already_idle(presenter):
    """Defends the fix above from its own edge case: the progress banner's
    Cancel button has no FSM-based enablement (unlike the top-level Stop
    button) — it stays visible/clickable for as long as
    `DashboardQmlViewModel.progressVisible` is true, which lags behind the
    FSM's own return to `IDLE` (set synchronously here, but the background
    worker's `finally` that hides the bar runs later, asynchronously). A
    second click landing in that window must not attempt an
    `IDLE -> IDLE` self-transition, which the matrix does not declare
    either."""
    presenter.fsm.transition_to(UIMode.LOCKED)
    presenter._on_stop_stream()
    assert presenter.fsm.current_state == UIMode.IDLE

    presenter._on_stop_stream()

    assert presenter.fsm.current_state == UIMode.IDLE


# ---------------------------------------------------------------------------
# _on_timeframe_changed (BOT-033) — ChartToolbar.sig_timeframe_changed handler
# ---------------------------------------------------------------------------


def test_timeframe_changed_to_the_same_value_is_a_no_op(presenter, mock_thread_mgr):
    assert presenter._active_interval == "1m"

    presenter._on_timeframe_changed("1m")

    assert mock_thread_mgr.submit.call_count == 0


def test_timeframe_changed_while_idle_updates_interval_and_reloads(
    presenter, mock_thread_mgr
):
    presenter._on_timeframe_changed("5m")

    assert presenter._active_interval == "5m"
    assert mock_thread_mgr.submit.call_count == 1
    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_load_history
    assert submit_args[2] == "5m"  # interval_str positional arg


def test_timeframe_changed_while_history_loading_does_not_reload(
    presenter, mock_thread_mgr
):
    # BOT-069 — historyLoading is now a display mirror, not the gate;
    # _on_timeframe_changed reads the real source of truth,
    # StreamLifecycleController's shared ExclusiveAction instance.
    presenter._stream_controller._stream_actions.try_start("load_history")

    presenter._on_timeframe_changed("5m")

    assert presenter._active_interval == "5m"
    assert mock_thread_mgr.submit.call_count == 0


def test_timeframe_changed_while_live_stops_then_restarts(presenter, mock_thread_mgr):

    presenter.fsm.transition_to(UIMode.LOCKED)
    presenter.fsm.transition_to(UIMode.LIVE)

    presenter._on_timeframe_changed("15m")

    assert presenter._active_interval == "15m"
    assert presenter.fsm.current_state.name == "LOCKED"  # _on_start_stream re-locked it
    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_sync_and_start
    assert submit_args[3] == "15m"  # interval_str positional arg


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------


def test_on_load_history_exception_is_caught_by_safe_ui_action(presenter):
    """@safe_ui_action catches exceptions from _ensure_chart_cards without crashing
    — in production mode specifically (BOT-066: this fixture's config otherwise
    has dev.mode on for the rest of the suite, which re-raises instead)."""
    presenter.config.get.side_effect = lambda key, default=None, cast=None: default
    presenter._ensure_chart_cards = MagicMock(side_effect=ValueError("Test Exception"))

    logs = []
    presenter.ui_log_signal.connect(logs.append)

    presenter._on_load_history()

    assert any(
        "Test Exception" in log or "_on_load_history failed" in log for log in logs
    )


# ---------------------------------------------------------------------------
# Indicator control (BOT-032 Phase 6) — every indicator is a script now, no
# RSI/EMA/MACD is hardcoded in the engine. Reading the enabled set and
# feeding candles through it is IndicatorScriptRunner's job (see
# test_indicator_script_runner.py); these tests only pin down that the
# Presenter actually calls it at the right times.
# ---------------------------------------------------------------------------


def _make_kline(timestamp: float, close_price: float) -> MagicMock:
    kline = MagicMock()
    kline.close_time.timestamp.return_value = timestamp
    kline.close_price = close_price
    return kline


def test_on_load_history_runs_no_scripts_when_none_enabled(presenter):
    """The view model's checklist starts unchecked — nothing runs."""
    presenter._on_load_history()

    assert presenter._script_runner.active == {}


def test_on_load_history_runs_the_enabled_scripts(presenter):
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]

    presenter._on_load_history()

    assert "ema_ribbon" in presenter._script_runner.active


def test_a_historical_batch_emits_indicator_data_once_warmed_up(presenter):
    """Feeding enough candles for ema_cross (EMA 12/26) must reach
    ui_indicator_data_signal with a namespaced curve name — the same
    warm-up-drops-None contract BOT-020's indicators always had, now
    observed through the script path instead of a hardcoded one."""
    presenter._enabled_script_keys = lambda: ["ema_cross"]
    presenter._rebuild_scripts()

    emitted = []
    presenter.ui_indicator_data_signal.connect(
        lambda name, x, y: emitted.append((name, x, y))
    )

    klines = [_make_kline(1000.0 + i, 100.0 + i) for i in range(30)]
    presenter._script_runner.feed_all(klines)

    names = {name for name, _, _ in emitted}
    assert any(name.startswith("ema_cross:") for name in names)


def test_on_indicator_data_ignores_an_unrecognised_bare_name(presenter):
    """A name with no `key:line` separator has no script to route to — must
    be a silent no-op, not a crash (there is no "built-in" fallback anymore,
    BOT-032 Phase 6 removed the last one)."""
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}

    presenter._on_indicator_data("EMA(20)", [1.0], [100.0])

    mock_card.add_overlay_indicator.assert_not_called()
    mock_card.update_indicator_data.assert_not_called()


def test_indicator_data_routes_to_the_chart_of_the_active_symbol(presenter):
    """BOT-033 Phase 2 — regression test for a bug _active_symbol fixes:
    _on_indicator_data used to look the chart card up by the
    _DEFAULT_SYMBOLS[0] constant ("ETHUSDT") no matter what symbol was
    actually loaded, so switching to e.g. BTCUSDT silently stopped every
    indicator line from reaching its chart (the card existed, keyed
    correctly by _ensure_chart_cards, but nothing looked it up under its
    real key anymore)."""
    presenter._active_symbol = "BTCUSDT"
    mock_card = MagicMock()
    presenter.active_charts = {"BTCUSDT": mock_card}
    presenter._script_runner.draw = MagicMock()

    presenter._on_indicator_data("ema_cross:fast", [1.0], [100.0])

    presenter._script_runner.draw.assert_called_once_with(
        mock_card, "ema_cross:fast", [1.0], [100.0]
    )


def test_rebuild_scripts_clears_the_chart_of_the_active_symbol(presenter):
    """Same bug/fix as above, for _rebuild_scripts' clear_from_chart call."""
    presenter._active_symbol = "BTCUSDT"
    mock_card = MagicMock()
    presenter.active_charts = {"BTCUSDT": mock_card}
    presenter._script_runner.clear_from_chart = MagicMock()

    presenter._rebuild_scripts()

    presenter._script_runner.clear_from_chart.assert_called_once_with(mock_card)


# ---------------------------------------------------------------------------
# BOT-035 — load more history on scroll
# ---------------------------------------------------------------------------


def _make_stored_kline(
    close_timestamp: float, close_price: float = 100.0, *, symbol: str = "ETHUSDT"
):
    """A real `MarketData` row, for tests whose candles must survive a store.

    `_make_full_kline` below returns a `MagicMock`, which was enough while the
    history arrived through a stubbed dispatcher. `EPIC-025` PR 1.1 reads it
    through `IHistoricalKlines`, whose fake keys rows on `open_time` exactly as
    the real repository does — and a `MagicMock` has no real `open_time` to key
    on. The open time is one minute before the close, matching the 1m cadence
    these tests use.
    """
    close_time = datetime.fromtimestamp(close_timestamp, tz=UTC)
    return MarketData(
        symbol=symbol,
        interval="1m",
        open_time=close_time - timedelta(minutes=1),
        open_price=99.0,
        high_price=101.0,
        low_price=98.0,
        close_price=close_price,
        volume=10.0,
        close_time=close_time,
        quote_asset_volume=0.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.0,
        taker_buy_quote_asset_volume=0.0,
    )


def _make_full_kline(
    close_timestamp: float,
    close_price: float = 100.0,
    open_price: float = 99.0,
    high_price: float = 101.0,
    low_price: float = 98.0,
    volume: float = 10.0,
):
    """Unlike _make_kline (feed()-only tests), this fills every field
    map_klines/map_volume actually read — real float() coercion, not a
    MagicMock stand-in, since those two are module-level functions and would raise on
    an un-configured attribute."""
    kline = MagicMock()
    kline.close_time.timestamp.return_value = close_timestamp
    kline.close_price = close_price
    kline.open_price = open_price
    kline.high_price = high_price
    kline.low_price = low_price
    kline.volume = volume
    return kline


def test_on_near_left_edge_asks_pagination_controller_for_the_oldest_timestamp(
    presenter,
):
    mock_card = MagicMock()
    mock_card._raw_history = [(1000.0, 1, 2, 0, 1), (1060.0, 1, 2, 0, 1)]
    presenter.active_charts = {"ETHUSDT": mock_card}
    calls = []
    presenter._pagination.on_near_left_edge = lambda s, t: calls.append((s, t))

    presenter._on_near_left_edge("ETHUSDT")

    assert calls == [("ETHUSDT", 1000.0)]


def test_on_near_left_edge_is_a_no_op_with_no_chart_or_empty_history(presenter):
    calls = []
    presenter._pagination.on_near_left_edge = lambda s, t: calls.append((s, t))

    presenter._on_near_left_edge("UNKNOWN_SYMBOL")
    presenter.active_charts["ETHUSDT"] = MagicMock(_raw_history=[])
    presenter._on_near_left_edge("ETHUSDT")

    assert calls == []


def test_fetch_older_history_submits_the_load_more_background_task(
    presenter, mock_thread_mgr
):
    presenter._fetch_older_history("ETHUSDT", 1000.0)

    assert mock_thread_mgr.submit.call_count == 1
    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_load_more_history
    assert submit_args[1:5] == (
        "ETHUSDT",
        presenter._active_interval,
        1000.0,
        75,
    )
    assert submit_args[5] is presenter._cancellation_token


def test_fetch_older_history_honors_a_configured_batch_size(presenter, mock_thread_mgr):
    presenter.config.get.side_effect = lambda key, default=None, cast=None: (
        250 if key == "CHART_CARD_LOAD_MORE_BATCH_CANDLES" else default
    )

    presenter._fetch_older_history("ETHUSDT", 1000.0)

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[1:5] == ("ETHUSDT", presenter._active_interval, 1000.0, 250)


def test_run_load_more_history_asks_for_the_newest_page_below_the_boundary(
    presenter, fake_historical_klines
):
    """Paging backwards: bounded above by what the chart already holds, and
    `newest_first` so the page is the candles just before that boundary rather
    than the oldest in the shard."""
    fake_historical_klines.seed([_make_stored_kline(900.0)])

    presenter._run_load_more_history(
        "ETHUSDT", "1m", 1000.0, 75, presenter._cancellation_token
    )

    read = fake_historical_klines.reads[0]
    assert read.symbols == ("ETHUSDT",)
    assert read.limit == 75
    assert read.newest_first is True
    assert read.end_time.timestamp() == 1000.0


def test_run_load_more_history_filters_out_the_boundary_candle(
    presenter, fake_historical_klines
):
    """The repository's end_time filter is inclusive (open_time <= end_time)
    — a returned candle at/after the timestamp we already have on the chart
    must be dropped client-side, or it would render as a duplicate."""
    fake_historical_klines.seed(
        [
            _make_stored_kline(1000.0),  # == the oldest already loaded — must drop
            _make_stored_kline(940.0),  # genuinely older — must keep
        ]
    )
    emitted = []
    presenter.ui_history_prepended_signal.connect(
        lambda symbol, candles, volume: emitted.append((symbol, candles, volume))
    )

    presenter._run_load_more_history(
        "ETHUSDT", "1m", 1000.0, 75, presenter._cancellation_token
    )

    assert len(emitted) == 1
    _symbol, candles, _volume = emitted[0]
    assert len(candles) == 1
    assert candles[0][0] == 940.0


def test_run_load_more_history_emits_nothing_when_no_older_data_exists(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = []
    emitted = []
    presenter.ui_history_prepended_signal.connect(lambda *a: emitted.append(a))
    finished = []
    presenter.ui_history_prepend_finished_signal.connect(lambda *a: finished.append(a))

    presenter._run_load_more_history(
        "ETHUSDT", "1m", 1000.0, 75, presenter._cancellation_token
    )

    assert emitted == []
    # Unconditional — the pagination controller must still unlock. found_more
    # is False here — nothing was found, so HistoryPaginationController must
    # not arm an auto-recheck (it would loop forever, see its docstring).
    assert finished == [("ETHUSDT", False)]


def test_run_load_more_history_does_nothing_with_an_already_cancelled_token(
    presenter, mock_dispatcher
):
    presenter._cancellation_token.cancel()

    presenter._run_load_more_history(
        "ETHUSDT", "1m", 1000.0, 75, presenter._cancellation_token
    )

    mock_dispatcher.dispatch.assert_not_called()


def test_on_history_prepended_prepends_to_the_chart_and_rebuilds_scripts(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]
    presenter._raw_klines_by_symbol["ETHUSDT"] = [_make_full_kline(1000.0)]
    older = [_make_full_kline(940.0)]
    mapped = map_klines(older)
    volume = map_volume(older)

    presenter._on_history_prepended("ETHUSDT", mapped, volume)

    mock_card.prepend_historical_data.assert_called_once_with(mapped)
    mock_card.prepend_historical_volume.assert_called_once_with(volume)
    assert "ema_ribbon" in presenter._script_runner.active


def test_on_history_prepended_is_a_no_op_with_no_candles(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}

    presenter._on_history_prepended("ETHUSDT", [], [])

    mock_card.prepend_historical_data.assert_not_called()


def test_on_history_prepend_finished_unlocks_the_pagination_controller(presenter):
    calls = []
    presenter._pagination.on_load_more_finished = lambda *a: calls.append(a)

    presenter._on_history_prepend_finished("ETHUSDT", True)

    assert calls == [("ETHUSDT", True)]


def test_run_load_more_history_reports_found_more_when_data_arrives(
    presenter, fake_historical_klines
):
    fake_historical_klines.seed([_make_stored_kline(900.0)])
    finished = []
    presenter.ui_history_prepend_finished_signal.connect(lambda *a: finished.append(a))

    presenter._run_load_more_history(
        "ETHUSDT", "1m", 1000.0, 75, presenter._cancellation_token
    )

    assert finished == [("ETHUSDT", True)]


def test_a_live_tick_extends_the_raw_kline_cache_for_a_later_prepend_rebuild(
    presenter,
):
    """Without this, a load-more's rebuild+refeed after some live ticks have
    already closed would silently drop those candles from every script."""
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter._raw_klines_by_symbol["ETHUSDT"] = [_make_full_kline(1000.0)]

    presenter._on_ui_chart_update(
        "ETHUSDT", 1060.0, 99.0, 101.0, 98.0, 100.0, 10.0, True
    )

    assert len(presenter._raw_klines_by_symbol["ETHUSDT"]) == 2
    assert (
        presenter._raw_klines_by_symbol["ETHUSDT"][-1].close_time.timestamp() == 1060.0
    )


def test_a_live_tick_tags_the_cached_candle_with_the_active_interval(presenter):
    """Regression: _tick_to_candle used to hard-code "1m" via the
    _DEFAULT_INTERVAL_STR module constant regardless of _active_interval
    (BOT-034 replaced every OTHER read site with the instance attribute but
    missed this one) — silently mislabeling every live-tick candle appended
    to _raw_klines_by_symbol once a user picked a timeframe other than
    "1m"."""
    presenter._active_interval = "5m"
    presenter.active_charts = {"ETHUSDT": MagicMock()}

    presenter._on_ui_chart_update(
        "ETHUSDT", 1000.0, 99.0, 101.0, 98.0, 100.0, 10.0, True
    )

    candle = presenter._raw_klines_by_symbol["ETHUSDT"][-1]
    assert candle.interval == "5m"


# ---------------------------------------------------------------------------
# ViewModel bridging — top bar / WS badge / log panel
# ---------------------------------------------------------------------------


def test_price_ticker_updates_on_chart_tick(presenter):
    presenter.active_charts = {"ETHUSDT": MagicMock()}

    presenter._on_ui_chart_update("ETHUSDT", 1.0, 100.0, 101.0, 99.0, 100.5, 5.0, True)

    assert "ETHUSDT" in presenter._view_model.priceTickerText
    assert "100.50" in presenter._view_model.priceTickerText


def test_ws_status_badge_reflects_fsm_state(presenter):

    presenter.fsm.transition_to(UIMode.LOCKED)

    assert presenter._view_model.wsStatusText == "WS: SYNCING"


def test_ws_status_badge_tone_matches_every_ui_mode(presenter):
    """`EPIC-015` Phase 4 — `StatusPill.qml`'s semantic tone
    (`"idle"|"active"|"success"|"danger"`) must be derived from `UIMode`,
    not reverse-engineered from a colour string (`dashboard_presenter.py`'s
    `_WS_STATUS_BY_MODE` comment). Pins the exact mapping the task
    requires: IDLE->idle, LOCKED->active ("SYNCING"), LIVE->success,
    ERROR->danger.

    ERROR is asserted via the emitted signal sequence, not the value left
    behind after `transition_to()` returns: `_on_fsm_error` (an existing
    hook, predating this task) auto-recovers ERROR->IDLE synchronously,
    inside the same reentrant-lock call (`BaseStateMachine` uses
    `threading.RLock`) — the global callback that paints the badge fires
    again for that inner ERROR->IDLE transition before the outer call
    returns, so by then the badge has already settled back to idle. That
    behaviour is not this task's concern; only that "danger" was really
    reached in between is.
    """
    vm = presenter._view_model
    seen_tones: list[str] = []
    vm.wsStatusChanged.connect(lambda: seen_tones.append(vm.wsStatusTone))

    assert vm.wsStatusTone == "idle"  # construction-time default (IDLE)

    presenter.fsm.transition_to(UIMode.LOCKED)
    assert vm.wsStatusTone == "active"

    presenter.fsm.transition_to(UIMode.LIVE)
    assert vm.wsStatusTone == "success"

    presenter.fsm.transition_to(UIMode.ERROR)
    assert "danger" in seen_tones
    assert vm.wsStatusTone == "idle"


# ---------------------------------------------------------------------------
# Auto-start (BOT-034) — construction-time wiring. Uses `view`/`mock_container`
# directly (not the `presenter` fixture, which deliberately resets past
# auto-start's own effect for every other test — see its docstring) so these
# can observe the real moment of construction. Auto-start is config-gated
# and off by default (BOT-062) — each test below explicitly flips
# `DEV_BOARD_AUTOSTART_ENABLED` on via `mock_config`, since that's no longer
# `mock_container`'s implicit behavior.
# ---------------------------------------------------------------------------


def _enable_autostart(mock_config) -> None:
    mock_config.get.side_effect = lambda key, default=None, cast=None: (
        True if key == "DEV_BOARD_AUTOSTART_ENABLED" else default
    )


def test_construction_auto_starts_immediately(
    view, mock_container, mock_config, mock_thread_mgr
):
    _enable_autostart(mock_config)

    p = DashboardPresenter(view, mock_container)

    assert p.fsm.current_state.name == "LOCKED"
    assert mock_thread_mgr.submit.call_count == 1
    assert mock_thread_mgr.submit.call_args[0][0] == p._run_sync_and_start


def test_starting_live_manually_while_autostart_pending_is_rejected(
    view, mock_container, mock_config, mock_thread_mgr
):
    """The FSM-state guard added alongside auto-start (BOT-034) — without
    it, a manual Start Live click during the auto-start window would raise
    InvalidStateTransitionError (LOCKED -> LOCKED)."""
    _enable_autostart(mock_config)
    p = DashboardPresenter(view, mock_container)
    mock_thread_mgr.submit.reset_mock()

    p._on_start_stream()

    assert mock_thread_mgr.submit.call_count == 0
    assert p.fsm.current_state.name == "LOCKED"


def test_a_market_tick_cancels_the_autostart_fallback_timer(
    view, mock_container, mock_config
):
    _enable_autostart(mock_config)
    p = DashboardPresenter(view, mock_container)
    assert p._autostart._timer is not None  # fallback armed by construction

    p._on_ui_chart_update("ETHUSDT", 1.0, 100.0, 101.0, 99.0, 100.5, 5.0, False)

    assert p._autostart._timer is None


def test_a_market_tick_does_not_crash_when_autostart_is_disabled(view, mock_container):
    """BOT-062: with `DEV_BOARD_AUTOSTART_ENABLED` at its real default
    (`False` — `mock_config.get`'s side_effect falls through to the
    caller's own default, same as the real `ConfigManager`), `__init__`
    never assigns `self._autostart` at all. `_on_ui_chart_update` used to
    call `self._autostart.on_market_tick()` unconditionally, so a live tick
    arriving with auto-start off crashed with `AttributeError` — the
    default configuration was unusable the moment a real tick landed."""
    p = DashboardPresenter(view, mock_container)

    p._on_ui_chart_update(
        "ETHUSDT", 1.0, 100.0, 101.0, 99.0, 100.5, 5.0, False
    )  # must not raise


# ---------------------------------------------------------------------------
# Custom indicator scripts (BOT-032) — presenter side only.
# The runner's own behaviour is covered in test_indicator_script_runner.py.
# ---------------------------------------------------------------------------


def _make_market_data(close: float, index: int):
    """A real MarketData — scripts take the whole candle, so a MagicMock would
    not exercise the real path."""
    from datetime import UTC, datetime, timedelta

    from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData

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


def test_script_lines_are_routed_to_the_runner(presenter):
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


def test_script_region_signal_reaches_the_runner_and_the_chart(presenter):
    """Emitting through the runner's region callback must reach the
    presenter's own signal, and the presenter's slot must forward it to the
    active chart card — the same round trip as line data."""
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]
    presenter._rebuild_scripts()

    reached = []
    presenter.ui_script_region_signal.connect(lambda key, spans: reached.append(key))
    presenter._script_runner._emit_region("ema_ribbon", [(1.0, 61.0, "#e74c3c", 0.08)])

    assert reached == ["ema_ribbon"]
    mock_card.set_script_regions.assert_called_once_with(
        "ema_ribbon", [(1.0, 61.0, "#e74c3c", 0.08)]
    )


def test_script_info_signal_reaches_the_runner_and_the_chart(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter._enabled_script_keys = lambda: ["ema_ribbon"]
    presenter._rebuild_scripts()

    reached = []
    presenter.ui_script_info_signal.connect(lambda key, fields: reached.append(key))
    presenter._script_runner._emit_info("ema_ribbon", [])

    assert reached == ["ema_ribbon"]
    mock_card.set_script_info.assert_called_once_with("ema_ribbon", [])


def test_script_region_signal_is_a_no_op_with_no_active_chart(presenter):
    """No chart yet (e.g. signal arrives before Load History) must not raise."""
    presenter._on_script_region_data("ema_ribbon", [])
    presenter._on_script_info_data("ema_ribbon", [])
    presenter._on_script_marker_data("ema_ribbon", [])


def test_script_marker_signal_reaches_the_runner_and_the_chart(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    presenter._enabled_script_keys = lambda: ["ema_cross"]
    presenter._rebuild_scripts()

    reached = []
    presenter.ui_script_marker_signal.connect(lambda key, points: reached.append(key))
    presenter._script_runner._emit_markers(
        "ema_cross", [(1.0, 100.0, "Buy", "#0ECB81", "up")]
    )

    assert reached == ["ema_cross"]
    mock_card.set_script_markers.assert_called_once_with(
        "ema_cross", [(1.0, 100.0, "Buy", "#0ECB81", "up")]
    )


def test_presenter_shutdown_cancels_cancellation_token_and_shuts_down_autostart(
    presenter,
):
    token = MagicMock()
    presenter._cancellation_token = token
    autostart = MagicMock()
    presenter._autostart_controller = autostart

    presenter.shutdown()

    token.cancel.assert_called_once()
    autostart.shutdown.assert_called_once()
    assert presenter._shutdown_requested is True


# ---------------------------------------------------------------------------
# `EPIC-021K` §2.3/§4 — OrderFeed -> live-fill chart markers. Dev Board is
# multi-symbol, so (unlike Trading's single `_active_symbol`) any open chart
# card should get its own fill drawn, and a fill for a symbol with no open
# card has nowhere to go.
# ---------------------------------------------------------------------------


def _fill_event(symbol="ETHUSDT", order_time=None, status=None):
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
        OrderFilledEvent,
    )
    from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
        ClientOrderId,
    )
    from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
    from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
    from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
    from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide

    order = Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.05"),
        status=status or OrderStatus.NEW,
        order_time=order_time,
    )
    return OrderFilledEvent(
        order=order, fill_price=Decimal("64000.00"), fill_quantity=Decimal("0.05")
    )


def test_order_filled_draws_a_marker_on_that_symbols_open_chart(presenter):
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_fill_marker import (
        order_filled_marker,
    )

    mock_card = MagicMock()
    presenter.active_charts = {"ETHUSDT": mock_card}
    event = _fill_event("ETHUSDT", order_time=datetime(2026, 9, 2, 12, 0, tzinfo=UTC))

    presenter._on_order_filled(event)

    mock_card.set_script_markers.assert_called_once_with(
        "live_fills", [order_filled_marker(event)]
    )


def test_order_filled_for_a_symbol_with_no_open_chart_is_a_no_op(presenter):
    presenter.active_charts = {}

    presenter._on_order_filled(_fill_event("ETHUSDT"))  # must not raise

    assert presenter._fill_markers_by_symbol == {}


# ---------------------------------------------------------------------------
# `EPIC-023A` — OrderFeed -> Vị thế/Lệnh chờ khớp tables (account-wide, same
# behaviour `TradingPresenter`'s own OrderFeed handlers already have — see
# `test_trading_presenter_toggle.py`'s mirror-image tests).
# ---------------------------------------------------------------------------


def _position(symbol="BTCUSDT"):
    from datetime import UTC, datetime
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
        LivePosition,
    )
    from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
        MarginType,
    )

    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("0.5"),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64500.00"),
        unrealized_pnl=Decimal("10.0"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime.now(UTC),
    )


def test_order_filled_with_a_live_status_adds_to_open_orders(
    presenter, view, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
        build_open_order_row,
    )

    spy = MagicMock()
    monkeypatch.setattr(view, "set_open_orders", spy)
    event = _fill_event("BTCUSDT")

    presenter._on_order_filled(event)

    spy.assert_called_once_with([build_open_order_row(event.order)])


def test_order_filled_with_a_terminal_status_removes_it(presenter, view, monkeypatch):
    from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus

    spy = MagicMock()
    monkeypatch.setattr(view, "set_open_orders", spy)
    presenter._on_order_filled(_fill_event("BTCUSDT", status=OrderStatus.NEW))
    spy.reset_mock()

    presenter._on_order_filled(_fill_event("BTCUSDT", status=OrderStatus.FILLED))

    spy.assert_called_once_with([])


def test_position_changed_updates_the_positions_table(presenter, view, monkeypatch):
    from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
        PositionChangedEvent,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
        build_position_row,
    )

    spy = MagicMock()
    monkeypatch.setattr(view, "set_positions", spy)
    position = _position()

    presenter._on_position_changed(PositionChangedEvent(position=position))

    spy.assert_called_once_with([build_position_row(position)])


def test_position_closed_removes_it_from_the_positions_table(
    presenter, view, monkeypatch
):
    """`BUG-086` regression, Dev Board's own copy."""
    from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
        PositionChangedEvent,
    )
    from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
        PositionClosedEvent,
    )

    spy = MagicMock()
    monkeypatch.setattr(view, "set_positions", spy)
    position = _position()
    presenter._on_position_changed(PositionChangedEvent(position=position))
    spy.reset_mock()

    presenter._on_position_closed(PositionClosedEvent(symbol=position.symbol))

    spy.assert_called_once_with([])


def test_position_closed_for_an_unknown_symbol_is_a_no_op(presenter, view, monkeypatch):
    from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
        PositionClosedEvent,
    )

    spy = MagicMock()
    monkeypatch.setattr(view, "set_positions", spy)

    presenter._on_position_closed(PositionClosedEvent(symbol="ETHUSDT"))

    spy.assert_called_once_with([])


def test_order_blocked_appears_in_the_screens_own_log_panel(presenter):
    """`BUG-084` — Dev Board's own copy of the same visibility fix."""
    from Sagittarius_Elite_Warrior.src.domain.events.live_order_blocked_event import (
        LiveOrderBlockedEvent,
    )

    presenter._on_order_blocked(
        LiveOrderBlockedEvent(symbol="BTCUSDT", reason="max_notional_per_order")
    )

    log_model = presenter._view_model.log_model
    assert log_model.rowCount() == 1
    entry = log_model._entries[0]
    assert entry.level == "info"
    assert "BTCUSDT" in entry.message
    assert "max_notional_per_order" in entry.message


# ---------------------------------------------------------------------------
# `EPIC-023B` — live equity chart: seeded from `EquityCurveRecorder`'s
# backlog on construction, appended to live via `EquityFeed`. Mirrors
# `test_trading_presenter_equity.py` (`view` there is a `MagicMock`; here
# `view` is a real `DashboardView`, so assertions spy on `view.equity_chart`'s
# real methods via `monkeypatch` — same style the OrderFeed tests above use).
# ---------------------------------------------------------------------------


def _equity_sample(minute: int = 0):
    from datetime import datetime
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import (
        EquitySample,
    )

    return EquitySample(
        captured_at=datetime(2026, 9, 2, 12, minute, tzinfo=UTC),
        wallet_balance=Decimal("1000.00"),
        unrealized_pnl=Decimal("25.50"),
    )


def test_construction_with_an_empty_recorder_seeds_an_empty_chart(
    view, mock_container, monkeypatch
):
    spy = MagicMock()
    monkeypatch.setattr(view.equity_chart, "render_historical_data", spy)

    DashboardPresenter(view, mock_container)

    spy.assert_called_once_with([])


def test_construction_seeds_the_full_backlog_from_the_recorder(
    view, mock_container, equity_recorder, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_chart_adapter import (
        equity_samples_to_candles,
    )

    equity_recorder.record(_equity_sample(0))
    equity_recorder.record(_equity_sample(1))
    spy = MagicMock()
    monkeypatch.setattr(view.equity_chart, "render_historical_data", spy)

    DashboardPresenter(view, mock_container)

    spy.assert_called_once_with(
        equity_samples_to_candles([_equity_sample(0), _equity_sample(1)])
    )


def test_equity_sampled_event_appends_one_point_to_the_chart(
    presenter, view, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
        EquitySampledEvent,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_chart_adapter import (
        equity_sample_to_candle,
    )

    spy = MagicMock()
    monkeypatch.setattr(view.equity_chart, "append_closed_candle", spy)

    sample = _equity_sample(5)
    presenter._on_equity_sampled(EquitySampledEvent(sample=sample))

    spy.assert_called_once_with(*equity_sample_to_candle(sample))


# ---------------------------------------------------------------------------
# `EPIC-023C` — strategy card: arm/disarm delegate to `StrategyArmingCoordinator`,
# `SignalFeed` -> the "Tín hiệu gần nhất" card, filtered to the armed symbol.
# Mirrors what `test_strategy_arming_coordinator.py` already covers at the
# coordinator level — Trading itself has no dedicated presenter-level test
# for these thin delegators either, so this stays to the genuinely
# presenter-owned logic (the signal filter, the armed-summary refresh).
# ---------------------------------------------------------------------------


def test_construction_restores_the_strategy_card_from_the_real_registry(presenter):
    """Proves `_arming_coordinator.restore_into_view_model()` actually ran
    — an empty `strategyOptions` would mean the real "Chiến lược" combo
    stays empty forever, the exact gap the fake `_build_strategy_combo()`
    left before this epic."""
    keys = [option["key"] for option in presenter._view_model.strategyOptions]
    assert "ema_crossover" in keys
    assert presenter._view_model.armedSummary == ""


def test_arm_requested_delegates_to_the_coordinator(presenter, monkeypatch):
    spy = MagicMock()
    monkeypatch.setattr(presenter._arming_coordinator, "on_arm_clicked", spy)

    presenter._on_arm_requested()

    spy.assert_called_once_with()


def test_disarm_requested_delegates_to_the_coordinator(presenter, monkeypatch):
    spy = MagicMock()
    monkeypatch.setattr(presenter._arming_coordinator, "on_disarm_clicked", spy)

    presenter._on_disarm_requested()

    spy.assert_called_once_with()


def _signal_event(symbol="BTCUSDT"):
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
        SignalGeneratedEvent,
    )
    from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
    from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
        SignalAction,
    )

    signal = Signal(
        symbol=symbol,
        action=SignalAction.BUY,
        reason="RSI Oversold",
        price=64000.0,
        time=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )
    return SignalGeneratedEvent(signal=signal)


def test_signal_generated_for_the_armed_symbol_updates_the_card(
    presenter, strategy_session
):
    from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
        LiveStrategyConfig,
    )

    strategy_session.arm(
        LiveStrategyConfig(
            strategy_key="ema_crossover", symbol="BTCUSDT", interval="1m"
        )
    )

    presenter._on_signal_generated(_signal_event("BTCUSDT"))

    assert "BTCUSDT" not in presenter._view_model.lastSignalText  # symbol not restated
    assert "BUY" in presenter._view_model.lastSignalText
    assert "RSI Oversold" in presenter._view_model.lastSignalText


def test_signal_generated_for_a_different_symbol_is_ignored(
    presenter, strategy_session
):
    """A signal from a *backtest* `StrategyEngine` on the same shared bus
    must never appear on this card as if it were live."""
    from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
        LiveStrategyConfig,
    )

    strategy_session.arm(
        LiveStrategyConfig(
            strategy_key="ema_crossover", symbol="BTCUSDT", interval="1m"
        )
    )

    presenter._on_signal_generated(_signal_event("ETHUSDT"))

    assert presenter._view_model.lastSignalText == ""


def test_signal_generated_with_nothing_armed_is_ignored(presenter):
    presenter._on_signal_generated(_signal_event("BTCUSDT"))

    assert presenter._view_model.lastSignalText == ""


def test_armed_config_changed_updates_the_summary(presenter, strategy_session):
    from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
        LiveStrategyConfig,
    )

    config = LiveStrategyConfig(
        strategy_key="ema_crossover", symbol="BTCUSDT", interval="1m"
    )
    strategy_session.arm(config)

    presenter._refresh_armed_summary(busy=False)

    assert presenter._view_model.armedSummary != ""
    assert presenter._view_model.strategyBusy is False


# ---------------------------------------------------------------------------
# `EPIC-023D` — Enable/Disable trading toggle + Emergency Stop, same
# behaviour `TradingPresenter`'s own toggle/Emergency Stop have — see
# `test_trading_presenter_toggle.py`/`test_trading_presenter_emergency_stop.py`
# for the mirror-image tests.
# ---------------------------------------------------------------------------


def test_construction_reflects_the_session_state(presenter):
    assert presenter._view_model.enabled is False


def test_construction_when_already_enabled_reflects_that_too(
    view, mock_container, session_state, mock_thread_mgr
):
    """If Trading enabled it first, opening Dev Board must show "đang
    BẬT", never a default "TẮT" that contradicts the account's real
    state — the account-wide sharing `EPIC-023`'s README §2 documents."""
    session_state.enable({"BTCUSDT"})

    presenter = DashboardPresenter(view, mock_container)

    assert presenter._view_model.enabled is True


def test_toggle_when_disabled_submits_enable(presenter, mock_thread_mgr):
    presenter._view_model.toggleRequested.emit()

    mock_thread_mgr.submit.assert_called_once()
    submitted_callable = mock_thread_mgr.submit.call_args[0][0]
    assert submitted_callable == presenter._run_enable
    assert presenter._view_model.toggleBusy is True


def test_toggle_when_enabled_submits_disable(
    view, mock_container, session_state, mock_thread_mgr
):
    session_state.enable(set())
    presenter = DashboardPresenter(view, mock_container)
    mock_thread_mgr.submit.reset_mock()

    presenter._view_model.toggleRequested.emit()

    mock_thread_mgr.submit.assert_called_once()
    submitted_callable = mock_thread_mgr.submit.call_args[0][0]
    assert submitted_callable == presenter._run_disable


def test_toggle_is_blocked_while_emergency_stop_is_pending(presenter, mock_thread_mgr):
    """`BUG-089`'s precedent, Dev Board's own copy — a toggle click must
    never race an Emergency Stop already in flight."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
        ActionOutcome,
    )

    presenter._emergency_stop_tracker.begin_action("emergency_stop", None, None)

    presenter._view_model.toggleRequested.emit()

    mock_thread_mgr.submit.assert_not_called()
    assert presenter._emergency_stop_tracker.active_outcome is ActionOutcome.PENDING


def test_successful_enable_turns_the_toggle_on_and_seeds_open_orders(
    presenter, mock_dispatcher, view, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
        EnableTradingCommand,
        EnableTradingResult,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
        build_open_order_row,
    )

    order = _fill_event("BTCUSDT").order
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(order,),
    )
    open_orders_spy = MagicMock()
    positions_spy = MagicMock()
    monkeypatch.setattr(view, "set_open_orders", open_orders_spy)
    monkeypatch.setattr(view, "set_positions", positions_spy)
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    mock_dispatcher.dispatch.assert_called_once_with(
        EnableTradingCommand, EnableTradingCommand()
    )
    assert presenter._view_model.enabled is True
    assert presenter._view_model.toggleBusy is False
    open_orders_spy.assert_called_once_with([build_open_order_row(order)])
    positions_spy.assert_called_once_with([])


def test_refused_enable_shows_the_block_reason_and_seeds_positions(
    presenter, mock_dispatcher, view, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
        EnableTradingBlockReason,
        EnableTradingResult,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
        build_position_row,
    )

    position = _position()
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=False,
        block_reason=EnableTradingBlockReason.UNEXPECTED_POSITIONS,
        reconciled_positions=(position,),
        reconciled_open_orders=(),
    )
    positions_spy = MagicMock()
    monkeypatch.setattr(view, "set_positions", positions_spy)
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    assert presenter._view_model.enabled is False
    log_entries = presenter._view_model.log_model.entries
    assert any("unexpected open positions" in entry.message for entry in log_entries)
    positions_spy.assert_called_once_with([build_position_row(position)])


def test_an_enable_exception_from_the_dispatcher_is_reported_not_raised(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)  # must not raise

    log_entries = presenter._view_model.log_model.entries
    assert any("boom" in entry.message for entry in log_entries)


def test_successful_disable_turns_the_toggle_off(
    view, mock_container, session_state, mock_dispatcher
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disable_trading import (
        DisableTradingCommand,
    )

    session_state.enable(set())
    presenter = DashboardPresenter(view, mock_container)
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_disable(action_id)

    mock_dispatcher.dispatch.assert_called_once_with(
        DisableTradingCommand, DisableTradingCommand()
    )
    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False


def _emergency_stop_result(
    *, fully_succeeded: bool, final_state_confirmed: bool = True
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop import (
        EmergencyStopResult,
        EmergencyStopStepResult,
    )

    ok = EmergencyStopStepResult(succeeded=True, detail="OK")
    return EmergencyStopResult(
        trading_disabled=ok,
        orders_cancelled=ok,
        positions_closed=(
            ok if fully_succeeded else EmergencyStopStepResult(False, "APIError")
        ),
        final_positions=(),
        final_open_orders=(),
        final_state_confirmed=final_state_confirmed,
    )


def test_emergency_stop_success_reconciles_the_tables_and_logs(
    presenter, mock_dispatcher, view, monkeypatch
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop import (
        EmergencyStopCommand,
    )

    mock_dispatcher.dispatch.return_value = _emergency_stop_result(fully_succeeded=True)
    open_orders_spy = MagicMock()
    positions_spy = MagicMock()
    monkeypatch.setattr(view, "set_open_orders", open_orders_spy)
    monkeypatch.setattr(view, "set_positions", positions_spy)

    presenter._on_emergency_stop_requested()
    action_id = presenter._emergency_stop_tracker.active_action.action_id
    presenter._run_emergency_stop(action_id)

    mock_dispatcher.dispatch.assert_called_once_with(
        EmergencyStopCommand, EmergencyStopCommand()
    )
    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False
    positions_spy.assert_called_once_with([])
    open_orders_spy.assert_called_once_with([])
    log_entries = presenter._view_model.log_model.entries
    assert any("EMERGENCY STOP" in entry.message for entry in log_entries)


def test_emergency_stop_partial_failure_is_reported(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = _emergency_stop_result(
        fully_succeeded=False
    )

    presenter._on_emergency_stop_requested()
    action_id = presenter._emergency_stop_tracker.active_action.action_id
    presenter._run_emergency_stop(action_id)

    log_entries = presenter._view_model.log_model.entries
    assert any("PARTIALLY FAILED" in entry.message for entry in log_entries)


def test_emergency_stop_with_unconfirmed_final_state_does_not_touch_the_tables(
    presenter, mock_dispatcher, view, monkeypatch
):
    """`BUG-093`'s precedent, Dev Board's own copy — a failed reconciliation
    read must never be treated as "confirmed flat"."""
    mock_dispatcher.dispatch.return_value = _emergency_stop_result(
        fully_succeeded=True, final_state_confirmed=False
    )
    open_orders_spy = MagicMock()
    positions_spy = MagicMock()
    monkeypatch.setattr(view, "set_open_orders", open_orders_spy)
    monkeypatch.setattr(view, "set_positions", positions_spy)

    presenter._on_emergency_stop_requested()
    action_id = presenter._emergency_stop_tracker.active_action.action_id
    presenter._run_emergency_stop(action_id)

    open_orders_spy.assert_not_called()
    positions_spy.assert_not_called()
    log_entries = presenter._view_model.log_model.entries
    assert any("[WARNING]" in entry.message for entry in log_entries)


def test_order_filled_refreshes_the_session_stats_card(presenter, session_state):
    session_state.enable(set())
    session_state.orders_sent_this_session = 0

    presenter._on_order_filled(_fill_event("BTCUSDT"))

    assert presenter._view_model.ordersSentThisSession == (
        session_state.orders_sent_this_session
    )
    assert presenter._view_model.openSymbolsCount == len(
        session_state.known_open_symbols
    )


# ---------------------------------------------------------------------------
# `BOT-126` — market tick interval filtering
#
# `_handle_market_tick` used to filter a `MarketTickEvent` by `symbol`
# alone, exactly the fault `BUG-085` fixed for `MarketTickEventHandler`.
# Harmless while `ILiveStreamService` was one process-wide stream (no two
# intervals for the same symbol could ever be live at once); `BOT-126`'s
# per-owner subscriptions made that possible for real (this screen and
# Trading each own their own), so this locks the fix: a tick for a symbol
# this screen has open, at a DIFFERENT interval than `_active_interval`,
# must never reach the chart.
# ---------------------------------------------------------------------------


def _tick_event(symbol: str = "BTCUSDT", interval: str = "1m"):
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
    from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
        MarketTickEvent,
    )

    dt = datetime(2026, 9, 8, tzinfo=UTC)
    return MarketTickEvent(
        market_data=MarketData(
            symbol=symbol,
            interval=interval,
            open_time=dt,
            open_price=100.0,
            high_price=110.0,
            low_price=90.0,
            close_price=105.0,
            volume=1000.0,
            close_time=dt,
            quote_asset_volume=105000.0,
            number_of_trades=50,
            taker_buy_base_asset_volume=500.0,
            taker_buy_quote_asset_volume=52500.0,
            is_closed=True,
        )
    )


def test_a_tick_for_an_open_symbol_at_a_different_interval_is_ignored(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"BTCUSDT": mock_card}
    presenter._active_interval = "1m"

    presenter._handle_market_tick(_tick_event("BTCUSDT", "5m"))

    mock_card.append_closed_candle.assert_not_called()


def test_a_tick_for_an_open_symbol_at_the_active_interval_reaches_the_chart(presenter):
    mock_card = MagicMock()
    presenter.active_charts = {"BTCUSDT": mock_card}
    presenter._active_interval = "1m"

    presenter._handle_market_tick(_tick_event("BTCUSDT", "1m"))

    mock_card.append_closed_candle.assert_called_once()


# ---------------------------------------------------------------------------
# `EPIC-024B` — manual trading card + per-order cancel. Dispatches through
# the exact same ExecuteOrderCommand/ExecuteOrderCommandHandler the strategy
# path uses (`LiveTradingCoordinator`) — no new order-submission path.
# ---------------------------------------------------------------------------


def _live_position(symbol: str, signed_amount: str):
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
        LivePosition,
    )
    from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
        MarginType,
    )

    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(signed_amount),
        entry_price=Decimal(64000),
        mark_price=Decimal(64000),
        unrealized_pnl=Decimal(0),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=_tick_event().market_data.close_time,
    )


def test_manual_order_requested_submits_background_worker_for_a_market_order(
    presenter, mock_thread_mgr
):
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
    from Sagittarius_Elite_Warrior.src.domain.trading.policies.manual_order_intent import (
        ManualOrderDirection,
    )

    presenter._active_symbol = "BTCUSDT"
    presenter._last_price_by_symbol["BTCUSDT"] = Decimal(64000)

    presenter._view_model.requestManualOrder("LONG", 0.01, "MARKET", 0.0)

    mock_thread_mgr.submit.assert_called_once()
    args = mock_thread_mgr.submit.call_args[0]
    assert args[0] == presenter._run_manual_order
    assert args[2] == "BTCUSDT"
    assert args[3] is ManualOrderDirection.LONG
    assert args[4] == Decimal("0.01")
    assert args[5] is OrderType.MARKET
    assert args[6] == Decimal(64000)
    assert presenter._view_model.manualOrderBusy is True


def test_manual_order_requested_rejects_a_market_order_with_no_known_price(
    presenter, mock_thread_mgr
):
    presenter._active_symbol = "BTCUSDT"
    presenter._last_price_by_symbol.clear()

    presenter._view_model.requestManualOrder("LONG", 0.01, "MARKET", 0.0)

    mock_thread_mgr.submit.assert_not_called()
    log_entries = presenter._view_model.log_model.entries
    assert any("market price" in entry.message for entry in log_entries)


def test_manual_order_requested_blocked_while_already_pending(
    presenter, mock_thread_mgr
):
    presenter._active_symbol = "BTCUSDT"
    presenter._last_price_by_symbol["BTCUSDT"] = 64000
    presenter._manual_order_tracker.begin_action("manual_order", None, None)

    presenter._view_model.requestManualOrder("LONG", 0.01, "MARKET", 0.0)

    mock_thread_mgr.submit.assert_not_called()


def test_run_manual_order_dispatches_execute_order_with_the_mapped_intent(
    presenter, mock_dispatcher
):
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_open_positions import (
        GetOpenPositionsQuery,
    )
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order import (
        ExecuteOrderCommand,
    )
    from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
    from Sagittarius_Elite_Warrior.src.domain.trading.policies.manual_order_intent import (
        ManualOrderDirection,
    )
    from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import (
        OrderSide,
    )

    def dispatch_side_effect(command_type, command):
        if command_type is GetOpenPositionsQuery:
            return (_live_position("BTCUSDT", "-0.01"),)  # currently SHORT
        return None

    mock_dispatcher.dispatch.side_effect = dispatch_side_effect

    presenter._run_manual_order(
        1,
        "BTCUSDT",
        ManualOrderDirection.LONG,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    execute_calls = [
        call
        for call in mock_dispatcher.dispatch.call_args_list
        if call.args[0] is ExecuteOrderCommand
    ]
    assert len(execute_calls) == 1
    command = execute_calls[0].args[1]
    assert command.live is True
    assert command.order_request.symbol == "BTCUSDT"
    # Currently SHORT + Long click -> BUY, reduce_only=True (closes the
    # short) — `manual_order_intent_for()`'s own table, row 2.
    assert command.order_request.side is OrderSide.BUY
    assert command.order_request.reduce_only is True


def test_run_manual_order_hard_blocks_when_strategy_owns_the_symbol_with_a_position(
    presenter, mock_dispatcher, strategy_session, strategy_registry
):
    """`PRO-003` §4.1.2 (user decision) — the hard block."""
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_open_positions import (
        GetOpenPositionsQuery,
    )
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order import (
        ExecuteOrderCommand,
    )
    from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
    from Sagittarius_Elite_Warrior.src.domain.trading.policies.manual_order_intent import (
        ManualOrderDirection,
    )
    from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
        LiveStrategyConfig,
    )

    strategy_session.arm(
        LiveStrategyConfig(
            strategy_key="ema_crossover",
            symbol="BTCUSDT",
            interval="5m",
            sizing_percent=20.0,
            leverage=1.0,
        )
    )
    completed = MagicMock()
    presenter.manualOrderCompleted.connect(completed)
    mock_dispatcher.dispatch.side_effect = lambda command_type, command: (
        (_live_position("BTCUSDT", "0.01"),)
        if command_type is GetOpenPositionsQuery
        else None
    )

    presenter._run_manual_order(
        1,
        "BTCUSDT",
        ManualOrderDirection.SHORT,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    assert not any(
        call.args[0] is ExecuteOrderCommand
        for call in mock_dispatcher.dispatch.call_args_list
    )
    completed.assert_called_once_with((1, None, True, None))


def test_run_manual_order_hard_blocks_when_strategy_owns_the_symbol_even_while_flat(
    presenter, mock_dispatcher, strategy_session, strategy_registry
):
    """`PRO-003` §4.1.2, tightened 2026-09-09 (user decision): blocking only
    "armed + has a position" still let a human's *first* order on a flat,
    armed symbol through — exactly the race that lets the strategy's next
    signal (which assumes it started flat) double up on a position it
    never opened. The block must fire on "armed" alone, with no
    GetOpenPositionsQuery round-trip needed to decide that."""
    from decimal import Decimal

    from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
    from Sagittarius_Elite_Warrior.src.domain.trading.policies.manual_order_intent import (
        ManualOrderDirection,
    )
    from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
        LiveStrategyConfig,
    )

    strategy_session.arm(
        LiveStrategyConfig(
            strategy_key="ema_crossover",
            symbol="BTCUSDT",
            interval="5m",
            sizing_percent=20.0,
            leverage=1.0,
        )
    )
    completed = MagicMock()
    presenter.manualOrderCompleted.connect(completed)

    presenter._run_manual_order(
        1,
        "BTCUSDT",
        ManualOrderDirection.LONG,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    mock_dispatcher.dispatch.assert_not_called()
    completed.assert_called_once_with((1, None, True, None))


def test_cancel_order_requested_submits_background_worker(presenter, mock_thread_mgr):
    presenter._on_cancel_order_requested("BTCUSDT", "abc123")

    mock_thread_mgr.submit.assert_called_once_with(
        presenter._run_cancel_order, "BTCUSDT", "abc123"
    )


def test_run_cancel_order_dispatches_cancel_order_command_for_exactly_that_order(
    presenter, mock_dispatcher
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.cancel_order import (
        CancelOrderCommand,
    )

    completed = MagicMock()
    presenter.cancelOrderCompleted.connect(completed)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_cancel_order("BTCUSDT", "abc123")

    mock_dispatcher.dispatch.assert_called_once_with(
        CancelOrderCommand, CancelOrderCommand("BTCUSDT", "abc123")
    )


def test_cancel_order_completed_removes_the_order_from_the_book(
    presenter, mock_dispatcher
):
    from Sagittarius_Elite_Warrior.src.application.use_cases.trading.cancel_order import (
        CancelOrderResult,
    )

    remove_spy = MagicMock()
    presenter._order_book.on_order_cancelled = remove_spy

    presenter._on_cancel_order_completed(
        ("BTCUSDT", "abc123", CancelOrderResult(None, None), None)
    )

    remove_spy.assert_called_once_with("abc123")
