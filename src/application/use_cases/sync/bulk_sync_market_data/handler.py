from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .command import BulkSyncMarketDataCommand

#: Default delay between concurrent target dispatches in milliseconds.
DEFAULT_RATE_LIMIT_DELAY_MS: int = 500
_MS_PER_SECOND: float = 1000.0
_MIN_BULK_SYNC_WORKERS: int = 1
_MAX_BULK_SYNC_WORKERS: int = 10


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
        @brief Executes the concurrent bulk synchronization process.
        """
        targets = command.targets
        total = len(targets)

        if total == 0:
            self._emit_empty_targets_event()
            return

        delay_sec = self._get_rate_limit_delay_seconds()
        self.logger.info(
            f"Starting concurrent bulk sync for {total} targets with a {delay_sec * _MS_PER_SECOND:.0f}ms start delay."
        )

        self._run_bulk_sync(targets=targets, delay_sec=delay_sec)
        self._emit_completion_event(total=total)

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
        self, symbol: str, interval: str
    ) -> tuple[str, str, bool, str]:
        """Dispatches a single sync command and catches any execution errors."""
        try:
            sync_cmd = SyncMarketDataCommand(
                symbols=[symbol],
                interval=TimeFrame(interval),
                start_time=None,
                end_time=None,
            )
            self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)
            return symbol, interval, False, ""
        except Exception as e:  # noqa: BLE001 - boundary: report per-symbol sync failure without aborting batch
            self.logger.error(f"Error syncing {symbol} ({interval}): {e}")
            return symbol, interval, True, str(e)

    def _sync_target_with_rate_limit(
        self,
        symbol: str,
        interval: str,
        delay_sec: float,
        rate_limit_lock: threading.Lock,
        last_dispatch_time: list[float],
    ) -> tuple[str, str, bool, str]:
        """Executes single target sync in a worker thread, respecting global rate limit delay."""
        with rate_limit_lock:
            now = time.time()
            elapsed = now - last_dispatch_time[0]
            if elapsed < delay_sec:
                time.sleep(delay_sec - elapsed)
            last_dispatch_time[0] = time.time()

        return self._sync_single_target(symbol, interval)

    def _run_bulk_sync(self, targets: list[tuple[str, str]], delay_sec: float) -> None:
        """Runs the thread pool execution and processes completion events."""
        total = len(targets)
        last_dispatch_time = [0.0]
        rate_limit_lock = threading.Lock()
        max_workers = self._calculate_max_workers(total)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    self._sync_target_with_rate_limit,
                    symbol,
                    interval,
                    delay_sec,
                    rate_limit_lock,
                    last_dispatch_time,
                )
                for idx, (symbol, interval) in enumerate(targets)
            ]

            for completed_count, future in enumerate(
                concurrent.futures.as_completed(futures), start=1
            ):
                symbol, interval, has_error, error_msg = future.result()
                self._emit_target_progress_event(
                    current_index=completed_count,
                    total_targets=total,
                    symbol=symbol,
                    interval=interval,
                    has_error=has_error,
                    error_msg=error_msg,
                )

    def _emit_target_progress_event(
        self,
        current_index: int,
        total_targets: int,
        symbol: str,
        interval: str,
        has_error: bool,
        error_msg: str,
    ) -> None:
        """Emits progress event for an individual target."""
        message = (
            f"[{current_index}/{total_targets}] {symbol} ({interval}) complete."
            if not has_error
            else f"Failed: {error_msg}"
        )
        self.event_bus.emit(
            BulkSyncProgressEvent(
                current_index=current_index,
                total_targets=total_targets,
                symbol=symbol,
                interval=interval,
                has_error=has_error,
                message=message,
            )
        )

    def _emit_empty_targets_event(self) -> None:
        """Emits an immediate completion event when target list is empty."""
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

    def _emit_completion_event(self, total: int) -> None:
        """Emits the final completion event for the entire batch."""
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
