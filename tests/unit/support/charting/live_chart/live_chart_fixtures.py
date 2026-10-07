"""Builders for the live chart's state tests: a real `ChartCard` and
`LiveCandleChart` over a candle feed a test scripts."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

OWNER = "test.owner"


class InlineThreadManager(IThreadManager):
    """Runs each task at once on the test's thread."""

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


class HeldThreadManager(IThreadManager):
    """Keeps each task until the test runs it: a load in flight."""

    def __init__(self) -> None:
        self.held: list[Callable[[], None]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self.held.append(lambda: task(*args, **kwargs))
        return concurrent.futures.Future()

    def run_all(self) -> None:
        held, self.held = self.held, []
        for task in held:
            task()

    def shutdown(self, wait: bool = True) -> None:
        return None


class ScriptedCandleFeed(ICandleFeed):
    """A feed whose sync and stream answer as the test says, and that records
    what it was asked."""

    def __init__(self) -> None:
        self.stream_message: str | None = None
        self.sync_error: str | None = None
        self.calls: list[str] = []
        #: What is stored: a chart opened at rest on an empty store fetches
        #: it (`BUG-172`), so most tests of "no network at rest" store a candle.
        self.stored: Sequence[MarketData] = ()

    def sync(
        self,
        symbol: str,
        interval: TimeFrame,
        cancelled: Callable[[], bool],
        *,
        newest: int | None = None,
    ) -> None:
        self.calls.append("sync")
        if self.sync_error is not None:
            raise RuntimeError(self.sync_error)

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        self.calls.append("history")
        return list(self.stored)

    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        self.calls.append("start_stream")
        if self.stream_message is not None:
            return CandleStreamStart(False, self.stream_message)
        return CandleStreamStart(True, "started")

    def stop_stream(self, owner_id: str) -> None:
        self.calls.append("stop_stream")


class Clock:
    """A clock a test moves."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def build_chart(
    feed: ScriptedCandleFeed,
    clock: Clock | None = None,
    threads: IThreadManager | None = None,
    notifier: RecordingNotifier | None = None,
) -> tuple[LiveCandleChart, ChartCard]:
    card = ChartCard("BTCUSDT")
    ports = LiveChartPorts(
        thread_manager=threads or InlineThreadManager(),
        feed=feed,
        stream_owner=OWNER,
        interval="1m",
        market=MarketType.SPOT,
        clock=clock or Clock(),
        notifier=notifier or RecordingNotifier(),
        scope="test",
    )
    return LiveCandleChart(card, ports, parent=card), card
