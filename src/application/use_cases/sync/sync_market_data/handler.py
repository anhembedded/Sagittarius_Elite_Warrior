import logging
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.in_flight_sync_guard import (
    InFlightSyncGuard,
)

from .command import SyncMarketDataCommand


class SyncMarketDataCommandHandler(ICommandHandler[SyncMarketDataCommand, None]):
    """
    @brief Handler for SyncMarketDataCommand.
    """

    def __init__(
        self,
        exchange_client: IExchangeClient,
        repo: IMarketDataRepository,
        event_publisher: IEventPublisher,
        in_flight_guard: InFlightSyncGuard,
    ) -> None:
        self.exchange_client = exchange_client
        self.repo = repo
        self.event_publisher = event_publisher
        self.in_flight_guard = in_flight_guard
        self.logger = logging.getLogger("App.SyncMarketData")

    def execute(self, command: SyncMarketDataCommand) -> None:
        """
        @brief Executes the synchronization.
        """
        self.logger.info(
            f"Starting sync for symbols: {command.symbols} at interval {command.interval.value}"
        )

        for symbol in command.symbols:
            if command.cancellation_requested and command.cancellation_requested():
                self.logger.info("Market data sync cancelled before %s.", symbol)
                return
            self._sync_single_symbol(symbol, command)

    def _sync_single_symbol(self, symbol: str, command: SyncMarketDataCommand) -> None:
        interval_key = command.interval.value
        # BOT-121: the single choke point every screen's sync dispatch passes
        # through (Backtest, Data Management single sync, Data Management
        # bulk sync via BulkSyncMarketDataCommandHandler dispatching per
        # target) — reserving here means two screens can never fetch the
        # same symbol+interval from the exchange concurrently.
        if not self.in_flight_guard.try_acquire(symbol, interval_key):
            self.logger.info(
                f"[{symbol}] Sync already in flight for {interval_key} "
                "elsewhere — skipping this request."
            )
            return
        try:
            self._sync_single_symbol_locked(symbol, command)
        finally:
            self.in_flight_guard.release(symbol, interval_key)

    def _sync_single_symbol_locked(
        self, symbol: str, command: SyncMarketDataCommand
    ) -> None:
        start_time = self._determine_start_time(symbol, command)
        total_klines = self._estimate_total_klines(start_time, command)

        def _progress_cb(
            current: int,
            *,
            current_symbol: str = symbol,
            total_count: int = total_klines,
        ) -> None:
            self.event_publisher.publish(
                SingleSyncProgressEvent(
                    symbol=current_symbol,
                    interval=command.interval.value,
                    current=current,
                    total=total_count,
                )
            )

        # BUG-025: consume the exchange stream chunk-by-chunk and persist
        # each chunk immediately, instead of accumulating the full requested
        # range into one list before a single save_klines() call — RAM usage
        # is now bounded by chunk size, not by how long the sync range is.
        synced_count = 0
        try:
            for chunk in self.exchange_client.stream_historical_klines(
                symbol,
                command.interval,
                start_time,
                command.end_time,
                _progress_cb,
                command.cancellation_requested,
            ):
                if command.cancellation_requested and command.cancellation_requested():
                    self.logger.info(
                        "[%s] Market data sync cancelled before save.", symbol
                    )
                    return
                self.repo.save_klines(chunk)
                synced_count += len(chunk)
                self.logger.debug(
                    "[%s] Persisted chunk of %d klines (%d total so far) — "
                    "streamed straight to DB, not held in RAM.",
                    symbol,
                    len(chunk),
                    synced_count,
                )
        except ExchangeRequestCancelledError:
            self.logger.info("[%s] Market data sync cancelled.", symbol)
            return

        if synced_count:
            self.logger.info(f"[{symbol}] Successfully synced {synced_count} klines.")
        else:
            self.logger.info(f"[{symbol}] Already up to date.")

    def _determine_start_time(
        self, symbol: str, command: SyncMarketDataCommand
    ) -> datetime:
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
        return start_time

    def _estimate_total_klines(
        self, start_time: datetime, command: SyncMarketDataCommand
    ) -> int:
        end_t = command.end_time or datetime.now(UTC)
        total_seconds = (end_t - start_time).total_seconds()

        interval_seconds = command.interval.to_seconds()
        total_klines = int(max(0, total_seconds) / interval_seconds)

        return max(total_klines, 1)
