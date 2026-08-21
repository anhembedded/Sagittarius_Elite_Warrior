import gc
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)


@pytest.fixture
def repo(tmp_path):
    db_config = DatabaseConfig(db_dir=str(tmp_path))
    db_manager = DatabaseManager(db_config)
    repository = SQLAlchemyMarketDataRepository(db_manager)
    yield repository
    # Dispose all SQLAlchemy engines to release SQLite file handles on teardown.
    # Without this Python's GC fires ResourceWarning: unclosed database.
    db_manager.dispose_all()


def create_mock_kline(symbol: str, timestamp: datetime) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=timestamp,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=timestamp,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def test_save_and_get_klines(repo):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=UTC)

    klines = [create_mock_kline("BTCUSDT", dt1), create_mock_kline("BTCUSDT", dt2)]

    repo.save_klines(klines)

    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)

    assert len(fetched) == 2
    assert fetched[0].open_time == dt1
    assert fetched[1].open_time == dt2
    assert fetched[0].close_price == 105.0

    # Assert all volumes and fields to prevent silent mapping bugs
    assert fetched[0].volume == 1000.0
    assert fetched[0].quote_asset_volume == 105000.0
    assert fetched[0].number_of_trades == 50
    assert fetched[0].taker_buy_base_asset_volume == 500.0
    assert fetched[0].taker_buy_quote_asset_volume == 52500.0


def test_upsert_behavior(repo):
    dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    kline1 = create_mock_kline("ETHUSDT", dt)

    repo.save_klines([kline1])

    # Save the same kline but with updated price (simulating an upsert)
    kline2 = create_mock_kline("ETHUSDT", dt)
    # Using object.__setattr__ because MarketData is frozen=True
    object.__setattr__(kline2, "close_price", 200.0)

    repo.save_klines([kline2])

    fetched = repo.get_klines("ETHUSDT", TimeFrame.ONE_MINUTE)

    assert len(fetched) == 1
    assert fetched[0].close_price == 200.0  # Should be updated


def test_get_latest_kline_time(repo):
    assert repo.get_latest_kline_time("BNBUSDT", TimeFrame.ONE_MINUTE) is None

    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=UTC)

    repo.save_klines(
        [create_mock_kline("BNBUSDT", dt1), create_mock_kline("BNBUSDT", dt2)]
    )

    latest = repo.get_latest_kline_time("BNBUSDT", TimeFrame.ONE_MINUTE)

    assert latest == dt2


def test_get_klines_with_time_range(repo):
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=UTC)
    dt3 = datetime(2023, 1, 1, 12, 2, tzinfo=UTC)

    repo.save_klines(
        [
            create_mock_kline("BTCUSDT", dt1),
            create_mock_kline("BTCUSDT", dt2),
            create_mock_kline("BTCUSDT", dt3),
        ]
    )

    # Query only middle point
    fetched = repo.get_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, start_time=dt2, end_time=dt2
    )
    assert len(fetched) == 1
    assert fetched[0].open_time == dt2

    # Query from middle to end
    fetched2 = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE, start_time=dt2)
    assert len(fetched2) == 2
    assert fetched2[0].open_time == dt2
    assert fetched2[1].open_time == dt3


def test_get_klines_with_limit(repo):
    from datetime import timedelta

    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)
    ]
    repo.save_klines(klines)

    # Get last 3 klines efficiently descending
    fetched = repo.get_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, limit=3, order_by_desc=True
    )

    assert len(fetched) == 3
    # Check that they are the latest 3 in DESCENDING order
    assert fetched[0].open_time == base_dt + timedelta(minutes=9)
    assert fetched[1].open_time == base_dt + timedelta(minutes=8)
    assert fetched[2].open_time == base_dt + timedelta(minutes=7)


def test_save_klines_bulk_chunking(repo):
    from datetime import timedelta

    # Create 12000 mock klines to ensure chunking logic (5000 per chunk) is executed
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i))
        for i in range(12000)
    ]

    # This should not raise any exceptions and should insert in chunks
    repo.save_klines(klines)

    # Verify count
    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)
    assert len(fetched) == 12000
    assert fetched[0].open_time == base_dt
    assert fetched[-1].open_time == base_dt + timedelta(minutes=11999)


def test_multi_symbol_db_separation(repo):
    from datetime import timedelta

    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)

    # Save klines for BTC and ETH in the same batch
    btc_klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(5)
    ]
    eth_klines = [
        create_mock_kline("ETHUSDT", base_dt + timedelta(minutes=i)) for i in range(5)
    ]

    repo.save_klines(btc_klines + eth_klines)

    # Retrieve independently
    btc_fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)
    eth_fetched = repo.get_klines("ETHUSDT", TimeFrame.ONE_MINUTE)

    assert len(btc_fetched) == 5
    assert len(eth_fetched) == 5

    # Ensure they don't leak into each other (symbol check is intrinsic, but we also know they use different engines)
    assert all(k.symbol == "BTCUSDT" for k in btc_fetched)
    assert all(k.symbol == "ETHUSDT" for k in eth_fetched)

    # Verify internal session pool created two engines
    assert len(repo.db_manager._sessions) == 2
    assert "BTCUSDT" in repo.db_manager._sessions
    assert "ETHUSDT" in repo.db_manager._sessions


def test_get_database_status_empty_database(repo):
    """An empty database returns a zeroed, typed DatabaseStatusSnapshot — not a dict."""
    status = repo.get_database_status("NOSUCHCOIN", TimeFrame.ONE_MINUTE)

    assert isinstance(status, DatabaseStatusSnapshot)
    assert status.first_record is None
    assert status.last_record is None
    assert status.total_candles == 0
    assert status.gaps == 0


def test_get_database_status_detects_gap(repo):
    """A missing candle between two stored ones is counted as a gap."""
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    dt2 = datetime(2023, 1, 1, 12, 1, tzinfo=UTC)
    # dt3 skips minute 12:02 entirely -> one gap at the expected 1-minute interval.
    dt3 = datetime(2023, 1, 1, 12, 5, tzinfo=UTC)

    repo.save_klines(
        [
            create_mock_kline("BTCUSDT", dt1),
            create_mock_kline("BTCUSDT", dt2),
            create_mock_kline("BTCUSDT", dt3),
        ]
    )

    status = repo.get_database_status("BTCUSDT", TimeFrame.ONE_MINUTE)

    assert isinstance(status, DatabaseStatusSnapshot)
    assert status.first_record == dt1
    assert status.last_record == dt3
    assert status.total_candles == 3
    assert status.gaps == 1


def test_get_range_coverage_is_half_open_and_reports_first_gap(repo):
    start = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    rows = [
        create_mock_kline("BTCUSDT", start),
        create_mock_kline("BTCUSDT", start + timedelta(minutes=1)),
        create_mock_kline("BTCUSDT", start + timedelta(minutes=3)),
        create_mock_kline("BTCUSDT", start + timedelta(minutes=4)),
    ]
    repo.save_klines(rows)

    snapshot = repo.get_range_coverage(
        "BTCUSDT",
        TimeFrame.ONE_MINUTE,
        start,
        start + timedelta(minutes=4),
        start + timedelta(minutes=10),
    )

    assert snapshot.first_record == start
    assert snapshot.last_record == start + timedelta(minutes=3)
    assert snapshot.total_candles == 3
    assert snapshot.first_gap_after == start + timedelta(minutes=1)


def _live_market_data_count() -> int:
    """Counts real, currently-alive `MarketData` instances via the GC heap —
    deterministic and reproducible across machines/CI, unlike sampling OS-level
    RSS (noisy, affected by allocator behavior — see BUG-025's own report for
    why an RSS-based test was rejected). Same helper as the Sync side's proof
    in `test_python_binance_client_unit.py`, duplicated locally rather than
    shared since it is 4 lines and this is the only other file that needs it."""
    gc.collect()
    return sum(1 for obj in gc.get_objects() if type(obj) is MarketData)


def test_count_klines_matches_get_klines_length(repo):
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)
    ]
    repo.save_klines(klines)

    assert repo.count_klines("BTCUSDT", TimeFrame.ONE_MINUTE) == 10


def test_count_klines_respects_time_range_and_limit(repo):
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)
    ]
    repo.save_klines(klines)

    assert (
        repo.count_klines(
            "BTCUSDT", TimeFrame.ONE_MINUTE, start_time=base_dt + timedelta(minutes=5)
        )
        == 5
    )
    assert repo.count_klines("BTCUSDT", TimeFrame.ONE_MINUTE, limit=3) == 3


def test_count_klines_on_empty_database_is_zero(repo):
    assert repo.count_klines("BTCUSDT", TimeFrame.ONE_MINUTE) == 0


def test_stream_klines_yields_the_same_rows_as_get_klines(repo):
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)
    ]
    repo.save_klines(klines)

    streamed = list(repo.stream_klines("BTCUSDT", TimeFrame.ONE_MINUTE))
    fetched = repo.get_klines("BTCUSDT", TimeFrame.ONE_MINUTE)

    assert [k.open_time for k in streamed] == [k.open_time for k in fetched]


def test_stream_klines_offset_and_limit_select_the_out_of_sample_tail(repo):
    """Mirrors exactly how RunStaticBacktestCommandHandler asks for the
    out-of-sample phase (BUG-025): offset = in-sample count, limit =
    out-of-sample count, over the same ascending chronological order."""
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i)) for i in range(10)
    ]
    repo.save_klines(klines)

    tail = list(repo.stream_klines("BTCUSDT", TimeFrame.ONE_MINUTE, offset=7, limit=3))

    assert [k.open_time for k in tail] == [
        base_dt + timedelta(minutes=i) for i in (7, 8, 9)
    ]


def test_stream_klines_never_holds_more_than_a_bounded_number_of_rows_live(repo):
    """Real memory proof for BUG-025's Backtest side, not just a row-count
    assertion — same technique as the Sync side's
    `test_streaming_and_discarding_chunks_never_lets_more_than_one_chunk_stay_alive`,
    adapted for a per-row (not per-chunk) generator: `gc.collect()` is not
    cheap, so this samples the live count periodically instead of on every
    single row — sampling every row across thousands of them made the test
    itself take minutes.

    Saves far more rows than one internal fetch chunk, then walks the
    generator discarding each row immediately (mirrors how `_simulate()`
    consumes it: one candle touched at a time, nothing retained), sampling
    real live `MarketData` objects on the GC heap periodically. If
    `stream_klines()` secretly materialized the whole result set first (the
    original bug), the sampled live count would climb roughly linearly with
    rows streamed instead of staying flat and small."""
    base_dt = datetime(2023, 1, 1, 12, 0, tzinfo=UTC)
    total_rows = 2500
    sample_every = 250
    klines = [
        create_mock_kline("BTCUSDT", base_dt + timedelta(minutes=i))
        for i in range(total_rows)
    ]
    repo.save_klines(klines)

    baseline = _live_market_data_count()
    peak_live_beyond_baseline = 0

    for index, row in enumerate(repo.stream_klines("BTCUSDT", TimeFrame.ONE_MINUTE)):
        if index % sample_every == 0:
            live_now = _live_market_data_count() - baseline
            peak_live_beyond_baseline = max(peak_live_beyond_baseline, live_now)
        del row

    final_live = _live_market_data_count() - baseline

    # Generous bound: well under total_rows is enough to prove this isn't a
    # full materialization, without pinning to SQLAlchemy's exact internal
    # yield_per buffering, which is an implementation detail, not a contract.
    assert peak_live_beyond_baseline < total_rows // 2
    assert final_live == 0
