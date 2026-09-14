"""`BUG-107` — opening the Trading screen must not open a network connection.

Before this, construction unconditionally submitted `ChartCoordinator.start()`
with no `go_live` distinction, and `_run()` unconditionally dispatched
`SyncMarketDataCommand` + `StartLiveStreamCommand` — so navigating to the
Trading screen alone (the log the user reported: `App booted` ->
`[chart-env] ChartCard(ETHUSDT)` -> `SyncMarketDataCommand` ->
`StartLiveStreamCommand` -> `[Live Stream] ETHUSDT` — no click in between)
opened a real Binance stream. `mock_thread_manager` never actually runs the
submitted callable (see `presenter` fixture in
`test_trading_presenter_toggle.py`), so this module inspects what got
*submitted*, matching that file's own style.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    _CHART_AUTOSTART_CONFIG_KEY,
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY


def _submitted_go_live_flags(mock_thread_manager) -> list[bool]:
    """`go_live` is the trailing positional arg of every
    `ChartCoordinator._run` submission (`thread_manager.submit(self._run,
    symbol, interval, token, go_live)`) — this pulls just that column out
    of every call the presenter made, in order."""
    return [
        call.args[-1]
        for call in mock_thread_manager.submit.call_args_list
        if call.args and call.args[0].__name__ == "_run"
    ]


def test_opening_the_screen_loads_local_history_only(
    view, container, mock_thread_manager
):
    """The exact defect: construction alone must never request `go_live`."""
    TradingPresenter(view, container)

    flags = _submitted_go_live_flags(mock_thread_manager)
    assert flags == [False], (
        "opening the Trading screen submitted a live-stream request with no "
        "user action — this is the BUG-107 regression"
    )


def test_opening_the_screen_never_touches_the_dispatcher_for_the_chart(
    view, container, mock_dispatcher
):
    """`go_live=False` is submitted to the thread pool, which
    `mock_thread_manager` never actually runs — so the real proof that no
    network call was even queued is that the dispatcher the chart worker
    would have used stays untouched at construction."""
    TradingPresenter(view, container)

    mock_dispatcher.dispatch.assert_not_called()


def test_a_configured_opt_in_goes_live_on_open(
    view, container, mock_config, mock_thread_manager
):
    """The escape hatch this fix keeps: a deployment that explicitly wants
    the old always-live behaviour can still have it, opted in by config —
    same shape as Dev Board's own `DEV_BOARD_AUTOSTART_ENABLED`."""
    mock_config.get.side_effect = lambda key, default=None, cast=None: (
        True if key in (DEV_MODE_CONFIG_KEY, _CHART_AUTOSTART_CONFIG_KEY) else default
    )

    TradingPresenter(view, container)

    assert _submitted_go_live_flags(mock_thread_manager) == [True]


def test_enabling_trading_is_the_action_that_goes_live(
    presenter, mock_dispatcher, mock_thread_manager
):
    """The correct trigger for a network connection: the user explicitly
    turning trading on, not opening the screen."""
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(),
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    assert presenter._chart_live_requested is True
    assert _submitted_go_live_flags(mock_thread_manager) == [True]


def test_a_failed_enable_does_not_go_live(
    presenter, mock_dispatcher, mock_thread_manager
):
    mock_dispatcher.dispatch.return_value = None
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    assert presenter._chart_live_requested is False
    assert _submitted_go_live_flags(mock_thread_manager) == []


def test_going_live_does_not_stop_a_stream_this_screen_never_started(
    presenter, mock_dispatcher, mock_thread_manager
):
    """The second half of the fix, easy to get wrong: promoting to live for
    the first time must not call `ChartCoordinator.stop()` first. This
    screen has only ever read local history, so there is nothing of its own
    to stop — and `stop()` kills the process-wide stream unconditionally
    (`StopLiveStreamCommand` takes no caller identity), which would cut off
    Dev Board if it happened to be the one running it."""
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(),
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
        StopLiveStreamCommand,
    )

    dispatched_commands = [
        call.args[0] for call in mock_dispatcher.dispatch.call_args_list
    ]
    assert StopLiveStreamCommand not in dispatched_commands


def test_a_symbol_change_before_going_live_does_not_stop_the_stream(
    presenter, mock_dispatcher, mock_thread_manager
):
    """A user browsing symbols before ever enabling trading must not touch
    the process-wide stream at all — same reasoning as the test above, for
    the OTHER path into `_restart_chart()`."""
    mock_thread_manager.submit.reset_mock()

    presenter._on_symbol_change_requested("ETHUSDT")

    from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
        StopLiveStreamCommand,
    )

    dispatched_commands = [
        call.args[0] for call in mock_dispatcher.dispatch.call_args_list
    ]
    assert StopLiveStreamCommand not in dispatched_commands
    assert _submitted_go_live_flags(mock_thread_manager) == [False]


def test_a_symbol_change_after_going_live_does_stop_and_restart_live(
    presenter, mock_dispatcher, mock_thread_manager
):
    """Once this screen owns the stream, changing symbol must still behave
    like it always did: stop, then restart live for the new symbol."""
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(),
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id
    presenter._run_enable(action_id)
    mock_dispatcher.dispatch.reset_mock()
    mock_thread_manager.submit.reset_mock()

    presenter._on_symbol_change_requested("ETHUSDT")

    from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
        StopLiveStreamCommand,
    )

    dispatched_commands = [
        call.args[0] for call in mock_dispatcher.dispatch.call_args_list
    ]
    assert dispatched_commands == [StopLiveStreamCommand]
    assert _submitted_go_live_flags(mock_thread_manager) == [True]
