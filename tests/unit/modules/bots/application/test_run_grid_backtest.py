"""`EPIC-029D` — the backtest query reads what is stored, never fetches, and
refuses in words: no candles (with an offer to sync), too many, unreadable
parameters. A candle with stored 1-second klines replays through them; one
without is coarse."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestRefusal,
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    handler as handler_module,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.streamed_fine_klines import (
    StreamedFineKlines,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestCancelled,
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)
SYMBOL = "BTCUSDT"


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


def _minute(n: int, ohlc: tuple[float, float, float, float]) -> MarketData:
    return _kline(T0 + timedelta(minutes=n), TimeFrame.ONE_MINUTE, ohlc)


def _second(
    minute: int, second: int, ohlc: tuple[float, float, float, float]
) -> MarketData:
    at = T0 + timedelta(minutes=minute, seconds=second)
    return _kline(at, TimeFrame.ONE_SECOND, ohlc)


def _handler(repository: FakeMarketDataRepository) -> RunGridBacktestQueryHandler:
    return RunGridBacktestQueryHandler(StoredKlinesReader(repository), repository)


def _query(**changes: object) -> RunGridBacktestQuery:
    fields: dict[str, object] = {
        "symbol": SYMBOL,
        "config": CONFIG,
        "terms": TERMS,
        "interval": TimeFrame.ONE_MINUTE,
        "start": T0,
        "end": T0 + timedelta(hours=1),
        **changes,
    }
    return RunGridBacktestQuery(**fields)  # type: ignore[arg-type]


#: Minute 0 dips through 64,000 and recovers through 65,000; minute 1 does the
#: same with no 1-second klines stored.
_ROUND_TRIP = (65000.0, 65000.01, 63990.0, 64990.0)


def _stored() -> FakeMarketDataRepository:
    repository = FakeMarketDataRepository()
    repository.save_klines(
        MarketType.SPOT,
        [_minute(0, _ROUND_TRIP), _minute(1, (64990.0, 65000.01, 63990.0, 64990.0))],
    )
    repository.save_klines(
        MarketType.SPOT,
        [
            _second(0, 0, (65000.0, 65000.0, 63990.0, 64000.0)),
            _second(0, 1, (64000.0, 65000.01, 64000.0, 64990.0)),
        ],
    )
    return repository


def test_stored_one_second_klines_order_the_round_trip() -> None:
    result = _handler(_stored()).execute(_query())

    assert isinstance(result, GridBacktestResult)
    assert result.completed_cycles >= 1
    # Minute 0 had 1-second klines; minute 1 is replayed coarse and says so.
    assert result.coarse_periods == (T0 + timedelta(minutes=1),)
    assert [point.time for point in result.equity] == [T0, T0 + timedelta(minutes=1)]


def test_a_period_with_no_stored_candles_offers_a_sync() -> None:
    result = _handler(FakeMarketDataRepository()).execute(_query())

    assert isinstance(result, GridBacktestRefusal)
    assert result.missing_candles
    assert "No 1m candles of BTCUSDT" in result.reason


def test_a_period_too_long_for_the_interval_is_refused_before_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(handler_module, "MAX_CANDLES", 1)

    result = _handler(_stored()).execute(_query())

    assert isinstance(result, GridBacktestRefusal)
    assert not result.missing_candles
    assert "longer interval" in result.reason


def test_unreadable_parameters_are_refused_in_words() -> None:
    result = _handler(_stored()).execute(_query(config={**CONFIG, "grid_count": "x"}))

    assert isinstance(result, GridBacktestRefusal)
    assert "grid_count" in result.reason


def test_a_cancelled_request_returns_no_result() -> None:
    result = _handler(_stored()).execute(_query(cancelled=lambda: True))

    assert result == GridBacktestCancelled(replayed_bars=0, total_bars=2)


def test_a_period_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(ValueError, match="end after it starts"):
        _query(end=T0)


def test_the_stream_drops_what_came_before_and_keeps_what_comes_after() -> None:
    klines = iter(
        [
            _second(0, 0, (1.0, 1.0, 1.0, 1.0)),
            _second(1, 0, (2.0, 2.0, 2.0, 2.0)),
            _second(1, 30, (3.0, 3.0, 3.0, 3.0)),
            _second(2, 0, (4.0, 4.0, 4.0, 4.0)),
        ]
    )
    stream = StreamedFineKlines(klines)

    minute_one = stream.within(T0 + timedelta(minutes=1), T0 + timedelta(minutes=2))
    minute_two = stream.within(T0 + timedelta(minutes=2), T0 + timedelta(minutes=3))

    assert [k.open for k in minute_one] == [2, 3]
    assert [k.open for k in minute_two] == [4]
    assert stream.within(T0 + timedelta(minutes=3), T0 + timedelta(minutes=4)) == ()
