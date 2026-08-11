import logging
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)

from .command import SyncMarketDataCommand


class SyncMarketDataCommandHandler(ICommandHandler[SyncMarketDataCommand, None]):
    """
    @brief Handler for SyncMarketDataCommand.
    """

    def __init__(
        self, exchange_client: IExchangeClient, repo: IMarketDataRepository
    ) -> None:
        self.exchange_client = exchange_client
        self.repo = repo
        self.logger = logging.getLogger("App.SyncMarketData")

    def execute(self, command: SyncMarketDataCommand) -> None:
        """
        @brief Executes the synchronization.
        """
        self.logger.info(
            f"Starting sync for symbols: {command.symbols} at interval {command.interval.value}"
        )

        for symbol in command.symbols:
            if command.start_time:
                start_time = command.start_time
                self.logger.info(
                    f"[{symbol}] Syncing from explicit start time: {start_time}"
                )
            else:
                latest_time = self.repo.get_latest_kline_time(symbol, command.interval)
                if latest_time is None:
                    start_time = datetime.now(UTC) - timedelta(
                        days=command.days_back_if_empty
                    )
                    self.logger.info(
                        f"[{symbol}] No existing data found. Syncing from {command.days_back_if_empty} days ago: {start_time}"
                    )
                else:
                    start_time = latest_time
                    self.logger.info(
                        f"[{symbol}] Syncing from latest timestamp: {start_time}"
                    )

            klines = self.exchange_client.get_historical_klines(
                symbol, command.interval, start_time, command.end_time
            )

            if klines:
                self.repo.save_klines(klines)
                self.logger.info(
                    f"[{symbol}] Successfully synced {len(klines)} klines."
                )
            else:
                self.logger.info(f"[{symbol}] Already up to date.")
