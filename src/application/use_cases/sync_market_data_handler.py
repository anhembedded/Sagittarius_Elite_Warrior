import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sagittarius_engine.interfaces import ILogger
from sagittarius_engine.extensions.cqrs import ICommand
from Binace_Bot.src.application.use_cases.sync_market_data import SyncMarketDataCommand
from Binace_Bot.src.application.interfaces.i_exchange_client import IExchangeClient
from Binace_Bot.src.application.interfaces.i_market_data_repository import (
    IMarketDataRepository,
)


class SyncMarketDataCommandHandler(ICommand[SyncMarketDataCommand, None]):
    """
    @brief Handler for SyncMarketDataCommand.
    """

    def __init__(
        self,
        exchange_client: IExchangeClient,
        repo: IMarketDataRepository,
        logger: Optional[ILogger] = None,
    ) -> None:
        self.exchange_client = exchange_client
        self.repo = repo
        self.logger = logger or logging.getLogger("App.SyncMarketData")

    def execute(self, command: SyncMarketDataCommand) -> None:
        """
        @brief Executes the synchronization.
        """
        self.logger.info(
            f"Starting sync for symbols: {command.symbols} at interval {command.interval.value}"
        )

        for symbol in command.symbols:
            latest_time = self.repo.get_latest_kline_time(symbol, command.interval)

            if latest_time is None:
                # If no data, fetch from N days ago
                start_time = datetime.now(timezone.utc) - timedelta(
                    days=command.days_back_if_empty
                )
                self.logger.info(
                    f"[{symbol}] No existing data found. Syncing from {command.days_back_if_empty} days ago: {start_time}"
                )
            else:
                # Fetch from the latest timestamp we have
                start_time = latest_time
                self.logger.info(
                    f"[{symbol}] Syncing from latest timestamp: {start_time}"
                )

            klines = self.exchange_client.get_historical_klines(
                symbol, command.interval, start_time
            )

            if klines:
                self.repo.save_klines(klines)
                self.logger.info(
                    f"[{symbol}] Successfully synced {len(klines)} klines."
                )
            else:
                self.logger.info(f"[{symbol}] Already up to date.")
