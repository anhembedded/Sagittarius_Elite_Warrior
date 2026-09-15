"""
Regression tests for BUG-067 / BUG-052:
Cooperative cancellation of live stream auto-sync and clean shutdown of stream controller & BinanceClient.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.stream_lifecycle_controller import (
    StreamLifecycleController,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


def test_stream_lifecycle_controller_passes_cancellation_to_the_sync() -> None:
    dispatcher = MagicMock()
    market_data_sync = FakeMarketDataSync()
    token = CancellationToken()

    controller = StreamLifecycleController(
        thread_manager=MagicMock(),
        dispatcher=dispatcher,
        market_data_sync=market_data_sync,
        historical_klines=FakeHistoricalKlines(),
        config=MagicMock(),
        fsm=MagicMock(),
        view_model=MagicMock(),
        script_runner=MagicMock(),
        raw_klines_by_symbol={},
        get_active_interval=lambda: "1m",
        set_active_interval=MagicMock(),
        set_active_symbol=MagicMock(),
        ensure_chart_cards=lambda s: [],
        rebuild_scripts=MagicMock(),
        compute_fetch_limit=lambda: 100,
        get_cancellation_token=lambda: token,
        reset_cancellation_token=lambda: token,
        emit_history_reloaded=MagicMock(),
        emit_history_load_finished=MagicMock(),
        emit_history_prepended=MagicMock(),
        emit_history_prepend_finished=MagicMock(),
        emit_stream_success=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
        emit_sync_progress=MagicMock(),
    )

    # Trigger _run_sync_and_start
    controller._run_sync_and_start(
        symbols=["BTCUSDT"],
        interval=TimeFrame.ONE_MINUTE,
        interval_str="1m",
        limit=100,
        token=token,
    )

    # `EPIC-025` PR 0.5: read off the port this screen now calls, instead of
    # off the command it used to build.
    request = market_data_sync.requests[0]
    assert request.cancellation_requested is not None
    assert request.cancellation_requested == token.is_cancelled
    assert not request.cancellation_requested()
    # BOT-123 — every sync is tagged so `on_sync_progress` can tell this
    # screen's own sync apart from one Backtest/Data Management started
    # (`SyncProgressFeed` fans every report out to every screen that has
    # one, per `BOT-121`/`BOT-122`).
    assert request.correlation_id

    token.cancel()
    assert request.cancellation_requested()


def test_stream_lifecycle_controller_shutdown_finishes_action_slots() -> None:
    token = CancellationToken()
    mock_thread_manager = MagicMock()

    controller = StreamLifecycleController(
        thread_manager=mock_thread_manager,
        dispatcher=MagicMock(),
        market_data_sync=FakeMarketDataSync(),
        historical_klines=FakeHistoricalKlines(),
        config=MagicMock(),
        fsm=MagicMock(current_state=UIMode.IDLE),
        view_model=MagicMock(),
        script_runner=MagicMock(),
        raw_klines_by_symbol={},
        get_active_interval=lambda: "1m",
        set_active_interval=MagicMock(),
        set_active_symbol=MagicMock(),
        ensure_chart_cards=lambda s: [],
        rebuild_scripts=MagicMock(),
        compute_fetch_limit=lambda: 100,
        get_cancellation_token=lambda: token,
        reset_cancellation_token=lambda: token,
        emit_history_reloaded=MagicMock(),
        emit_history_load_finished=MagicMock(),
        emit_history_prepended=MagicMock(),
        emit_history_prepend_finished=MagicMock(),
        emit_stream_success=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
        emit_sync_progress=MagicMock(),
    )

    assert controller._stream_actions.try_start("load_history")
    assert controller._stream_actions.held_slot() is not None
    controller.shutdown()
    assert controller._stream_actions.held_slot() is None


def test_python_binance_client_close_closes_session() -> None:
    mock_client = MagicMock()
    client = PythonBinanceClient(client=mock_client)
    client.close()
    mock_client.session.close.assert_called_once()


def _controller(**overrides) -> StreamLifecycleController:
    token = CancellationToken()
    defaults = {
        "thread_manager": MagicMock(),
        "dispatcher": MagicMock(),
        "market_data_sync": FakeMarketDataSync(),
        "historical_klines": FakeHistoricalKlines(),
        "config": MagicMock(),
        "fsm": MagicMock(),
        "view_model": MagicMock(),
        "script_runner": MagicMock(),
        "raw_klines_by_symbol": {},
        "get_active_interval": lambda: "1m",
        "set_active_interval": MagicMock(),
        "set_active_symbol": MagicMock(),
        "ensure_chart_cards": lambda s: [],
        "rebuild_scripts": MagicMock(),
        "compute_fetch_limit": lambda: 100,
        "get_cancellation_token": lambda: token,
        "reset_cancellation_token": lambda: token,
        "emit_history_reloaded": MagicMock(),
        "emit_history_load_finished": MagicMock(),
        "emit_history_prepended": MagicMock(),
        "emit_history_prepend_finished": MagicMock(),
        "emit_stream_success": MagicMock(),
        "emit_stream_failed": MagicMock(),
        "emit_log": MagicMock(),
        "emit_sync_progress": MagicMock(),
    }
    defaults.update(overrides)
    return StreamLifecycleController(**defaults), token


def test_sync_shows_the_progress_bar_then_hides_it_once_the_run_finishes() -> None:
    """BOT-123: `emit_sync_progress` is the only path
    `DashboardQmlViewModel.progressVisible` has to turn on/off — a run that
    forgets the `finally` hide would leave the bar frozen at its last
    percent forever, since nothing else ever calls `hide_progress()`."""
    emit_sync_progress = MagicMock()
    controller, token = _controller(emit_sync_progress=emit_sync_progress)

    controller._run_sync_and_start(
        symbols=["BTCUSDT"],
        interval=TimeFrame.ONE_MINUTE,
        interval_str="1m",
        limit=100,
        token=token,
    )

    calls = emit_sync_progress.call_args_list
    # First call: bar shown, before the sync dispatch.
    assert calls[0][0][2] is True
    # Last call: bar hidden, unconditionally, whatever the run's outcome.
    assert calls[-1][0] == (0, 0, False, "")


def test_on_sync_progress_ignores_a_report_for_a_different_correlation_id() -> None:
    """BOT-121/BOT-122: `SyncProgressFeed` fans every report out to every
    screen that has one — a sync Backtest or Data Management started must
    not move this screen's bar."""
    emit_sync_progress = MagicMock()
    controller, _token = _controller(emit_sync_progress=emit_sync_progress)
    controller._active_sync_correlation_id = "dev-board-own-id"

    other_screens_report = SimpleNamespace(
        correlation_id="some-other-screens-id",
        current=5,
        total=10,
        to_message=lambda: "irrelevant",
    )
    controller.on_sync_progress(other_screens_report)

    emit_sync_progress.assert_not_called()


def test_on_sync_progress_forwards_a_report_for_its_own_correlation_id() -> None:
    emit_sync_progress = MagicMock()
    controller, _token = _controller(emit_sync_progress=emit_sync_progress)
    controller._active_sync_correlation_id = "dev-board-own-id"

    own_report = SimpleNamespace(
        correlation_id="dev-board-own-id",
        current=5,
        total=10,
        to_message=lambda: "5/10",
    )
    controller.on_sync_progress(own_report)

    emit_sync_progress.assert_called_once_with(5, 10, True, "5/10")


def test_on_sync_progress_ignores_everything_when_no_sync_is_in_flight() -> None:
    emit_sync_progress = MagicMock()
    controller, _token = _controller(emit_sync_progress=emit_sync_progress)
    assert controller._active_sync_correlation_id is None

    report = SimpleNamespace(
        correlation_id="", current=0, total=0, to_message=lambda: ""
    )
    controller.on_sync_progress(report)

    emit_sync_progress.assert_not_called()
