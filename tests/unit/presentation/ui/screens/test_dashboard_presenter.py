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
from Binace_Bot.src.presentation.ui.screens.dashboard.kline_mapping import (
    map_klines,
    map_volume,
)
from Binace_Bot.src.presentation.ui.constants import UIMode  # noqa: E402

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
    # Key-aware, not a blanket stub: a blanket `return_value = False` used to
    # be harmless (only _compute_fetch_limit's floor read it, and
    # max(75, slowest, 0) doesn't care) but BOT-034's fallback_seconds read
    # made it a real bug — False * 1000 == 0, so AutoStartController's
    # fallback timer fired almost immediately instead of never, racing the
    # test body's own action against a background _load_history() call it
    # never expected. Falling through to the caller's own `default` matches
    # what the real ConfigManager.get() does for an unset key.
    mock_config.get.side_effect = lambda key, default=None, cast=None: default
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
def presenter(view, mock_container, mock_thread_mgr):
    """
    @details BOT-034: construction now auto-starts (AutoStartController.begin()
    calls _on_start_stream(), which submits a background task and locks the
    FSM) — this mock thread manager never actually runs that task, so left
    alone the FSM would sit LOCKED forever, an artifact of the mock rather
    than real behavior (in the real app the task completes quickly one way
    or the other). Reset both the submit call history and the FSM back to
    IDLE here so every *other* test's assertions reflect only its own
    action — see test_autostart_controller_integration.py for tests that
    exercise auto-start's own effect on a freshly-constructed presenter.
    """
    p = DashboardPresenter(view, mock_container)
    mock_thread_mgr.submit.reset_mock()
    p.fsm.transition_to(UIMode.ERROR)  # auto-recovers to IDLE via _on_fsm_error
    return p


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
    presenter._run_load_history(symbols, "1m", 5000, presenter._cancellation_token)

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
    presenter._run_load_history(
        ["BTCUSDT", "ETHUSDT"], "1m", 100, presenter._cancellation_token
    )

    assert any("BTCUSDT" in log for log in logs)


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


def test_run_sync_and_start_full_workflow(presenter, mock_dispatcher):
    """_run_sync_and_start dispatches Sync → HistoricalKlines → StartLiveStream in order."""
    mock_dispatcher.dispatch.return_value = []

    from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

    presenter._run_sync_and_start(
        ["BTCUSDT"], TimeFrame("1m"), "1m", 5000, presenter._cancellation_token
    )

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
    presenter, mock_dispatcher
):
    """Sync (Step 1) always runs — cancellation is checked *between* steps,
    not before the first one — but History (Step 2) and Start Stream
    (Step 3) must not run once cancelled."""
    from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

    token = CancellationToken()
    token.cancel()
    mock_dispatcher.dispatch.return_value = []

    presenter._run_sync_and_start(["BTCUSDT"], TimeFrame("1m"), "1m", 5000, token)

    call_types = [args[0][0] for args in mock_dispatcher.dispatch.call_args_list]
    assert call_types == [SyncMarketDataCommand]


def test_stop_stream_cancels_the_current_token_and_issues_a_fresh_one(presenter):
    old_token = presenter._cancellation_token

    presenter._on_stop_stream()

    assert old_token.is_cancelled()
    assert presenter._cancellation_token is not old_token
    assert not presenter._cancellation_token.is_cancelled()


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
    presenter._view_model.set_history_loading(True)

    presenter._on_timeframe_changed("5m")

    assert presenter._active_interval == "5m"
    assert mock_thread_mgr.submit.call_count == 0


def test_timeframe_changed_while_live_stops_then_restarts(presenter, mock_thread_mgr):
    from Binace_Bot.src.presentation.ui.constants import UIMode

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
    """@safe_ui_action catches exceptions from _ensure_chart_cards without crashing."""
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


# ---------------------------------------------------------------------------
# BOT-035 — load more history on scroll
# ---------------------------------------------------------------------------


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


def test_run_load_more_history_dispatches_with_end_time_and_desc_order(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = [_make_full_kline(900.0)]

    presenter._run_load_more_history(
        "ETHUSDT", "1m", 1000.0, 75, presenter._cancellation_token
    )

    dispatched_type, query = mock_dispatcher.dispatch.call_args[0]
    assert dispatched_type == GetHistoricalKlinesQuery
    assert query.symbol == "ETHUSDT"
    assert query.limit == 75
    assert query.order_by_desc is True
    assert query.end_time.timestamp() == 1000.0


def test_run_load_more_history_filters_out_the_boundary_candle(
    presenter, mock_dispatcher
):
    """The repository's end_time filter is inclusive (open_time <= end_time)
    — a returned candle at/after the timestamp we already have on the chart
    must be dropped client-side, or it would render as a duplicate."""
    mock_dispatcher.dispatch.return_value = [
        _make_full_kline(1000.0),  # == the oldest already loaded — must drop
        _make_full_kline(940.0),  # genuinely older — must keep
    ]
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
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = [_make_full_kline(900.0)]
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
# Auto-start (BOT-034) — construction-time wiring. Uses `view`/`mock_container`
# directly (not the `presenter` fixture, which deliberately resets past
# auto-start's own effect for every other test — see its docstring) so these
# can observe the real moment of construction.
# ---------------------------------------------------------------------------


def test_construction_auto_starts_immediately(view, mock_container, mock_thread_mgr):
    p = DashboardPresenter(view, mock_container)

    assert p.fsm.current_state.name == "LOCKED"
    assert mock_thread_mgr.submit.call_count == 1
    assert mock_thread_mgr.submit.call_args[0][0] == p._run_sync_and_start


def test_starting_live_manually_while_autostart_pending_is_rejected(
    view, mock_container, mock_thread_mgr
):
    """The FSM-state guard added alongside auto-start (BOT-034) — without
    it, a manual Start Live click during the auto-start window would raise
    InvalidStateTransitionError (LOCKED -> LOCKED)."""
    p = DashboardPresenter(view, mock_container)
    mock_thread_mgr.submit.reset_mock()

    p._on_start_stream()

    assert mock_thread_mgr.submit.call_count == 0
    assert p.fsm.current_state.name == "LOCKED"


def test_a_market_tick_cancels_the_autostart_fallback_timer(view, mock_container):
    p = DashboardPresenter(view, mock_container)
    assert p._autostart._timer is not None  # fallback armed by construction

    p._on_ui_chart_update("ETHUSDT", 1.0, 100.0, 101.0, 99.0, 100.5, 5.0, False)

    assert p._autostart._timer is None


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
