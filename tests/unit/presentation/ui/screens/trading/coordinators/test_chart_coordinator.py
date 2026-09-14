"""`BUG-107` — `ChartCoordinator`'s `go_live` split.

Before this, `_run()` unconditionally dispatched `SyncMarketDataCommand`
and `StartLiveStreamCommand`, so submitting `start()` at all — which
`TradingPresenter` did unconditionally at construction — opened a real
Binance connection the instant the Trading screen was navigated to, no
click, no opt-in. This module pins the two halves `start()` now offers,
run synchronously (no `IThreadManager`, no `CancellationToken` real
threading involved — same style as the module's own docstring calls out
for background workers with no bookkeeping of their own).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.coordinators.chart_coordinator import (
    _STREAM_OWNER,
    ChartCoordinator,
)


class _FakeToken:
    def is_cancelled(self) -> bool:
        return False


def _coordinator(dispatcher):
    return ChartCoordinator(
        thread_manager=MagicMock(),
        dispatcher=dispatcher,
        emit_history_ready=MagicMock(),
        emit_load_finished=MagicMock(),
        emit_stream_started=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
    )


def test_go_live_false_never_touches_the_network() -> None:
    """The default path: local history only, no `SyncMarketDataCommand`,
    no `StartLiveStreamCommand`."""
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = MagicMock(data={})
    coordinator = _coordinator(dispatcher)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    dispatched_commands = {call.args[0] for call in dispatcher.dispatch.call_args_list}
    assert SyncMarketDataCommand not in dispatched_commands
    assert StartLiveStreamCommand not in dispatched_commands


def test_go_live_true_syncs_and_starts_the_stream() -> None:
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = MagicMock(data={})
    coordinator = _coordinator(dispatcher)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), True)

    dispatched_commands = [call.args[0] for call in dispatcher.dispatch.call_args_list]
    assert SyncMarketDataCommand in dispatched_commands
    assert StartLiveStreamCommand in dispatched_commands


def test_stop_dispatches_regardless_of_go_live() -> None:
    """`stop()` itself is unconditional — callers decide whether it is safe
    to call at all (`TradingPresenter._restart_chart`'s own guard)."""
    dispatcher = MagicMock()
    coordinator = _coordinator(dispatcher)

    coordinator.stop()

    dispatcher.dispatch.assert_called_once_with(
        StopLiveStreamCommand, StopLiveStreamCommand(owner=_STREAM_OWNER)
    )


def test_start_defaults_to_local_history_only() -> None:
    """`go_live` defaults to `False` — a caller that forgets the argument
    must get the quiet behaviour, not a live connection by omission."""
    thread_manager = MagicMock()
    coordinator = ChartCoordinator(
        thread_manager=thread_manager,
        dispatcher=MagicMock(),
        emit_history_ready=MagicMock(),
        emit_load_finished=MagicMock(),
        emit_stream_started=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
    )

    coordinator.start("BTCUSDT", "1m", _FakeToken())

    thread_manager.submit.assert_called_once()
    assert thread_manager.submit.call_args.args[-1] is False
