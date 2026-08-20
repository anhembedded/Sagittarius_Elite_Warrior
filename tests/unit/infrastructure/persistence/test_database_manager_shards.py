from __future__ import annotations

import tempfile
from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)


def test_list_shards_and_remove_shard_in_temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            # Create two shard databases
            with manager.get_session("BTCUSDT"):
                pass
            with manager.get_session("ETHUSDT"):
                pass

            shards = manager.list_shards()
            assert "BTCUSDT" in shards
            assert "ETHUSDT" in shards
            assert len(shards) == 2

            # Remove one shard
            removed = manager.remove_shard("BTCUSDT")
            assert removed is True

            shards_after = manager.list_shards()
            assert "BTCUSDT" not in shards_after
            assert "ETHUSDT" in shards_after

            # Check files on disk
            assert not (Path(tmpdir) / "BTCUSDT.db").exists()
            assert (Path(tmpdir) / "ETHUSDT.db").exists()
        finally:
            manager.dispose_all()


def test_purge_all_shards():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            with manager.get_session("SOLUSDT"):
                pass
            with manager.get_session("BNBUSDT"):
                pass

            assert len(manager.list_shards()) == 2

            purged_count = manager.purge_all_shards()
            assert purged_count == 2
            assert len(manager.list_shards()) == 0
        finally:
            manager.dispose_all()


def test_vacuum_shards_without_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(db_dir=tmpdir)
        manager = DatabaseManager(config)

        try:
            with manager.get_session("XRPUSDT"):
                pass

            # Vacuum single
            manager.vacuum("XRPUSDT")
            # Vacuum all
            manager.vacuum()
        finally:
            manager.dispose_all()
