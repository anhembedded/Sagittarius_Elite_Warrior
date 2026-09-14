from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.clear_market_data.command import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)

logger = logging.getLogger("App.Database")


class ClearMarketDataCommandHandler(
    ICommandHandler[ClearMarketDataCommand, ClearMarketDataResult]
):
    """
    @brief Handler executing data deletion or database purging via IMarketDataRepository.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, command: ClearMarketDataCommand) -> ClearMarketDataResult:
        try:
            if command.purge_all:
                count = self._repository.purge_all()
                msg = f"Purged the entire database ({count} database shards)."
                logger.info(msg)
                return ClearMarketDataResult(
                    deleted_records=count, success=True, message=msg
                )

            if not command.symbol.strip():
                return ClearMarketDataResult(
                    deleted_records=0,
                    success=False,
                    message="Symbol cannot be empty.",
                )

            count = self._repository.clear_klines(
                symbol=command.symbol.strip(), interval=command.interval
            )
            interval_label = (
                f" ({command.interval.value})" if command.interval is not None else ""
            )
            msg = f"Successfully deleted {count:,} candles for {command.symbol.strip()}{interval_label}."
            logger.info(msg)
            return ClearMarketDataResult(
                deleted_records=count, success=True, message=msg
            )
        except Exception as exc:  # noqa: BLE001 - boundary: wrap exception in result
            err_msg = f"Error while clearing data: {exc}"
            logger.error(err_msg)
            return ClearMarketDataResult(
                deleted_records=0, success=False, message=err_msg
            )
