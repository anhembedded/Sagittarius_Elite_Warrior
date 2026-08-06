import time
import logging
from Binace_Bot.src.application.ports.i_cqrs import ICommandHandler
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from .command import BulkSyncMarketDataCommand
from Binace_Bot.src.application.events.bulk_sync_events import BulkSyncProgressEvent
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.handler import (
    SyncMarketDataCommandHandler,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.config.config_keys import ConfigKeys


class BulkSyncMarketDataCommandHandler(
    ICommandHandler[BulkSyncMarketDataCommand, None]
):
    """
    @brief Handler for BulkSyncMarketDataCommand. Orchestrates bulk sync sequentially.
    """

    def __init__(
        self,
        event_bus: IEventBus,
        config: IConfig,
        sync_handler: SyncMarketDataCommandHandler,
    ) -> None:
        self.event_bus = event_bus
        self.config = config
        self.sync_handler = sync_handler
        self.logger = logging.getLogger("App.BulkSync")

    def execute(self, command: BulkSyncMarketDataCommand) -> None:
        """
        @brief Executes the sequential bulk synchronization loop.
        """
        targets = command.targets
        total = len(targets)

        if total == 0:
            self.logger.info("No targets provided for bulk sync.")
            self.event_bus.emit(
                BulkSyncProgressEvent(
                    current_index=0,
                    total_targets=0,
                    symbol="",
                    interval="",
                    is_complete=True,
                    message="No targets to sync.",
                )
            )
            return

        delay_ms = self.config.get(ConfigKeys.BINANCE_RATE_LIMIT_DELAY_MS.value, 500)
        delay_sec = delay_ms / 1000.0

        self.logger.info(
            f"Starting sequential bulk sync for {total} targets with a {delay_ms}ms delay."
        )

        for idx, (symbol, interval) in enumerate(targets):
            self.logger.info(f"[{idx + 1}/{total}] Syncing {symbol} ({interval})...")

            try:
                # Dispatch the single sync command
                sync_cmd = SyncMarketDataCommand(
                    symbols=[symbol],
                    interval=TimeFrame(interval),
                    start_time=None,
                    end_time=None,
                )
                self.sync_handler.execute(sync_cmd)

                # Emit progress event
                self.event_bus.emit(
                    BulkSyncProgressEvent(
                        current_index=idx + 1,
                        total_targets=total,
                        symbol=symbol,
                        interval=interval,
                        message=f"[{idx + 1}/{total}] {symbol} ({interval}) complete.",
                    )
                )

                # Rate Limiting
                if idx < total - 1:
                    time.sleep(delay_sec)

            except Exception as e:
                self.logger.error(f"Error syncing {symbol} ({interval}): {e}")
                self.event_bus.emit(
                    BulkSyncProgressEvent(
                        current_index=idx + 1,
                        total_targets=total,
                        symbol=symbol,
                        interval=interval,
                        has_error=True,
                        message=f"Failed: {str(e)}",
                    )
                )

        self.logger.info("Bulk sync completed.")
        self.event_bus.emit(
            BulkSyncProgressEvent(
                current_index=total,
                total_targets=total,
                symbol="",
                interval="",
                is_complete=True,
                message="Bulk sync completed successfully.",
            )
        )
