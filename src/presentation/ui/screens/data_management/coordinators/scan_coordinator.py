import logging
from collections.abc import Callable
from threading import Lock

from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators.action_kinds import (
    DataManagementActionKind,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_signal_payloads import (
    StatusRowUpdate,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.DataManagement")


class ScanCoordinator:
    """Coordinates database scanning, auto-discovery, clearing, purging, and VACUUM compaction."""

    def __init__(
        self,
        view_model: DataManagementViewModel,
        dispatcher: IDispatcher,
        thread_manager: IThreadManager,
        tracker: ActionOwnershipTracker[DataManagementActionKind, object, UIMode],
        market_data_repo: IMarketDataRepository,
        ui_log_signal: Callable[[str], None],
        ui_error_log_signal: Callable[[str], None],
        ui_status_table_signal: Callable[[StatusRowUpdate], None],
        ui_remove_symbol_signal: Callable[[str, str], None],
        ui_clear_table_signal: Callable[[], None],
        ui_stats_refresh_signal: Callable[[], None],
        ui_unlock_signal: Callable[[], None],
        ui_symbol_options_signal: Callable[[list[str]], None],
        transition_fsm: Callable[[UIMode], bool],
        get_current_fsm_state: Callable[[], UIMode],
    ) -> None:
        self._view_model = view_model
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._tracker = tracker
        self._market_data_repo = market_data_repo

        self._ui_log_signal = ui_log_signal
        self._ui_error_log_signal = ui_error_log_signal
        self._ui_status_table_signal = ui_status_table_signal
        self._ui_remove_symbol_signal = ui_remove_symbol_signal
        self._ui_clear_table_signal = ui_clear_table_signal
        self._ui_stats_refresh_signal = ui_stats_refresh_signal
        self._ui_unlock_signal = ui_unlock_signal
        self._ui_symbol_options_signal = ui_symbol_options_signal
        self._transition_fsm = transition_fsm
        self._get_current_fsm_state = get_current_fsm_state
        self._cancellation_lock = Lock()
        self._cancellation_tokens: set[CancellationToken] = set()

    def create_cancellation_token(self) -> CancellationToken:
        """Create and register a token before a scan is submitted to the pool."""
        token = CancellationToken()
        with self._cancellation_lock:
            self._cancellation_tokens.add(token)
        return token

    def cancel(self) -> None:
        """Idempotently cancel every queued or active database scan."""
        with self._cancellation_lock:
            tokens = tuple(self._cancellation_tokens)
        for token in tokens:
            token.cancel()

    def _release_cancellation_token(self, token: CancellationToken) -> None:
        with self._cancellation_lock:
            self._cancellation_tokens.discard(token)

    def run_auto_discover(
        self, cancellation_token: CancellationToken | None = None
    ) -> None:
        """Background worker: Scans all existing SQLite shards on disk and populates the table."""
        token = cancellation_token or self.create_cancellation_token()
        action = self._tracker.begin_action(
            DataManagementActionKind.AUTO_DISCOVER,
            None,
            self._get_current_fsm_state(),
        )
        try:
            try:
                available_symbols: list[str] = self._dispatcher.dispatch(
                    ListAvailableSymbolsQuery, ListAvailableSymbolsQuery()
                )
                if available_symbols and self._tracker.is_current_pending(
                    action.action_id, DataManagementActionKind.AUTO_DISCOVER
                ):
                    self._ui_symbol_options_signal(available_symbols)
            except Exception as err:  # noqa: BLE001
                logging.getLogger("App.Presenter").debug(
                    f"Exchange symbols not available at auto-discover: {err}"
                )

            query = ScanAllDatabasesQuery(
                symbols=[],
                intervals=[],
                cancellation_requested=token.is_cancelled,
            )
            results: list[DatabaseStatusDTO] = self._dispatcher.dispatch(
                ScanAllDatabasesQuery, query
            )

            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.AUTO_DISCOVER
            ):
                self._tracker.log_stale_callback(
                    "auto_discover",
                    action.action_id,
                    DataManagementActionKind.AUTO_DISCOVER,
                )
                return

            for item in results:
                self._ui_status_table_signal(
                    StatusRowUpdate(
                        symbol=item.symbol,
                        first_record=item.first_record,
                        last_record=item.last_record,
                        total_candles=item.total_candles,
                        status_text=item.status_text,
                        interval=item.interval,
                    )
                )

            if results:
                logger.info(
                    f"[storage-vault] Auto-discovered {len(results)} active database tables."
                )
                self._ui_log_signal(
                    f"Auto-discovered {len(results)} active database tables."
                )
            else:
                logger.info(
                    "[storage-vault] Storage Vault is empty: 0 database shards found on disk."
                )
                self._ui_log_signal(
                    "Storage Vault trống (chưa có cơ sở dữ liệu cục bộ). Hãy chọn cặp giao dịch và nhấn Sync để tải dữ liệu."
                )
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001 - boundary: log without crashing
            logger.error(f"[storage-vault] Auto-discovery error: {exc}")
            self._ui_log_signal(f"Storage Vault auto-discovery complete: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._release_cancellation_token(token)
            self._ui_stats_refresh_signal()

    def run_check_status(self, symbol: str, interval: str) -> None:
        """Background worker: dispatches GetDatabaseStatusQuery."""
        action = self._tracker.begin_action(
            DataManagementActionKind.SCAN_STATUS,
            {"symbol": symbol, "interval": interval},
            self._get_current_fsm_state(),
        )
        try:
            query = GetDatabaseStatusQuery(symbol=symbol, interval=interval)
            response = self._dispatcher.dispatch(GetDatabaseStatusQuery, query)
            status: DatabaseStatusDTO | None = (
                getattr(response, "data", response) if response else None
            )

            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.SCAN_STATUS
            ):
                self._tracker.log_stale_callback(
                    "check_status",
                    action.action_id,
                    DataManagementActionKind.SCAN_STATUS,
                )
                return

            if status is None:
                self._ui_log_signal("No status data returned.")
                self._tracker.finish_action(action.action_id, ActionOutcome.EMPTY)
                return

            self._ui_status_table_signal(
                StatusRowUpdate(
                    symbol=symbol,
                    first_record=status.first_record,
                    last_record=status.last_record,
                    total_candles=status.total_candles,
                    status_text=status.status_text,
                    interval=interval,
                )
            )
            self._ui_log_signal("Scan complete.")
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Error scanning database: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._ui_unlock_signal()

    def run_scan_all(
        self,
        symbols: list[str],
        intervals: list[str],
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: dispatches ScanAllDatabasesQuery."""
        token = cancellation_token or self.create_cancellation_token()
        action = self._tracker.begin_action(
            DataManagementActionKind.SCAN_ALL,
            {"symbols": symbols, "intervals": intervals},
            self._get_current_fsm_state(),
        )
        try:
            query = ScanAllDatabasesQuery(
                symbols=symbols,
                intervals=intervals,
                cancellation_requested=token.is_cancelled,
            )
            results: list[DatabaseStatusDTO] = self._dispatcher.dispatch(
                ScanAllDatabasesQuery, query
            )

            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.SCAN_ALL
            ):
                self._tracker.log_stale_callback(
                    "scan_all", action.action_id, DataManagementActionKind.SCAN_ALL
                )
                return

            for item in results:
                self._ui_status_table_signal(
                    StatusRowUpdate(
                        symbol=item.symbol,
                        first_record=item.first_record,
                        last_record=item.last_record,
                        total_candles=item.total_candles,
                        status_text=item.status_text,
                        interval=item.interval,
                    )
                )

            if results:
                logger.info(
                    f"[storage-vault] Full scan complete: {len(results)} active database tables."
                )
                self._ui_log_signal(
                    f"Full scan complete. Found {len(results)} active database tables."
                )
            else:
                logger.info(
                    "[storage-vault] Full scan complete: 0 database tables found."
                )
                self._ui_log_signal(
                    "Full scan complete. No database tables found in Storage Vault."
                )
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Error scanning databases: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._release_cancellation_token(token)
            self._ui_unlock_signal()

    def run_clear_data(self, symbol: str, interval: str) -> None:
        """Background worker: dispatches ClearMarketDataCommand."""
        action = self._tracker.begin_action(
            DataManagementActionKind.CLEAR_DATA,
            {"symbol": symbol, "interval": interval},
            self._get_current_fsm_state(),
        )
        try:
            interval_vo = TimeFrame(interval) if interval else None
            cmd = ClearMarketDataCommand(symbol=symbol, interval=interval_vo)
            result: ClearMarketDataResult = self._dispatcher.dispatch(
                ClearMarketDataCommand, cmd
            )
            if self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.CLEAR_DATA
            ):
                if result.success:
                    self._ui_log_signal(result.message)
                    self._ui_remove_symbol_signal(symbol, interval)
                    self._tracker.finish_action(
                        action.action_id, ActionOutcome.SUCCEEDED
                    )
                else:
                    self._ui_error_log_signal(result.message)
                    self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
            else:
                self._tracker.log_stale_callback(
                    "clear_data",
                    action.action_id,
                    DataManagementActionKind.CLEAR_DATA,
                )
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Failed to clear market data: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._ui_unlock_signal()

    def run_purge_all(self) -> None:
        """Background worker: dispatches ClearMarketDataCommand with purge_all=True."""
        action = self._tracker.begin_action(
            DataManagementActionKind.PURGE_ALL,
            None,
            self._get_current_fsm_state(),
        )
        try:
            cmd = ClearMarketDataCommand(purge_all=True)
            result: ClearMarketDataResult = self._dispatcher.dispatch(
                ClearMarketDataCommand, cmd
            )
            if self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.PURGE_ALL
            ):
                if result.success:
                    self._ui_log_signal(result.message)
                    self._ui_clear_table_signal()
                    self._tracker.finish_action(
                        action.action_id, ActionOutcome.SUCCEEDED
                    )
                else:
                    self._ui_error_log_signal(result.message)
                    self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
            else:
                self._tracker.log_stale_callback(
                    "purge_all",
                    action.action_id,
                    DataManagementActionKind.PURGE_ALL,
                )
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Failed to purge vault: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._ui_unlock_signal()

    def run_vacuum(self) -> None:
        """Background worker: runs SQLite VACUUM compaction using injected repository."""
        action = self._tracker.begin_action(
            DataManagementActionKind.VACUUM,
            None,
            self._get_current_fsm_state(),
        )
        try:
            self._market_data_repo.vacuum()
            if self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.VACUUM
            ):
                self._ui_log_signal("Database optimization (VACUUM) completed.")
                self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
            else:
                self._tracker.log_stale_callback(
                    "vacuum", action.action_id, DataManagementActionKind.VACUUM
                )
        except Exception as exc:  # noqa: BLE001
            self._ui_error_log_signal(f"VACUUM optimization failed: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._ui_stats_refresh_signal()
