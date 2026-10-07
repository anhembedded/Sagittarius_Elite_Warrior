"""`BUG-107` — the live chart coordinator's `go_live` split.

`EPIC-029G` moved the coordinator to `support/charting/live_chart/`
(`LiveChartCoordinator`) behind `ICandleFeed`. These tests moved with it and
drive it through market_data's own `MarketDataCandleFeed`, over the same
verified fakes, so every assertion below is the one it was before the move.

Before this, `_run()` unconditionally dispatched `SyncMarketDataCommand`
and `StartLiveStreamCommand`, so submitting `start()` at all — which
the single Trading screen's presenter did unconditionally at construction —
opened a real Binance connection the instant the screen was navigated to, no
click, no opt-in. The desks inherited the coordinator (`EPIC-028M`). This module pins the two halves `start()` now offers,
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

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
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
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_callbacks import (
    LiveChartCallbacks,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_coordinator import (
    LiveChartCoordinator,
)

_OWNER = "desk.spot_testnet"


class _FakeToken:
    def is_cancelled(self) -> bool:
        return False


def _callbacks(history_ready: MagicMock | None = None) -> LiveChartCallbacks:
    return LiveChartCallbacks(
        history_ready=history_ready or MagicMock(),
        load_finished=MagicMock(),
        stream_started=MagicMock(),
        stream_failed=MagicMock(),
        log=MagicMock(),
    )


def _coordinator(
    sync: FakeMarketDataSync | None = None,
    history: FakeHistoricalKlines | None = None,
    stream: FakeMarketStream | None = None,
    market: MarketType = MarketType.SPOT,
    owner: str = _OWNER,
    *,
    thread_manager: MagicMock | None = None,
    history_ready: MagicMock | None = None,
) -> LiveChartCoordinator:
    """No dispatcher: `EPIC-025` PR 1.1b took the last one this coordinator
    held, so there is no bus left for a test to record."""
    feed = MarketDataCandleFeed(
        sync or FakeMarketDataSync(),
        history or FakeHistoricalKlines(),
        stream or FakeMarketStream(),
        market,
    )
    return LiveChartCoordinator(
        thread_manager or MagicMock(), feed, _callbacks(history_ready), owner
    )


def test_go_live_false_with_candles_stored_never_touches_the_network() -> None:
    """The default path: stored history only — no sync, no live stream."""
    sync = FakeMarketDataSync()
    stream = FakeMarketStream()
    history = FakeHistoricalKlines()
    history.seed([candle("BTCUSDT", 0)])
    coordinator = _coordinator(sync, history, stream=stream)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    assert sync.requests == [], "no sync may be started when something is stored"
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


def test_a_futures_chart_syncs_reads_and_streams_futures() -> None:
    """`EPIC-028C` — the chart's market is the screen's venue's. A Futures
    screen drawing Spot candles would show, and arm its strategy on, prices
    Futures never had."""
    sync = FakeMarketDataSync()
    history = FakeHistoricalKlines()
    stream = FakeMarketStream()
    coordinator = _coordinator(
        sync, history=history, stream=stream, market=MarketType.FUTURES_USD_M
    )

    coordinator._run("BTCUSDT", "1m", _FakeToken(), True)

    assert sync.requests[0].market is MarketType.FUTURES_USD_M
    assert history.reads[0].market is MarketType.FUTURES_USD_M
    held = stream.held_by(_OWNER)
    assert held is not None
    assert held.market_type is MarketType.FUTURES_USD_M


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
    coordinator = _coordinator(history=history, history_ready=emit_history_ready)

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
    to call at all (`DeskChart._restart`'s own guard).

    Asserted on what the stream holds afterwards, not on a dispatched
    command: `BOT-126`'s whole point is that this screen releasing its own
    subscription leaves the Dev Board's alone, and only the port's
    bookkeeping can show that.
    """
    stream = FakeMarketStream()
    stream.start("dashboard", MarketType.SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)
    coordinator = _coordinator(stream=stream)
    coordinator._run("BTCUSDT", "1m", _FakeToken(), True)

    coordinator.stop()

    assert stream.held_by(_OWNER) is None
    assert stream.held_by("dashboard") is not None


def test_start_defaults_to_local_history_only() -> None:
    """`go_live` defaults to `False` — a caller that forgets the argument
    must get the quiet behaviour, not a live connection by omission."""
    thread_manager = MagicMock()
    coordinator = _coordinator(thread_manager=thread_manager)

    coordinator.start("BTCUSDT", "1m", _FakeToken())

    thread_manager.submit.assert_called_once()
    assert thread_manager.submit.call_args.args[-1] is False


def test_two_desks_stream_under_their_own_owners() -> None:
    """`EPIC-028K` — one shared owner made a second desk's chart replace the
    first's subscription (the PR #300 epic review). Each desk streams under
    its own, and stopping one leaves the other streaming."""
    stream = FakeMarketStream()
    futures = _coordinator(
        stream=stream, market=MarketType.FUTURES_USD_M, owner="desk.futures"
    )
    spot = _coordinator(stream=stream, market=MarketType.SPOT, owner="desk.spot")

    futures._run("BTCUSDT", "1m", _FakeToken(), True)
    spot._run("ETHUSDT", "1m", _FakeToken(), True)
    futures.stop()

    assert stream.held_by("desk.futures") is None
    held = stream.held_by("desk.spot")
    assert held is not None
    assert held.market_type is MarketType.SPOT


class _CancelledToken:
    def is_cancelled(self) -> bool:
        return True


def test_a_cancelled_load_reports_nothing() -> None:
    """`BUG-150`: the chart a callback emits on may be deleted once its load
    is cancelled (a closed Market tab), so nothing at all is reported."""
    callbacks = _callbacks()
    feed = MarketDataCandleFeed(
        FakeMarketDataSync(),
        FakeHistoricalKlines(),
        FakeMarketStream(),
        MarketType.SPOT,
    )
    coordinator = LiveChartCoordinator(MagicMock(), feed, callbacks, _OWNER)

    coordinator._run("BTCUSDT", "1m", _CancelledToken(), True)

    for name in ("history_ready", "load_finished", "stream_started", "log"):
        getattr(callbacks, name).assert_not_called()
    callbacks.stream_failed.assert_not_called()


def test_a_settled_load_names_its_own_token() -> None:
    callbacks = _callbacks()
    feed = MarketDataCandleFeed(
        FakeMarketDataSync(),
        FakeHistoricalKlines(),
        FakeMarketStream(),
        MarketType.SPOT,
    )
    token = _FakeToken()
    coordinator = LiveChartCoordinator(MagicMock(), feed, callbacks, _OWNER)

    coordinator._run("BTCUSDT", "1m", token, False)

    callbacks.load_finished.assert_called_once_with(token)


class _RefusingSync(FakeMarketDataSync):
    """The exchange refusing the interval (`BUG-159`: Futures has no 1s)."""

    def sync(self, request) -> None:
        raise RuntimeError("APIError(code=-1120): Invalid interval.")


def test_a_refused_sync_is_named_and_the_stored_candles_still_draw() -> None:
    """`BUG-159`: the sync of an interval the exchange refuses raised out of
    `_run` before any history was drawn, so the chart kept the previous
    interval's candles under the new one's label."""
    history = FakeHistoricalKlines()
    callbacks = _callbacks()
    feed = MarketDataCandleFeed(
        _RefusingSync(), history, FakeMarketStream(), MarketType.FUTURES_USD_M
    )
    coordinator = LiveChartCoordinator(MagicMock(), feed, callbacks, _OWNER)

    coordinator._run("BTCUSDT", "1s", _FakeToken(), True)

    token, headline, detail = callbacks.stream_failed.call_args.args
    assert isinstance(token, _FakeToken)
    assert "BTCUSDT" in headline and "1s" in headline
    assert "Invalid interval" not in headline, "`BOT-169`: the exception is the detail"
    assert "Invalid interval" in detail
    assert history.reads[0].interval == TimeFrame.ONE_SECOND
    callbacks.history_ready.assert_called_once_with("BTCUSDT", [], [], [])


class _ScriptedFeed(ICandleFeed):
    """An `ICandleFeed` that answers as told: a failing read, a refused stream."""

    def __init__(
        self, *, read_error: Exception | None = None, stream_message: str = ""
    ) -> None:
        self._read_error = read_error
        self._stream_message = stream_message

    def sync(self, symbol, interval, cancelled) -> None:
        return None

    def load_history(self, symbol, interval, limit):
        if self._read_error is not None:
            raise self._read_error
        return ()

    def start_stream(self, owner_id, symbol, interval) -> CandleStreamStart:
        return CandleStreamStart(False, self._stream_message)

    def stop_stream(self, owner_id) -> None:
        return None


def test_a_load_that_raises_says_so_in_a_sentence_with_the_exception_as_detail() -> (
    None
):
    callbacks = _callbacks()
    feed = _ScriptedFeed(read_error=OSError("disk unreadable"))
    coordinator = LiveChartCoordinator(MagicMock(), feed, callbacks, _OWNER)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    _token, headline, detail = callbacks.stream_failed.call_args.args
    assert headline == "The chart could not be loaded. Try again."
    assert "disk unreadable" in detail
    callbacks.load_finished.assert_called_once()


def test_a_stream_that_will_not_open_keeps_its_reason_as_detail() -> None:
    callbacks = _callbacks()
    feed = _ScriptedFeed(stream_message="socket closed")
    coordinator = LiveChartCoordinator(MagicMock(), feed, callbacks, _OWNER)

    coordinator._run("BTCUSDT", "1m", _FakeToken(), True)

    _token, headline, detail = callbacks.stream_failed.call_args.args
    assert "BTCUSDT" in headline and "socket closed" not in headline
    assert detail == "socket closed"


def test_the_stream_reports_carry_the_token_of_the_request_they_answer() -> None:
    """`EPIC-034G`: the chart fences a report of a replaced request by it."""
    callbacks = _callbacks()
    coordinator = LiveChartCoordinator(
        MagicMock(),
        MarketDataCandleFeed(
            FakeMarketDataSync(),
            FakeHistoricalKlines(),
            FakeMarketStream(),
            MarketType.SPOT,
        ),
        callbacks,
        _OWNER,
    )
    token = _FakeToken()

    coordinator._run("BTCUSDT", "1m", token, True)

    started_token, _text = callbacks.stream_started.call_args.args
    assert started_token is token
