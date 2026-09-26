from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pyarrow.parquet as pq
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.export_market_data import (
    ExportMarketDataCommand,
    ExportMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)


def _make_kline(open_price: float) -> MarketData:
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open_price=open_price,
        high_price=open_price + 1,
        low_price=open_price - 1,
        close_price=open_price + 0.5,
        volume=10.0,
        close_time=datetime(2026, 1, 1, 0, 0, 59, 999000, tzinfo=UTC),
        quote_asset_volume=100.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=1.0,
        taker_buy_quote_asset_volume=2.0,
    )


def test_export_csv_writes_header_and_every_row(tmp_path):
    repo = Mock()
    repo.stream_klines.return_value = iter([_make_kline(100.0), _make_kline(101.0)])
    handler = ExportMarketDataCommandHandler(repo)
    destination = tmp_path / "out.csv"

    cmd = ExportMarketDataCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        market=MarketType.SPOT,
        destination_path=str(destination),
        file_format=ExportFileFormat.CSV,
    )
    result = handler.execute(cmd)

    assert result.success is True
    assert result.exported_records == 2
    with open(destination, newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 2
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["market"] == "spot"
    assert float(rows[0]["open_price"]) == 100.0
    repo.stream_klines.assert_called_once_with(
        market=MarketType.SPOT,
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        start_time=None,
        end_time=None,
    )


def test_export_json_writes_a_streamed_array(tmp_path):
    repo = Mock()
    repo.stream_klines.return_value = iter([_make_kline(50.0)])
    handler = ExportMarketDataCommandHandler(repo)
    destination = tmp_path / "out.json"

    cmd = ExportMarketDataCommand(
        symbol="ETHUSDT",
        interval=TimeFrame.ONE_HOUR,
        market=MarketType.SPOT,
        destination_path=str(destination),
        file_format=ExportFileFormat.JSON,
    )
    result = handler.execute(cmd)

    assert result.success is True
    assert result.exported_records == 1
    rows = json.loads(destination.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    assert rows[0]["open_price"] == 50.0
    assert rows[0]["number_of_trades"] == 5
    assert rows[0]["market"] == "spot"


def test_export_parquet_round_trips_through_pyarrow(tmp_path):
    repo = Mock()
    repo.stream_klines.return_value = iter([_make_kline(10.0), _make_kline(20.0)])
    handler = ExportMarketDataCommandHandler(repo)
    destination = tmp_path / "out.parquet"

    cmd = ExportMarketDataCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        market=MarketType.SPOT,
        destination_path=str(destination),
        file_format=ExportFileFormat.PARQUET,
    )
    result = handler.execute(cmd)

    assert result.success is True
    assert result.exported_records == 2
    table = pq.read_table(destination)
    assert table.num_rows == 2
    assert table.column("open_price").to_pylist() == [10.0, 20.0]
    assert table.column("market").to_pylist() == ["spot", "spot"]


def test_export_failure_is_reported_never_raised(tmp_path):
    repo = Mock()
    repo.stream_klines.side_effect = RuntimeError("disk unavailable")
    handler = ExportMarketDataCommandHandler(repo)

    cmd = ExportMarketDataCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        market=MarketType.SPOT,
        destination_path=str(tmp_path / "out.csv"),
        file_format=ExportFileFormat.CSV,
    )
    result = handler.execute(cmd)

    assert result.success is False
    assert result.exported_records == 0
    assert "disk unavailable" in result.message
