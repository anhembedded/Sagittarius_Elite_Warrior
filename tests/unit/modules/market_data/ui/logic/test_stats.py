"""`logic/stats.py`: the Data status bar's stat values are raw numbers (bytes,
candles) or `None`, never display text (`EPIC-033N`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.market_data.ui.logic.stats import (
    database_size_bytes,
    stored_records,
)


def test_the_size_is_the_bytes_of_every_database_file(tmp_path):
    (tmp_path / "BTCUSDT_1m.db").write_bytes(b"x" * 1000)
    (tmp_path / "BTCUSDT_1m.db-wal").write_bytes(b"x" * 24)
    (tmp_path / "notes.txt").write_bytes(b"x" * 5000)

    assert database_size_bytes(tmp_path) == 1024
    assert database_size_bytes(str(tmp_path)) == 1024


def test_an_unknown_size_is_none(tmp_path):
    assert database_size_bytes(None) is None
    assert database_size_bytes("  ") is None
    assert database_size_bytes(tmp_path / "missing") is None
    assert database_size_bytes(tmp_path) is None  # a directory with no database


def test_records_are_summed_and_unknown_before_any_count():
    assert stored_records([1200, 1440]) == 2640
    assert stored_records([]) is None
    assert stored_records([0, 0]) is None
