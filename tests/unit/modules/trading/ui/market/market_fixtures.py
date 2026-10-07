"""Doubles for the Market mode's tests, each derived from its port
(`testing-rule.md` §2): a candle feed that records its streams, a thread
manager that runs tasks when the test says, and an account that raises."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    ICandleFeed,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

START = datetime(2026, 10, 1, tzinfo=UTC)


def candle(
    symbol: str,
    index: int,
    *,
    closed: bool = True,
    interval: str = "1m",
    open_price: float = 100.0,
) -> MarketData:
    opened = START + timedelta(minutes=index)
    close = open_price + 1 + index % 5
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=opened,
        open_price=open_price,
        high_price=close + 1,
        low_price=open_price - 1,
        close_price=close,
        volume=10.0,
        close_time=opened + timedelta(minutes=1),
        quote_asset_volume=0.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.0,
        taker_buy_quote_asset_volume=0.0,
        is_closed=closed,
    )


def tick(
    market_data: MarketData,
    market: MarketType = MarketType.SPOT,
    source: MarketDataVenue = MarketDataVenue.MAINNET_PUBLIC,
) -> MarketTickEvent:
    return MarketTickEvent(
        market_data=market_data, market_type=market, market_data_venue=source
    )


class RecordingCandleFeed(ICandleFeed):
    """Serves 60 stored candles per symbol at the timeframe asked for, none
    at the timeframes in `empty`, and records each stream."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.empty: set[str] = set()

    def sync(
        self,
        symbol: str,
        interval: TimeFrame,
        cancelled: Callable[[], bool],
        *,
        newest: int | None = None,
    ) -> None:
        return None

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        if interval.value in self.empty:
            return ()
        return tuple(
            candle(symbol, index, interval=interval.value)
            for index in range(min(limit, 60))
        )

    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        self.started.append(owner_id)
        return CandleStreamStart(True, f"Live for {symbol}.")

    def stop_stream(self, owner_id: str) -> None:
        self.stopped.append(owner_id)


class QueuedThreads(IThreadManager):
    """Holds each task until `run_all()`: the test decides when the worker
    answers, so it can answer late, out of order, or not at all."""

    def __init__(self) -> None:
        self._tasks: list[tuple[Callable[..., Any], tuple[Any, ...]]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self._tasks.append((task, args))
        return concurrent.futures.Future()

    def shutdown(self, wait: bool = True) -> None:
        self._tasks.clear()

    def run_all(self) -> None:
        while self._tasks:
            task, args = self._tasks.pop(0)
            task(*args)

    def run_first(self) -> None:
        task, args = self._tasks.pop(0)
        task(*args)

    def run_last(self) -> None:
        task, args = self._tasks.pop()
        task(*args)


class RaisingAccount(FakeAccountSnapshot):
    """An account whose check raises instead of answering."""

    def check_connection(self) -> ExchangeConnectionStatus:
        raise ConnectionError("proxy refused the tunnel")


def presenter_container(
    event_bus: IEventBus, notifier: RecordingNotifier | None = None
) -> MagicMock:
    """What `BasePresenter` resolves for itself, and the `INotifier` the Market
    presenter tells (`BOT-169`); its own ports come in `MarketDependencies`."""
    config = MagicMock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None, cast=None: default
    services = {
        IEventBus: event_bus,
        IConfig: config,
        ILogger: MagicMock(),
        IDispatcher: MagicMock(),
        INotifier: notifier or RecordingNotifier(),
    }
    container = MagicMock()
    container.resolve.side_effect = services.__getitem__
    return container
