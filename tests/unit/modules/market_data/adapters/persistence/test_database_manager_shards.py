from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.models import (
    Base,
    KlineModel,
)
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import (
    SqliteShardConfig,
    SqliteShardManager,
)


def test_list_shards_and_remove_shard_in_temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            # Create two shard databases
            with manager.get_session(MarketType.SPOT, "BTCUSDT"):
                pass
            with manager.get_session(MarketType.SPOT, "ETHUSDT"):
                pass

            shards = manager.list_shards(MarketType.SPOT)
            assert "BTCUSDT" in shards
            assert "ETHUSDT" in shards
            assert len(shards) == 2

            # Remove one shard
            removed = manager.remove_shard(MarketType.SPOT, "BTCUSDT")
            assert removed is True

            shards_after = manager.list_shards(MarketType.SPOT)
            assert "BTCUSDT" not in shards_after
            assert "ETHUSDT" in shards_after

            # Check files on disk, market-qualified
            assert not (Path(tmpdir) / "spot_BTCUSDT.db").exists()
            assert (Path(tmpdir) / "spot_ETHUSDT.db").exists()
        finally:
            manager.dispose_all()


def test_spot_and_futures_shards_of_the_same_symbol_are_independent():
    """EPIC-027A acceptance: Spot and Futures candles of the same symbol and
    interval can coexist, and neither overwrites the other."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            with manager.get_session(MarketType.SPOT, "BTCUSDT"):
                pass

            assert manager.has_shard(MarketType.SPOT, "BTCUSDT") is True
            assert manager.has_shard(MarketType.FUTURES_USD_M, "BTCUSDT") is False

            with manager.get_session(MarketType.FUTURES_USD_M, "BTCUSDT"):
                pass

            assert manager.has_shard(MarketType.FUTURES_USD_M, "BTCUSDT") is True
            # Removing the Futures shard must not touch the Spot one.
            removed = manager.remove_shard(MarketType.FUTURES_USD_M, "BTCUSDT")
            assert removed is True
            assert manager.has_shard(MarketType.SPOT, "BTCUSDT") is True

            assert (Path(tmpdir) / "spot_BTCUSDT.db").exists()
            assert not (Path(tmpdir) / "futures_usd_m_BTCUSDT.db").exists()
        finally:
            manager.dispose_all()


def test_purge_all_shards():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            with manager.get_session(MarketType.SPOT, "SOLUSDT"):
                pass
            with manager.get_session(MarketType.FUTURES_USD_M, "BNBUSDT"):
                pass

            assert len(manager.list_shards(MarketType.SPOT)) == 1
            assert len(manager.list_shards(MarketType.FUTURES_USD_M)) == 1

            purged_count = manager.purge_all_shards()
            assert purged_count == 2
            assert len(manager.list_shards(MarketType.SPOT)) == 0
            assert len(manager.list_shards(MarketType.FUTURES_USD_M)) == 0
        finally:
            manager.dispose_all()


def test_vacuum_shards_without_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            with manager.get_session(MarketType.SPOT, "XRPUSDT"):
                pass

            # Vacuum single
            manager.vacuum(MarketType.SPOT, "XRPUSDT")
            # Vacuum all shards of one market
            manager.vacuum(MarketType.SPOT)
        finally:
            manager.dispose_all()


def test_list_legacy_shard_names_finds_unmigrated_bare_symbol_shards():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            with manager.get_session(MarketType.SPOT, "ETHUSDT"):
                pass
            # Simulate a shard written before EPIC-027A: bare symbol name, no
            # market prefix. Only the file's name matters to this listing.
            (Path(tmpdir) / "BTCUSDT.db").touch()

            assert manager.list_legacy_shard_names() == ["BTCUSDT"]
        finally:
            manager.dispose_all()


def test_migrate_legacy_shards_is_idempotent_and_tags_data_as_spot():
    """EPIC-027A acceptance: existing shards are migrated once, following ADR
    O3 ("tag as Spot"), idempotently, and a legacy shard's data survives."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # A shard written before EPIC-027A: bare symbol name, real schema and
        # data, created the same way the pre-migration repository did.
        legacy = SqliteShardManager(
            SqliteShardConfig(directory=tmpdir, metadata=Base.metadata)
        )
        try:
            with legacy.get_raw_session("BTCUSDT") as session:
                session.add(
                    KlineModel(
                        symbol="BTCUSDT",
                        interval="1h",
                        open_time=datetime(2026, 1, 1, tzinfo=UTC),
                        open_price=1.0,
                        high_price=2.0,
                        low_price=0.5,
                        close_price=1.5,
                        volume=10.0,
                        close_time=datetime(2026, 1, 1, 1, tzinfo=UTC),
                        quote_asset_volume=15.0,
                        number_of_trades=3,
                        taker_buy_base_asset_volume=1.0,
                        taker_buy_quote_asset_volume=1.5,
                    )
                )
                session.commit()
        finally:
            legacy.dispose_all()

        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)
        try:
            first_run = manager.migrate_legacy_shards()
            assert first_run == ["BTCUSDT"]
            assert manager.list_legacy_shard_names() == []
            assert manager.has_shard(MarketType.SPOT, "BTCUSDT") is True

            # Idempotent: nothing legacy left, so the second call is a no-op.
            second_run = manager.migrate_legacy_shards()
            assert second_run == []

            # The data itself survived the rename untouched.
            with manager.get_session(MarketType.SPOT, "BTCUSDT") as session:
                rows = session.query(KlineModel).filter_by(symbol="BTCUSDT").all()
                assert len(rows) == 1
                assert rows[0].close_price == 1.5
        finally:
            manager.dispose_all()


def test_migrate_legacy_shards_refuses_to_overwrite_an_existing_destination(caplog):
    """`os.rename` overwrites an existing destination silently on POSIX — a
    real install can already have `spot_BTCUSDT.db` (e.g. a prior partial
    migration, a restored backup) alongside a re-introduced bare-name
    `BTCUSDT.db`. Migrating must never destroy the pre-existing Spot data to
    make room for the "legacy" one; the legacy shard is left unmigrated and
    the collision is logged loudly instead."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)
        try:
            # Real, already-migrated Spot data — this must survive untouched.
            with manager.get_session(MarketType.SPOT, "BTCUSDT") as session:
                session.add(
                    KlineModel(
                        symbol="BTCUSDT",
                        interval="1h",
                        open_time=datetime(2026, 1, 1, tzinfo=UTC),
                        open_price=100.0,
                        high_price=110.0,
                        low_price=90.0,
                        close_price=105.0,
                        volume=1.0,
                        close_time=datetime(2026, 1, 1, 1, tzinfo=UTC),
                        quote_asset_volume=105.0,
                        number_of_trades=1,
                        taker_buy_base_asset_volume=0.5,
                        taker_buy_quote_asset_volume=52.5,
                    )
                )
                session.commit()
            manager.dispose_all()

            # A bare-name legacy shard re-introduced alongside it (the
            # collision scenario) — its own content is irrelevant here.
            (Path(tmpdir) / "BTCUSDT.db").touch()

            manager = DatabaseManager(config)
            with caplog.at_level("ERROR", logger="App.Database"):
                migrated = manager.migrate_legacy_shards()

            assert migrated == []
            assert manager.list_legacy_shard_names() == ["BTCUSDT"]
            assert any(
                "BTCUSDT" in record.getMessage()
                and "already exists" in record.getMessage()
                for record in caplog.records
            )

            # The real Spot data was never touched.
            with manager.get_session(MarketType.SPOT, "BTCUSDT") as session:
                rows = session.query(KlineModel).filter_by(symbol="BTCUSDT").all()
                assert len(rows) == 1
                assert rows[0].close_price == 105.0
        finally:
            manager.dispose_all()
