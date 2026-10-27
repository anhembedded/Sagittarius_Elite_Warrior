"""`EPIC-047H` - the bridge reads the host's candle store read-only, from the shard the host's own writer made.

The shards are written by the real `DatabaseManager` and `KlineModel` (the host's writer), in the venue's own
directory; the reader finds them by the names `shard_name` and `venue_directory` give, with no SQLAlchemy.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.bridge_candles import (
    StoreBridgeCandles,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.models import (
    KlineModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.readonly_candle_shards import (
    ReadOnlyCandleShards,
    shard_path,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    CandleQuery,
    UnknownCandleSeriesError,
)

T0 = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)
VENUE = TradingVenue.FUTURES_TESTNET


def _host_stores(base: Path, venue: TradingVenue, candles: int) -> None:
    """What the host's writer leaves: `candles` 1m rows of BTCUSDT in the venue's shard."""
    manager = DatabaseManager(
        DatabaseConfig(venue_directory(str(base), venue.market_data_venue))
    )
    session = manager.get_session(venue.market_type, "BTCUSDT")  # type: ignore[arg-type]
    for i in range(candles):
        opened = T0 + timedelta(minutes=i)
        session.add(
            KlineModel(
                symbol="BTCUSDT",
                interval="1m",
                open_time=opened.replace(tzinfo=None),
                open_price=100.5 + i,
                high_price=101.0 + i,
                low_price=99.25 + i,
                close_price=100.75 + i,
                volume=1.5,
                close_time=(opened + timedelta(seconds=59)).replace(tzinfo=None),
                quote_asset_volume=0.0,
                number_of_trades=0,
                taker_buy_base_asset_volume=0.0,
                taker_buy_quote_asset_volume=0.0,
            )
        )
    session.commit()
    session.close()


def test_the_newest_candles_come_back_oldest_first_with_exact_prices(
    tmp_path: Path,
) -> None:
    _host_stores(tmp_path, VENUE, 10)

    window = ReadOnlyCandleShards(tmp_path).window(VENUE, "BTCUSDT", "1m", 4, None)

    assert window.shard_found
    assert [c.open_time for c in window.candles] == [
        T0 + timedelta(minutes=i) for i in (6, 7, 8, 9)
    ]
    assert window.candles[-1].close_price == Decimal("109.75")
    assert window.candles[-1].volume == Decimal("1.5")
    assert window.older_available


def test_paging_back_with_before_returns_the_candles_older_than_the_oldest_held(
    tmp_path: Path,
) -> None:
    _host_stores(tmp_path, VENUE, 10)
    shards = ReadOnlyCandleShards(tmp_path)
    newest = shards.window(VENUE, "BTCUSDT", "1m", 4, None)

    older = shards.window(VENUE, "BTCUSDT", "1m", 4, newest.candles[0].open_time)

    assert [c.open_time for c in older.candles] == [
        T0 + timedelta(minutes=i) for i in (2, 3, 4, 5)
    ]
    assert older.older_available
    oldest = shards.window(VENUE, "BTCUSDT", "1m", 4, older.candles[0].open_time)
    assert len(oldest.candles) == 2
    assert not oldest.older_available


def test_a_symbol_with_no_shard_is_not_found_and_no_file_is_created(
    tmp_path: Path,
) -> None:
    window = ReadOnlyCandleShards(tmp_path).window(VENUE, "ETHUSDT", "1m", 4, None)

    assert (window.shard_found, window.candles) == (False, ())
    assert list(tmp_path.rglob("*")) == [], "reading must not create a shard"


def test_another_venues_candles_are_never_served_for_this_one(tmp_path: Path) -> None:
    _host_stores(tmp_path, TradingVenue.FUTURES_MAINNET, 3)

    window = ReadOnlyCandleShards(tmp_path).window(VENUE, "BTCUSDT", "1m", 4, None)

    assert not window.shard_found
    assert shard_path(tmp_path, VENUE, "BTCUSDT") != shard_path(
        tmp_path, TradingVenue.FUTURES_MAINNET, "BTCUSDT"
    )


def test_a_timeframe_the_store_holds_none_of_is_an_empty_window_of_a_found_shard(
    tmp_path: Path,
) -> None:
    _host_stores(tmp_path, VENUE, 3)

    window = ReadOnlyCandleShards(tmp_path).window(VENUE, "BTCUSDT", "1h", 4, None)

    assert (window.shard_found, window.candles, window.older_available) == (
        True,
        (),
        False,
    )


def test_the_reader_cannot_write_to_the_store(tmp_path: Path) -> None:
    _host_stores(tmp_path, VENUE, 2)
    path = shard_path(tmp_path, VENUE, "BTCUSDT")

    with pytest.raises(sqlite3.OperationalError):
        db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        db.execute("DELETE FROM klines")


def test_the_host_keeps_writing_while_the_reader_reads(tmp_path: Path) -> None:
    _host_stores(tmp_path, VENUE, 3)
    path = shard_path(tmp_path, VENUE, "BTCUSDT")
    writer = sqlite3.connect(path, isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "INSERT INTO klines VALUES ('BTCUSDT','1m','2030-01-01 00:00:00.000000',1,1,1,1,1,"
        "'2030-01-01 00:00:59.000000',0,0,0,0)"
    )

    window = ReadOnlyCandleShards(tmp_path).window(VENUE, "BTCUSDT", "1m", 10, None)

    assert len(window.candles) == 3, (
        "a read sees the committed rows while a write is open"
    )
    writer.execute("COMMIT")
    writer.close()


def test_the_bridge_port_refuses_what_it_cannot_name_before_touching_a_file(
    tmp_path: Path,
) -> None:
    candles = StoreBridgeCandles(tmp_path)
    good = CandleQuery("futures_testnet", "BTCUSDT", "1m", 3)

    for bad in (
        CandleQuery("narnia", "BTCUSDT", "1m", 3),
        CandleQuery("disabled", "BTCUSDT", "1m", 3),
        CandleQuery("futures_testnet", "../etc/passwd", "1m", 3),
        CandleQuery("futures_testnet", "BTCUSDT", "7x", 3),
        CandleQuery("futures_testnet", "BTCUSDT", "1m", 0),
        CandleQuery("futures_testnet", "BTCUSDT", "1m", 99999),
    ):
        with pytest.raises(UnknownCandleSeriesError):
            candles.window(bad)

    assert candles.window(good).root == "sew.candle-window/1"
