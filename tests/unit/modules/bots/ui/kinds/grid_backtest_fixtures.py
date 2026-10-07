"""Builders for the Grid backtest page's tests: the real `GridBacktest` (view,
coordinator, presenter) over the real query handler and the market-data
ports' verified fakes.

The pool holds each task until the test runs it, so a test can cancel, or
select another bot, while a run is still in flight. The sync is the verified
fake, which stores nothing; `StoringSync` adds what a real sync does for the
journey under test, writing the period's candles to the fake repository.
"""

from __future__ import annotations

import concurrent.futures
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import QDateTime, QTimeZone
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestContext,
    BacktestPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest import (
    GridBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

SYMBOL = "BTCUSDT"
T0 = datetime(2026, 9, 1, tzinfo=UTC)
#: One day of 15-minute candles.
CANDLES = 96
PERIOD = (T0, T0 + timedelta(minutes=15 * CANDLES))

#: The bots of these tests trade on Spot Testnet; `BUG-172` reads its market.
VENUE = TradingVenue.SPOT_TESTNET


def context(bot_id: str = "a3f9c1", *, terms: bool = True) -> BacktestContext:
    return BacktestContext(bot_id, VENUE, SYMBOL, CONFIG, TERMS if terms else None)


def swinging_candles() -> list[MarketData]:
    """BTC swinging ±2,600 around 65,000 every two hours: through four of the
    report's levels each way, inside its exits."""
    candles = []
    for index in range(CANDLES):
        o = 65000 + 2600 * math.sin(2 * math.pi * index / 8)
        c = 65000 + 2600 * math.sin(2 * math.pi * (index + 1) / 8)
        at = T0 + timedelta(minutes=15 * index)
        candles.append(
            MarketData(
                symbol=SYMBOL,
                interval=TimeFrame.FIFTEEN_MINUTES.value,
                open_time=at,
                open_price=round(o, 2),
                high_price=round(max(o, c) + 5, 2),
                low_price=round(min(o, c) - 5, 2),
                close_price=round(c, 2),
                volume=1.0,
                close_time=at + timedelta(minutes=15),
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.5,
                taker_buy_quote_asset_volume=0.5,
            )
        )
    return candles


class HeldPool(IThreadManager):
    """Keeps each task until `run_all` runs it on the test's thread."""

    def __init__(self) -> None:
        self.pending: list[tuple[Callable[..., Any], tuple[Any, ...]]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self.pending.append((task, args))
        return concurrent.futures.Future()

    def run_all(self) -> None:
        while self.pending:
            task, args = self.pending.pop(0)
            task(*args)

    def shutdown(self, wait: bool = True) -> None:
        self.pending.clear()


def _never() -> bool:
    return False


class QueryDispatcher(ICommandDispatcher):
    """Runs the real `RunGridBacktestQueryHandler`, as the app's dispatcher
    resolves it from the bots module's binding.

    `honours_cancel = False` models a replay that had already finished when
    Cancel was clicked: its result is on its way, and only the presenter's
    fence keeps it off the screen."""

    def __init__(self, repository: FakeMarketDataRepository) -> None:
        self._handler = RunGridBacktestQueryHandler(
            FakeMarketDataSources().serving(
                FakeMarketDataSources.ports(
                    VENUE.market_data_venue,
                    history=StoredKlinesReader(repository),
                    repository=repository,
                )
            )
        )
        self.queries: list[RunGridBacktestQuery] = []
        self.honours_cancel = True
        #: What the query raises instead of running, when a test sets it.
        self.raises: Exception | None = None

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any:
        if handler_class is not RunGridBacktestQuery or not isinstance(
            input_dto, RunGridBacktestQuery
        ):
            raise LookupError(f"no handler for {handler_class.__name__}")
        self.queries.append(input_dto)
        if self.raises is not None:
            raise self.raises
        run = input_dto if self.honours_cancel else replace(input_dto, cancelled=_never)
        return self._handler.execute(run)


class StoringSync(FakeMarketDataSync):
    """The verified fake, plus what a real sync leaves behind: the 15-minute
    candles of the period, written to the repository."""

    def __init__(self, repository: FakeMarketDataRepository) -> None:
        super().__init__()
        self._repository = repository

    def sync(self, request: MarketDataSyncRequest) -> None:
        super().sync(request)
        if request.interval is TimeFrame.FIFTEEN_MINUTES:
            self._repository.save_klines(MarketType.SPOT, swinging_candles())


@dataclass
class BacktestWorld:
    backtest: GridBacktest
    pool: HeldPool
    repository: FakeMarketDataRepository
    dispatcher: QueryDispatcher
    sync: FakeMarketDataSync
    notifier: RecordingNotifier


def build_backtest(
    *,
    stored: bool = True,
    storing_sync: bool = False,
    sync: FakeMarketDataSync | None = None,
) -> BacktestWorld:
    repository = FakeMarketDataRepository()
    if stored:
        repository.save_klines(MarketType.SPOT, swinging_candles())
    pool = HeldPool()
    dispatcher = QueryDispatcher(repository)
    sync = sync or (StoringSync(repository) if storing_sync else FakeMarketDataSync())
    notifier = RecordingNotifier()
    feed = MarketDataCandleFeed(
        sync, StoredKlinesReader(repository), FakeMarketStream(), MarketType.SPOT
    )
    backtest = GridBacktest(BacktestPorts(pool, dispatcher, sync, feed, notifier))
    view = backtest.view
    utc = QTimeZone.utc()
    view.start.setDateTime(
        QDateTime.fromSecsSinceEpoch(int(PERIOD[0].timestamp()), utc)
    )
    view.end.setDateTime(QDateTime.fromSecsSinceEpoch(int(PERIOD[1].timestamp()), utc))
    return BacktestWorld(backtest, pool, repository, dispatcher, sync, notifier)
