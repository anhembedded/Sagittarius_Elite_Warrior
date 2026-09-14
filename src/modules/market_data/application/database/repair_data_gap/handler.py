from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)

from .command import RepairDataGapCommand, RepairDataGapResult

logger = logging.getLogger("App.SyncMarketData")


class RepairDataGapCommandHandler(
    ICommandHandler[RepairDataGapCommand, RepairDataGapResult]
):
    """
    @brief Handler for RepairDataGapCommand.
    @details Selectively downloads missing klines for a specific gap time window and saves to SQLite.
    """

    def __init__(
        self,
        exchange_client: IExchangeClient,
        repo: IMarketDataRepository,
    ) -> None:
        self.exchange_client = exchange_client
        self.repo = repo

    def execute(self, command: RepairDataGapCommand) -> RepairDataGapResult:
        if not command.symbol:
            return RepairDataGapResult(
                success=False,
                repaired_candles=0,
                message="Symbol cannot be empty.",
            )

        logger.info(
            f"Repairing data gap for {command.symbol} ({command.interval.value}) "
            f"from {command.start_time} to {command.end_time}"
        )

        try:
            klines = self.exchange_client.get_historical_klines(
                symbol=command.symbol,
                interval=command.interval,
                start_str=command.start_time,
                end_str=command.end_time,
                progress_callback=None,
                cancellation_requested=command.cancellation_requested,
            )
        except ExchangeRequestCancelledError:
            logger.info("Gap repair cancelled by user.")
            return RepairDataGapResult(
                success=False,
                repaired_candles=0,
                message="Gap repair was cancelled.",
            )
        except Exception as err:  # noqa: BLE001
            logger.error(f"Failed to fetch klines for gap repair: {err}")
            return RepairDataGapResult(
                success=False,
                repaired_candles=0,
                message=f"Error fetching data from the exchange: {err}",
            )

        if command.cancellation_requested and command.cancellation_requested():
            return RepairDataGapResult(
                success=False,
                repaired_candles=0,
                message="Gap repair was cancelled.",
            )

        if klines:
            self.repo.save_klines(klines)
            logger.info(
                f"Successfully repaired gap for {command.symbol}: saved {len(klines)} klines."
            )
            return RepairDataGapResult(
                success=True,
                repaired_candles=len(klines),
                message=(
                    f"Successfully repaired {len(klines)} candles for {command.symbol} "
                    f"({command.interval.value})."
                ),
            )

        return RepairDataGapResult(
            success=True,
            repaired_candles=0,
            message="No additional candles available from the exchange for this time range.",
        )
