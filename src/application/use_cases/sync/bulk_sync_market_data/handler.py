import concurrent.futures
import logging
import threading
import time

from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .command import BulkSyncMarketDataCommand


class BulkSyncMarketDataCommandHandler(
    ICommandHandler[BulkSyncMarketDataCommand, None]
):
    """
    @brief Handler for BulkSyncMarketDataCommand. Orchestrates bulk sync sequentially.
    @details Depends on IDispatcher rather than the concrete SyncMarketDataCommandHandler
    (Dependency Inversion) — dispatches SyncMarketDataCommand the same way the
    Presenter layer already does, instead of holding a direct reference to another
    use case's handler.
    """

    def __init__(
        self,
        event_bus: IEventBus,
        config: IConfig,
        dispatcher: IDispatcher,
    ) -> None:
        self.event_bus = event_bus
        self.config = config
        self.dispatcher = dispatcher
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
            f"Starting concurrent bulk sync for {total} targets with a {delay_ms}ms start delay."
        )

        completed_count = 0

        def _sync_target(symbol: str, interval: str) -> tuple[str, str, bool, str]:
            """Helper function to execute the sync in a thread."""
            try:
                # Dispatch the single sync command
                sync_cmd = SyncMarketDataCommand(
                    symbols=[symbol],
                    interval=TimeFrame(interval),
                    start_time=None,
                    end_time=None,
                )
                self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)
                return symbol, interval, False, ""
            except Exception as e:  # noqa: BLE001 - boundary: report per-symbol sync failure without aborting the batch
                self.logger.error(f"Error syncing {symbol} ({interval}): {e}")
                return symbol, interval, True, str(e)

        # Global state for rate limiting inside worker threads
        last_dispatch_time = [0.0]
        rate_limit_lock = threading.Lock()

        def _sync_target_with_rate_limit(
            symbol: str, interval: str
        ) -> tuple[str, str, bool, str]:
            """Helper function to execute the sync in a thread, respecting global rate limit."""
            with rate_limit_lock:
                now = time.time()
                elapsed = now - last_dispatch_time[0]
                if elapsed < delay_sec:
                    time.sleep(delay_sec - elapsed)
                last_dispatch_time[0] = time.time()

            return _sync_target(symbol, interval)

        max_workers = max(1, min(10, total))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, (symbol, interval) in enumerate(targets):
                self.logger.info(
                    f"[{idx + 1}/{total}] Submitting {symbol} ({interval})..."
                )
                futures.append(
                    executor.submit(_sync_target_with_rate_limit, symbol, interval)
                )

            # Wait and report progress as they complete
            for future in concurrent.futures.as_completed(futures):
                symbol, interval, has_error, error_msg = future.result()

                completed_count += 1
                current_idx = completed_count

                if not has_error:
                    self.event_bus.emit(
                        BulkSyncProgressEvent(
                            current_index=current_idx,
                            total_targets=total,
                            symbol=symbol,
                            interval=interval,
                            message=f"[{current_idx}/{total}] {symbol} ({interval}) complete.",
                        )
                    )
                else:
                    self.event_bus.emit(
                        BulkSyncProgressEvent(
                            current_index=current_idx,
                            total_targets=total,
                            symbol=symbol,
                            interval=interval,
                            has_error=True,
                            message=f"Failed: {error_msg}",
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
