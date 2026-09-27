from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterator
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.export_market_data.command import (
    ExportMarketDataCommand,
    ExportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)

logger = logging.getLogger("App.Database")

#: Column order every export format writes, in `MarketData`'s own field order
#: (symbol/interval carried once per row rather than once per file — the file
#: itself may later be concatenated with others, e.g. multiple symbols).
_COLUMNS = (
    "symbol",
    "interval",
    "market",
    "open_time",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
)

#: How many rows accumulate before one Parquet `write_table()` call — bounds
#: memory the same way `IMarketDataRepository.stream_klines()` already bounds
#: the read side (`BUG-025`), rather than materializing all 500k+ rows twice.
_PARQUET_BATCH_SIZE = 20_000


def _kline_to_row(kline: MarketData, market: MarketType) -> dict[str, Any]:
    return {
        "symbol": kline.symbol,
        "interval": kline.interval,
        "market": market.value,
        "open_time": kline.open_time.isoformat(),
        "open_price": kline.open_price,
        "high_price": kline.high_price,
        "low_price": kline.low_price,
        "close_price": kline.close_price,
        "volume": kline.volume,
        "close_time": kline.close_time.isoformat(),
        "quote_asset_volume": kline.quote_asset_volume,
        "number_of_trades": kline.number_of_trades,
        "taker_buy_base_asset_volume": kline.taker_buy_base_asset_volume,
        "taker_buy_quote_asset_volume": kline.taker_buy_quote_asset_volume,
    }


class ExportMarketDataCommandHandler(
    ICommandHandler[ExportMarketDataCommand, ExportMarketDataResult]
):
    """
    @brief Streams stored klines straight to a `.csv`/`.parquet`/`.json` file
    on disk, one symbol/interval at a time.
    @details Reads via `IMarketDataRepository.stream_klines()` (`BUG-025`'s
    bounded-memory contract), never `get_klines()` — a 500k-candle export
    must not materialize the whole range as a Python list before writing a
    single byte.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, command: ExportMarketDataCommand) -> ExportMarketDataResult:
        try:
            klines = self._repository.stream_klines(
                market=command.market,
                symbol=command.symbol,
                interval=command.interval,
                start_time=command.start_time,
                end_time=command.end_time,
            )
            writer = {
                ExportFileFormat.CSV: self._write_csv,
                ExportFileFormat.JSON: self._write_json,
                ExportFileFormat.PARQUET: self._write_parquet,
            }[command.file_format]
            count = writer(klines, command.destination_path, command.market)
            msg = (
                f"Exported {count:,} candles for {command.symbol} "
                f"({command.interval.value}) to {command.destination_path}."
            )
            logger.info(msg)
            return ExportMarketDataResult(
                exported_records=count, success=True, message=msg
            )
        except Exception as exc:  # noqa: BLE001 - boundary: wrap exception in result
            err_msg = f"Error while exporting data: {exc}"
            logger.error(err_msg)
            return ExportMarketDataResult(
                exported_records=0, success=False, message=err_msg
            )

    @staticmethod
    def _write_csv(klines: Iterator[MarketData], path: str, market: MarketType) -> int:
        count = 0
        with open(path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=_COLUMNS)
            writer.writeheader()
            for kline in klines:
                writer.writerow(_kline_to_row(kline, market))
                count += 1
        return count

    @staticmethod
    def _write_json(klines: Iterator[MarketData], path: str, market: MarketType) -> int:
        """Streams a JSON array by hand (`[row,row,...]`) rather than
        `json.dump(list(...))` — a 500k-row list held twice (once as
        `MarketData`, once as dicts) before writing a single byte is exactly
        the materialization `stream_klines()` exists to avoid."""
        count = 0
        with open(path, "w", encoding="utf-8") as json_file:
            json_file.write("[")
            for kline in klines:
                if count:
                    json_file.write(",")
                json_file.write(json.dumps(_kline_to_row(kline, market)))
                count += 1
            json_file.write("]")
        return count

    @staticmethod
    def _write_parquet(
        klines: Iterator[MarketData], path: str, market: MarketType
    ) -> int:
        count = 0
        batch: list[dict[str, Any]] = []
        schema = pa.schema(
            [
                ("symbol", pa.string()),
                ("interval", pa.string()),
                ("market", pa.string()),
                ("open_time", pa.string()),
                ("open_price", pa.float64()),
                ("high_price", pa.float64()),
                ("low_price", pa.float64()),
                ("close_price", pa.float64()),
                ("volume", pa.float64()),
                ("close_time", pa.string()),
                ("quote_asset_volume", pa.float64()),
                ("number_of_trades", pa.int64()),
                ("taker_buy_base_asset_volume", pa.float64()),
                ("taker_buy_quote_asset_volume", pa.float64()),
            ]
        )
        with pq.ParquetWriter(path, schema) as parquet_writer:
            for kline in klines:
                batch.append(_kline_to_row(kline, market))
                count += 1
                if len(batch) >= _PARQUET_BATCH_SIZE:
                    parquet_writer.write_table(
                        pa.Table.from_pylist(batch, schema=schema)
                    )
                    batch = []
            if batch:
                parquet_writer.write_table(pa.Table.from_pylist(batch, schema=schema))
        return count
