"""`BUG-107` — `ChartCoordinator`'s `go_live` split.

Before this, `_run()` unconditionally dispatched `SyncMarketDataCommand`
and `StartLiveStreamCommand`, so submitting `start()` at all — which
`TradingPresenter` did unconditionally at construction — opened a real
Binance connection the instant the Trading screen was navigated to, no
click, no opt-in. This module pins the two halves `start()` now offers,
run synchronously (no `IThreadManager`, no `CancellationToken` real
threading involved — same style as the module's own docstring calls out
for background workers with no bookkeeping of their own).

**`EPIC-025` PR 0.5 changed what these tests can assert.** The sync now goes
through `IMarketDataSync`, a port market_data publishes, driven here by its
verified fake. That is not only the boundary rule (`Mock(spec=IMarketDataSync)`
on a *foreign* port fails `test_no_foreign_port_is_mocked.py`) — it is a
stronger assertion: "no sync was started" and "a sync was asked for BTCUSDT at
1m" are facts about the screen's behaviour, where "`SyncMarketDataCommand` was
in `dispatch.call_args_list`" was a fact about its plumbing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.coordinators.chart_coordinator import (
    _STREAM_OWNER,
    ChartCoordinator,
)


class _FakeToken:
    def is_cancelled(self) -> bool:
        return False


def _coordinator(
    sync: FakeMarketDataSync | None = None,
    history: FakeHistoricalKlines | None = None,
    stream: FakeMarketStream | None = None,
):
    """No dispatcher: `EPIC-025` PR 1.1b took the last one this coordinator
    held, so there is no bus left for a test to record."""
    return ChartCoordinator(
        thread_manager=MagicMock(),
        market_data_sync=sync or FakeMarketDataSync(),
        historical_klines=history or FakeHistoricalKlines(),
        market_stream=stream or FakeMarketStream(),
        emit_history_ready=MagicMock(),
        emit_load_finished=MagicMock(),
        emit_stream_started=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
    )


def test_go_live_false_never_touches_the_network() -> None:
    """The default path: local history only — no sync, no live stream."""
    sync = FakeMarketDataSync()
    stream = FakeMarketStream()
    coordinator = _coordinator(sync, stream=stream)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    assert sync.requests == [], "no sync may be started for a local-only load"
    # `EPIC-025` PR 1.1b — the guarantee moved rather than disappeared:
    # `StartLiveStreamCommand not in dispatched` used to prove it, and after
    # the move it would pass even if the screen opened every socket on the
    # exchange. The port's own bookkeeping is where the promise lives.
    assert stream.calls == [], "a local-only load may not open a stream"
    assert stream.is_streaming("BTCUSDT") is False


def test_go_live_true_syncs_and_starts_the_stream() -> None:
    sync = FakeMarketDataSync()
    stream = FakeMarketStream()
    coordinator = _coordinator(sync, stream=stream)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), True)

    assert sync.was_asked_for("BTCUSDT", TimeFrame.ONE_MINUTE)
    # The symbol and the timeframe, not just "a stream was started": a screen
    # that opened the right stream for the wrong pair looks identical to a
    # call-count assertion.
    assert stream.is_streaming("BTCUSDT", TimeFrame.ONE_MINUTE) is True


def test_the_sync_carries_the_screens_cancellation_check() -> None:
    """`async-ui-action-rule.md`: the caller owns the action. A sync started
    without the token's check cannot be stopped by the Cancel button, and
    nothing else in this screen would notice."""
    sync = FakeMarketDataSync()
    token = _FakeToken()
    coordinator = _coordinator(sync)

    coordinator._run("BTCUSDT", "1m", token, True)

    assert sync.requests[0].cancellation_requested == token.is_cancelled


def test_the_chart_draws_the_stored_candles_oldest_first() -> None:
    """`EPIC-025` PR 1.1 made this assertable at all. The old test could only
    say "a query was dispatched": the history arrived as
    `MagicMock(data={})` through `getattr(response, "data", response)`, so
    there was nothing real to check the order of. Order is the whole point —
    the port is asked for the *newest* N candles (that is how a limit keeps
    recent data) and the chart must draw them chronologically, so a missing
    `reversed()` would paint the series backwards in time."""
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = MagicMock(data={})
    history = FakeHistoricalKlines()
    history.seed(
        [candle("BTCUSDT", minute, close_price=float(minute)) for minute in range(3)]
    )
    emit_history_ready = MagicMock()
    coordinator = ChartCoordinator(
        thread_manager=MagicMock(),
        market_data_sync=FakeMarketDataSync(),
        historical_klines=history,
        market_stream=FakeMarketStream(),
        emit_history_ready=emit_history_ready,
        emit_load_finished=MagicMock(),
        emit_stream_started=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
    )

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    symbol, _mapped, _volume, raw = emit_history_ready.call_args.args
    assert symbol == "BTCUSDT"
    assert [row.close_price for row in raw] == [0.0, 1.0, 2.0]


def test_the_chart_asks_for_the_newest_candles_not_the_first() -> None:
    """A limit without `newest_first` would hand a live chart the OLDEST
    candles in the shard — same type, same row count, silently wrong data.
    Read off the port's own record of what was asked for."""
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = MagicMock(data={})
    history = FakeHistoricalKlines()
    coordinator = _coordinator(dispatcher, history=history)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    read = history.reads[0]
    assert read.symbols == ("BTCUSDT",)
    assert read.interval == TimeFrame.ONE_MINUTE
    assert read.newest_first is True


def test_stop_releases_only_this_screens_subscription() -> None:
    """`stop()` itself is unconditional — callers decide whether it is safe
    to call at all (`TradingPresenter._restart_chart`'s own guard).

    Asserted on what the stream holds afterwards, not on a dispatched
    command: `BOT-126`'s whole point is that this screen releasing its own
    subscription leaves the Dev Board's alone, and only the port's
    bookkeeping can show that.
    """
    stream = FakeMarketStream()
    stream.start("dashboard", ["BTCUSDT"], TimeFrame.ONE_MINUTE)
    coordinator = _coordinator(stream=stream)
    coordinator._run("BTCUSDT", "1m", _FakeToken(), True)

    coordinator.stop()

    assert stream.held_by(_STREAM_OWNER) is None
    assert stream.held_by("dashboard") is not None


def test_start_defaults_to_local_history_only() -> None:
    """`go_live` defaults to `False` — a caller that forgets the argument
    must get the quiet behaviour, not a live connection by omission."""
    thread_manager = MagicMock()
    coordinator = ChartCoordinator(
        thread_manager=thread_manager,
        market_data_sync=FakeMarketDataSync(),
        historical_klines=FakeHistoricalKlines(),
        market_stream=FakeMarketStream(),
        emit_history_ready=MagicMock(),
        emit_load_finished=MagicMock(),
        emit_stream_started=MagicMock(),
        emit_stream_failed=MagicMock(),
        emit_log=MagicMock(),
    )

    coordinator.start("BTCUSDT", "1m", _FakeToken())

    thread_manager.submit.assert_called_once()
    assert thread_manager.submit.call_args.args[-1] is False
