from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.import_market_data import (
    ImportMarketDataCommand,
    ImportMarketDataCommandHandler,
)


def test_import_valid_csv_upserts_via_save_klines(tmp_path):
    source = tmp_path / "candles.csv"
    source.write_text(
        "open_time,open,high,low,close,volume\n"
        "1700000000,1,2,0.5,1.5,10\n"
        "1700000060,2,3,1.5,2.5,20\n",
        encoding="utf-8",
    )
    repo = Mock()
    handler = ImportMarketDataCommandHandler(repo)

    cmd = ImportMarketDataCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, source_path=str(source)
    )
    result = handler.execute(cmd)

    assert result.success is True
    assert result.imported_records == 2
    assert result.warnings == []
    repo.save_klines.assert_called_once()
    saved = repo.save_klines.call_args[0][0]
    assert len(saved) == 2
    assert all(kline.symbol == "BTCUSDT" for kline in saved)


def test_import_partially_malformed_file_reports_warnings_but_still_imports(tmp_path):
    source = tmp_path / "candles.csv"
    source.write_text(
        "open_time,open,high,low,close,volume\n"
        "1700000000,1,2,0.5,1.5,10\n"
        "not_a_number,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )
    repo = Mock()
    handler = ImportMarketDataCommandHandler(repo)

    cmd = ImportMarketDataCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, source_path=str(source)
    )
    result = handler.execute(cmd)

    assert result.success is True
    assert result.imported_records == 1
    assert len(result.warnings) == 1
    assert "Row 3" in result.warnings[0]


def test_import_file_with_no_valid_rows_fails_without_calling_save(tmp_path):
    source = tmp_path / "candles.csv"
    source.write_text("open,high,low,close\n1,2,0.5,1.5\n", encoding="utf-8")
    repo = Mock()
    handler = ImportMarketDataCommandHandler(repo)

    cmd = ImportMarketDataCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, source_path=str(source)
    )
    result = handler.execute(cmd)

    assert result.success is False
    assert result.imported_records == 0
    repo.save_klines.assert_not_called()


def test_import_missing_file_fails_gracefully():
    repo = Mock()
    handler = ImportMarketDataCommandHandler(repo)

    cmd = ImportMarketDataCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        source_path="/nonexistent/path/candles.csv",
    )
    result = handler.execute(cmd)

    assert result.success is False
    assert result.imported_records == 0
    repo.save_klines.assert_not_called()


def test_import_repository_failure_is_reported_never_raised(tmp_path):
    source = tmp_path / "candles.csv"
    source.write_text(
        "open_time,open,high,low,close,volume\n1700000000,1,2,0.5,1.5,10\n",
        encoding="utf-8",
    )
    repo = Mock()
    repo.save_klines.side_effect = RuntimeError("db locked")
    handler = ImportMarketDataCommandHandler(repo)

    cmd = ImportMarketDataCommand(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, source_path=str(source)
    )
    result = handler.execute(cmd)

    assert result.success is False
    assert result.imported_records == 0
    assert "db locked" in result.message
