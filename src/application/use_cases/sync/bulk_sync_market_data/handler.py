from __future__ import annotations

import concurrent.futures
import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.services.rate_limiter import (
    ThreadSafeRateLimiter,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys

from .command import BulkSyncMarketDataCommand, CancellationCheck
from .progress_reporter import BulkSyncProgressReporter
from .sync_target import SyncTarget

#: Default delay between concurrent target dispatches in milliseconds.
DEFAULT_RATE_LIMIT_DELAY_MS: int = 500
_MS_PER_SECOND: float = 1000.0
_MIN_BULK_SYNC_WORKERS: int = 1
_MAX_BULK_SYNC_WORKERS: int = 10


class BulkSyncMarketDataCommandHandler(
    ICommandHandler[BulkSyncMarketDataCommand, None]
):
    """
    @brief Handler for BulkSyncMarketDataCommand. Orchestrates bulk sync concurrently.
    @details Depends on ICommandDispatcher rather than the concrete SyncMarketDataCommandHandler
    (Dependency Inversion) — dispatches SyncMarketDataCommand the same way the
    Presenter layer already does, instead of holding a direct reference to another
    use case's handler.
    """

    def __init__(
        self,
        event_publisher: IEventPublisher,
        config: IConfigReader,
        dispatcher: ICommandDispatcher,
    ) -> None:
        self.event_publisher = event_publisher
        self.config = config
        self.dispatcher = dispatcher
        self.logger = logging.getLogger("App.BulkSync")

    def execute(self, command: BulkSyncMarketDataCommand) -> None:
        """
        @brief Executes the concurrent bulk synchronization process.
        """
        targets = command.targets
        total = len(targets)
        reporter = BulkSyncProgressReporter(self.event_publisher, total_targets=total)

        if self._handle_empty_targets(total, reporter):
            return

        delay_sec = self._get_rate_limit_delay_seconds()
        self.logger.info(
            f"Starting concurrent bulk sync for {total} targets with a {delay_sec * _MS_PER_SECOND:.0f}ms start delay."
        )

        rate_limiter = ThreadSafeRateLimiter(delay_sec=delay_sec)
        self._run_bulk_sync(
            targets=targets,
            rate_limiter=rate_limiter,
            reporter=reporter,
            cancellation_requested=command.cancellation_requested,
            correlation_id=command.correlation_id,
        )

        self.logger.info("Bulk sync completed.")
        reporter.report_completed()

    def _handle_empty_targets(
        self, total: int, reporter: BulkSyncProgressReporter
    ) -> bool:
        """Helper to handle the case where no targets are provided."""
        if total == 0:
            self.logger.info("No targets provided for bulk sync.")
            reporter.report_empty()
            return True
        return False

    def _get_rate_limit_delay_seconds(self) -> float:
        """Reads the rate limit delay configuration in seconds."""
        raw_delay = self.config.get(
            ConfigKeys.BINANCE_RATE_LIMIT_DELAY_MS.value,
            DEFAULT_RATE_LIMIT_DELAY_MS,
        )
        try:
            delay_ms = (
                float(raw_delay)
                if not isinstance(raw_delay, bool)
                else float(DEFAULT_RATE_LIMIT_DELAY_MS)
            )
        except (ValueError, TypeError):
            delay_ms = float(DEFAULT_RATE_LIMIT_DELAY_MS)

        return delay_ms / _MS_PER_SECOND

    @staticmethod
    def _calculate_max_workers(total_targets: int) -> int:
        """Calculates bounded worker thread count based on target count."""
        return max(
            _MIN_BULK_SYNC_WORKERS,
            min(_MAX_BULK_SYNC_WORKERS, total_targets),
        )

    def _sync_single_target(
        self,
        target: SyncTarget,
        rate_limiter: ThreadSafeRateLimiter,
        cancellation_requested: CancellationCheck | None = None,
        correlation_id: str = "",
    ) -> tuple[str, str, bool, str]:
        """Dispatches a single sync command with rate limiting and catches any execution errors."""
        symbol, interval = target.symbol, target.interval.value
        if cancellation_requested and cancellation_requested():
            return symbol, interval, False, "Cancelled"
        rate_limiter.acquire(cancellation_requested=cancellation_requested)
        if cancellation_requested and cancellation_requested():
            return symbol, interval, False, "Cancelled"
        try:
            sync_cmd = SyncMarketDataCommand(
                symbols=[symbol],
                interval=target.interval,
                start_time=None,
                end_time=None,
                cancellation_requested=cancellation_requested,
                # BOT-122: every target in this batch reports progress under
                # the SAME id — the batch is one action, not N.
                correlation_id=correlation_id,
            )
            self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)
            return symbol, interval, False, ""
        except Exception as e:  # noqa: BLE001 - boundary: report per-symbol sync failure without aborting batch
            self.logger.error(f"Error syncing {symbol} ({interval}): {e}")
            return symbol, interval, True, str(e)

    def _run_bulk_sync(
        self,
        targets: list[SyncTarget],
        rate_limiter: ThreadSafeRateLimiter,
        reporter: BulkSyncProgressReporter,
        cancellation_requested: CancellationCheck | None = None,
        correlation_id: str = "",
    ) -> None:
        """Runs the thread pool execution and reports completion events via reporter."""
        max_workers = self._calculate_max_workers(len(targets))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    self._sync_single_target,
                    target,
                    rate_limiter,
                    cancellation_requested,
                    correlation_id,
                )
                for target in targets
            ]

            for future in concurrent.futures.as_completed(futures):
                if cancellation_requested and cancellation_requested():
                    for f in futures:
                        f.cancel()
                if future.cancelled():
                    continue
                try:
                    symbol, interval, has_error, error_msg = future.result()
                    reporter.report_target(
                        symbol=symbol,
                        interval=interval,
                        has_error=has_error,
                        error_msg=error_msg,
                    )
                except concurrent.futures.CancelledError:
                    continue
