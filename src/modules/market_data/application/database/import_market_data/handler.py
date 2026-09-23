from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.import_market_data.command import (
    ImportMarketDataCommand,
    ImportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.domain.csv_kline_parser import (
    parse_csv_klines,
)

logger = logging.getLogger("App.Database")


class ImportMarketDataCommandHandler(
    ICommandHandler[ImportMarketDataCommand, ImportMarketDataResult]
):
    """
    @brief Reads an external candle CSV and upserts it into the vault.
    @details `IMarketDataRepository.save_klines()` already upserts on
    `(symbol, interval, open_time)` (SQLite `ON CONFLICT DO UPDATE`,
    `sqlalchemy_repository.py`) — re-importing a file that overlaps data
    already stored safely overwrites just the overlapping candles, never
    duplicates them. This handler does not need its own dedup pass.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, command: ImportMarketDataCommand) -> ImportMarketDataResult:
        try:
            with open(command.source_path, encoding="utf-8-sig") as csv_file:
                csv_text = csv_file.read()
        except OSError as exc:
            err_msg = f"Could not read {command.source_path}: {exc}"
            logger.error(err_msg)
            return ImportMarketDataResult(
                imported_records=0, success=False, message=err_msg
            )

        parsed = parse_csv_klines(csv_text, command.symbol, command.interval)
        if not parsed.klines:
            msg = "No valid candles found in file." + (
                f" First issue: {parsed.warnings[0]}" if parsed.warnings else ""
            )
            logger.warning(msg)
            return ImportMarketDataResult(
                imported_records=0,
                success=False,
                message=msg,
                warnings=parsed.warnings,
            )

        try:
            self._repository.save_klines(parsed.klines)
        except Exception as exc:  # noqa: BLE001 - boundary: wrap exception in result
            err_msg = f"Error while saving imported candles: {exc}"
            logger.error(err_msg)
            return ImportMarketDataResult(
                imported_records=0,
                success=False,
                message=err_msg,
                warnings=parsed.warnings,
            )

        msg = (
            f"Imported {len(parsed.klines):,} candles for {command.symbol} "
            f"({command.interval.value}) from {command.source_path}."
        )
        if parsed.warnings:
            msg += f" {len(parsed.warnings)} row(s) skipped."
        logger.info(msg)
        return ImportMarketDataResult(
            imported_records=len(parsed.klines),
            success=True,
            message=msg,
            warnings=parsed.warnings,
        )
