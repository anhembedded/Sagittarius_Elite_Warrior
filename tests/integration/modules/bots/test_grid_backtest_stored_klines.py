"""`EPIC-029D` — a Grid backtest over candles stored in the real SQLite shards.

Two hours of BTCUSDT swinging through the report's ladder, written as
1-second klines and the 1-minute candles they make, then replayed through
`RunGridBacktestQuery` against `SQLAlchemyMarketDataRepository`: the
repository's stream feeds the replay a candle at a time. The same period
without its 1-second klines is replayed coarse, which is conservative in
cycles: it never completes more than the 1-second replay. (Its final equity
can still differ either way through the inventory marked at the end, the
PR #338 review's randomized probe, so that is not claimed.)

Two hours rather than the task's week: a week is 600,000 one-second rows,
minutes of inserts for the same mechanism (recorded in the task file).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)
#: The venue whose stored candles the replay reads (`BUG-172`).
VENUE = TradingVenue.SPOT_TESTNET
SYMBOL = "BTCUSDT"
SECONDS = 2 * 60 * 60


def _kline(
    at: datetime, interval: TimeFrame, ohlc: tuple[float, float, float, float]
) -> MarketData:
    o, h, low, c = ohlc
    return MarketData(
        symbol=SYMBOL,
        interval=interval.value,
        open_time=at,
        open_price=o,
        high_price=h,
        low_price=low,
        close_price=c,
        volume=1.0,
        close_time=at + timedelta(seconds=interval.to_seconds()),
        quote_asset_volume=1.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=0.5,
    )


def _price(second: int) -> float:
    """A swing of ±2,600 around 65,000 every 20 minutes: through four levels
    each way, inside the stop loss and the take profit."""
    return round(65000 + 2600 * math.sin(2 * math.pi * second / 1200), 2)


def _seconds() -> list[MarketData]:
    klines = []
    for second in range(SECONDS):
        o, c = _price(second), _price(second + 1)
        klines.append(
            _kline(
                T0 + timedelta(seconds=second),
                TimeFrame.ONE_SECOND,
                (o, max(o, c) + 1, min(o, c) - 1, c),
            )
        )
    return klines


def _minutes(seconds: list[MarketData]) -> list[MarketData]:
    minutes = []
    for start in range(0, len(seconds), 60):
        part = seconds[start : start + 60]
        minutes.append(
            _kline(
                part[0].open_time,
                TimeFrame.ONE_MINUTE,
                (
                    part[0].open_price,
                    max(k.high_price for k in part),
                    min(k.low_price for k in part),
                    part[-1].close_price,
                ),
            )
        )
    return minutes


@pytest.fixture
def repository(tmp_path) -> Iterator[SQLAlchemyMarketDataRepository]:
    manager = DatabaseManager(DatabaseConfig(db_dir=str(tmp_path)))
    yield SQLAlchemyMarketDataRepository(manager)
    manager.dispose_all()


def _replay(repository: SQLAlchemyMarketDataRepository) -> GridBacktestResult:
    sources = FakeMarketDataSources().serving(
        FakeMarketDataSources.ports(
            VENUE.market_data_venue,
            history=StoredKlinesReader(repository),
            repository=repository,
        )
    )
    result = RunGridBacktestQueryHandler(sources).execute(
        RunGridBacktestQuery(
            SYMBOL,
            CONFIG,
            TERMS,
            TimeFrame.ONE_MINUTE,
            T0,
            T0 + timedelta(seconds=SECONDS),
            VENUE,
        )
    )
    assert isinstance(result, GridBacktestResult)
    return result


def test_two_stored_hours_replay_through_their_one_second_klines(
    repository: SQLAlchemyMarketDataRepository,
) -> None:
    seconds = _seconds()
    repository.save_klines(MarketType.SPOT, _minutes(seconds))
    repository.save_klines(MarketType.SPOT, seconds)

    result = _replay(repository)

    assert result.stop_reason is StopReason.END_OF_DATA
    assert len(result.equity) == SECONDS // 60
    assert result.coarse_periods == ()
    assert result.completed_cycles >= 6
    assert result.grid_profit > 0
    assert result.maker_fees > 0


def test_without_one_second_klines_the_replay_is_coarse_and_completes_no_more_cycles(
    repository: SQLAlchemyMarketDataRepository,
) -> None:
    seconds = _seconds()
    repository.save_klines(MarketType.SPOT, _minutes(seconds))
    coarse = _replay(repository)
    repository.save_klines(MarketType.SPOT, seconds)
    fine = _replay(repository)

    assert coarse.coarse_periods
    assert coarse.completed_cycles <= fine.completed_cycles
