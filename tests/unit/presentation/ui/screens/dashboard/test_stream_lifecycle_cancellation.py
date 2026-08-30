"""
Regression tests for BUG-067 / BUG-052:
Cooperative cancellation of live stream auto-sync and clean shutdown of stream controller & BinanceClient.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.stream_lifecycle_controller import (
    StreamLifecycleController,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


def test_stream_lifecycle_controller_passes_cancellation_to_sync_command() -> None:
    dispatcher = MagicMock()
    token = CancellationToken()

    controller = StreamLifecycleController(
        thread_manager=MagicMock(),
        dispatcher=dispatcher,
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
    )

    # Trigger _run_sync_and_start
    controller._run_sync_and_start(
        symbols=["BTCUSDT"],
        interval=TimeFrame.ONE_MINUTE,
        interval_str="1m",
        limit=100,
        token=token,
    )

    assert dispatcher.dispatch.called
    sync_call_args = dispatcher.dispatch.call_args_list[0][0]
    assert sync_call_args[0] is SyncMarketDataCommand
    sync_cmd: SyncMarketDataCommand = sync_call_args[1]
    assert sync_cmd.cancellation_requested is not None
    assert sync_cmd.cancellation_requested == token.is_cancelled
    assert not sync_cmd.cancellation_requested()

    token.cancel()
    assert sync_cmd.cancellation_requested()


def test_stream_lifecycle_controller_shutdown_finishes_action_slots() -> None:
    token = CancellationToken()
    mock_thread_manager = MagicMock()

    controller = StreamLifecycleController(
        thread_manager=mock_thread_manager,
        dispatcher=MagicMock(),
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
