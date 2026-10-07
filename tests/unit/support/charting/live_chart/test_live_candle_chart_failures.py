"""`BOT-169` — a chart's failed sync or stream reaches the notifier as one
background notice for its mode, with a Retry that loads the chart again, and
a stream that opens clears it."""

from __future__ import annotations

import concurrent.futures

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    CandlesUnavailableError,
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_SCOPE = "market"
_CAUSE = "charting.live_stream.market.BTCUSDT"


class _InlineThreads(IThreadManager):
    def submit(self, task, *args, **kwargs):
        future: concurrent.futures.Future = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


class _Feed(ICandleFeed):
    def __init__(self) -> None:
        self.sync_error: Exception | None = RuntimeError("HTTP 502 <html>")
        self.syncs = 0

    def sync(self, symbol, interval, cancelled) -> None:
        self.syncs += 1
        if self.sync_error is not None:
            raise self.sync_error

    def load_history(self, symbol, interval, limit):
        return ()

    def start_stream(self, owner_id, symbol, interval) -> CandleStreamStart:
        return CandleStreamStart(True, "")

    def stop_stream(self, owner_id) -> None:
        return None


def _chart(qapp, feed: _Feed, notifier: RecordingNotifier) -> LiveCandleChart:
    ports = LiveChartPorts(
        thread_manager=_InlineThreads(),
        feed=feed,
        stream_owner="market.BTCUSDT",
        interval="1m",
        market=MarketType.SPOT,
        notifier=notifier,
        scope=_SCOPE,
    )
    return LiveCandleChart(ChartCard("BTCUSDT"), ports)


def test_a_failed_sync_is_a_background_notice_with_retry_and_detail(qapp) -> None:
    notifier = RecordingNotifier()
    feed = _Feed()
    chart = _chart(qapp, feed, notifier)
    logged: list[str] = []
    chart.logged.connect(logged.append)

    chart.go_live()
    chart.show_symbol("BTCUSDT")

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.cause == _CAUSE
    assert notice.scope == _SCOPE
    assert "BTCUSDT" in notice.headline
    assert "502" not in notice.headline and "502" in notice.detail
    assert notice.retry is not None
    assert all("502" not in line for line in logged)
    assert any(line.startswith("[ERROR]") for line in logged)


def test_retry_loads_again_and_an_opened_stream_clears_the_notice(qapp) -> None:
    notifier = RecordingNotifier()
    feed = _Feed()
    chart = _chart(qapp, feed, notifier)
    chart.go_live()
    chart.show_symbol("BTCUSDT")
    retry = notifier.last.retry
    assert retry is not None
    feed.sync_error = None

    retry()

    assert feed.syncs == 2
    assert _CAUSE in notifier.cleared
    assert set(notifier.cleared) == {_CAUSE}


def test_a_refusal_for_good_is_said_as_it_is_and_never_as_try_again(qapp) -> None:
    """`BUG-172` — Futures has no `1s` candles and a testnet lists fewer symbols.
    Asking again cannot change either answer, so the notice carries the reason the
    exchange gave, in words, and the chart still shows what is stored."""
    notifier = RecordingNotifier()
    feed = _Feed()
    feed.sync_error = CandlesUnavailableError(
        "This exchange has no 1s candles for its USDⓈ-M Futures market."
    )
    chart = _chart(qapp, feed, notifier)
    logged: list[str] = []
    chart.logged.connect(logged.append)

    chart.go_live()
    chart.show_symbol("BTCUSDT")

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert "has no 1s candles" in notice.headline
    assert "try again" not in notice.headline.lower()
    assert "stored candles" in notice.headline
    assert feed.syncs == 1


def test_a_short_history_draws_what_exists_and_says_nothing_is_wrong(qapp) -> None:
    """`BUG-172` — Spot Testnet keeps little history: a sync that stores fewer
    candles than a mainnet would is an ordinary success, not a failure."""
    notifier = RecordingNotifier()
    feed = _Feed()
    feed.sync_error = None
    chart = _chart(qapp, feed, notifier)

    chart.go_live()
    chart.show_symbol("BTCUSDT")

    assert notifier.failures == []
