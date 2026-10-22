"""`BOT-233` — the stored candles of a period: from the bot's own venue, counted against the period the
way a backtest counts them, refused past what one backtest draws, and never fetched."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    GetStoredCandlesQuery,
    GetStoredCandlesQueryHandler,
    StoredCandles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    handler as stored_handler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    handler as backtest_handler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)
SYMBOL = "BTCUSDT"
SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET


def _candle(at: datetime, interval: TimeFrame) -> MarketData:
    return MarketData(
        symbol=SYMBOL,
        interval=interval.value,
        open_time=at,
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        volume=1.0,
        close_time=at + timedelta(seconds=interval.to_seconds()),
        quote_asset_volume=1.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=0.5,
    )


def _store(
    repository: FakeMarketDataRepository,
    market: MarketType,
    interval: TimeFrame,
    count: int,
    *,
    skipping: tuple[int, ...] = (),
) -> None:
    step = timedelta(seconds=interval.to_seconds())
    repository.save_klines(
        market,
        [_candle(T0 + step * i, interval) for i in range(count) if i not in skipping],
    )


def _handler(**repositories: FakeMarketDataRepository) -> GetStoredCandlesQueryHandler:
    sources = FakeMarketDataSources()
    for venue, repository in (
        (SPOT, repositories["spot"]),
        (FUTURES, repositories["futures"]),
    ):
        sources.serving(
            FakeMarketDataSources.ports(
                venue.market_data_venue,
                history=StoredKlinesReader(repository),
                repository=repository,
            )
        )
    return GetStoredCandlesQueryHandler(sources)


def _ask(
    handler: GetStoredCandlesQueryHandler,
    venue: TradingVenue,
    interval: TimeFrame,
    hours: int,
) -> StoredCandles:
    return handler.execute(
        GetStoredCandlesQuery(venue, SYMBOL, interval, T0, T0 + timedelta(hours=hours))
    )


def test_a_fully_stored_period_is_returned_oldest_first_and_counted_whole() -> None:
    spot = FakeMarketDataRepository()
    _store(spot, MarketType.SPOT, TimeFrame.ONE_HOUR, 6)

    found = _ask(
        _handler(spot=spot, futures=FakeMarketDataRepository()),
        SPOT,
        TimeFrame.ONE_HOUR,
        6,
    )

    assert [c.open_time for c in found.candles] == sorted(
        c.open_time for c in found.candles
    )
    assert (found.expected, found.stored, found.missing) == (6, 6, 0)
    assert not found.needs_sync


def test_a_gap_is_counted_as_missing_and_a_sync_is_needed() -> None:
    spot = FakeMarketDataRepository()
    _store(spot, MarketType.SPOT, TimeFrame.ONE_HOUR, 6, skipping=(2, 3))

    found = _ask(
        _handler(spot=spot, futures=FakeMarketDataRepository()),
        SPOT,
        TimeFrame.ONE_HOUR,
        6,
    )

    assert len(found.candles) == 4
    assert (found.expected, found.stored, found.missing) == (6, 4, 2)
    assert found.needs_sync


def test_a_period_with_nothing_stored_is_all_missing() -> None:
    found = _ask(
        _handler(spot=FakeMarketDataRepository(), futures=FakeMarketDataRepository()),
        SPOT,
        TimeFrame.ONE_HOUR,
        6,
    )

    assert found.candles == () and found.missing == 6 and found.needs_sync


def test_each_venue_reads_its_own_markets_candles() -> None:
    """`BUG-172`: the Futures bot's period is never drawn from the Spot candles stored for it."""
    spot, futures = FakeMarketDataRepository(), FakeMarketDataRepository()
    _store(spot, MarketType.SPOT, TimeFrame.ONE_HOUR, 6)
    handler = _handler(spot=spot, futures=futures)

    assert _ask(handler, SPOT, TimeFrame.ONE_HOUR, 6).stored == 6
    assert _ask(handler, FUTURES, TimeFrame.ONE_HOUR, 6).stored == 0


def test_the_interval_is_the_one_asked_for() -> None:
    spot = FakeMarketDataRepository()
    _store(spot, MarketType.SPOT, TimeFrame.FIFTEEN_MINUTES, 24)
    handler = _handler(spot=spot, futures=FakeMarketDataRepository())

    assert _ask(handler, SPOT, TimeFrame.FIFTEEN_MINUTES, 6).stored == 24
    assert _ask(handler, SPOT, TimeFrame.ONE_HOUR, 6).stored == 0


def test_a_period_over_the_most_one_backtest_draws_is_refused_before_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(stored_handler, "MAX_CANDLES", 5)
    spot = FakeMarketDataRepository()
    _store(spot, MarketType.SPOT, TimeFrame.ONE_HOUR, 6)

    found = _ask(
        _handler(spot=spot, futures=FakeMarketDataRepository()),
        SPOT,
        TimeFrame.ONE_HOUR,
        6,
    )

    assert found.too_many and found.candles == () and not found.needs_sync
    assert found.expected == 6


def test_the_bound_is_the_one_a_run_refuses_by() -> None:
    """The page must not draw a period the Run next to it would refuse, or the other way about."""
    assert stored_handler.MAX_CANDLES == backtest_handler.MAX_CANDLES
