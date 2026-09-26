"""`BOT-144` — clear/purge/VACUUM split out of `ScanCoordinator`.

@details `ScanCoordinator` crossed the `architecture-rule.md` §5.4 400-line
ceiling once its own `request_*` orchestration (BOT-144 §3.1) was added
alongside scanning/auto-discovery. Clear/purge/VACUUM are a distinct job
family — they mutate or compact the vault rather than reading its status —
the same reasoning that already split gap inspection into `GapCoordinator`,
kline inspection into `KLineInspectorCoordinator`, and export/import into
`ExportImportCoordinator`.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators.action_kinds import (
    DataManagementActionKind,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class VaultMaintenanceCoordinator:
    """Coordinates clearing one symbol/interval, purging the entire Storage
    Vault, and SQLite VACUUM compaction."""

    def __init__(
        self,
        dispatcher: IDispatcher,
        thread_manager: IThreadManager,
        tracker: ActionOwnershipTracker[DataManagementActionKind, object, UIMode],
        market_data_repo: IMarketDataRepository,
        ui_log_signal: Callable[[str], None],
        ui_error_log_signal: Callable[[str], None],
        ui_remove_symbol_signal: Callable[[str, str], None],
        ui_clear_table_signal: Callable[[], None],
        ui_stats_refresh_signal: Callable[[], None],
        ui_unlock_signal: Callable[[], None],
        transition_fsm: Callable[[UIMode], bool],
        get_current_fsm_state: Callable[[], UIMode],
        is_shutdown_requested: Callable[[], bool],
    ) -> None:
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._tracker = tracker
        self._market_data_repo = market_data_repo
        self._ui_log_signal = ui_log_signal
        self._ui_error_log_signal = ui_error_log_signal
        self._ui_remove_symbol_signal = ui_remove_symbol_signal
        self._ui_clear_table_signal = ui_clear_table_signal
        self._ui_stats_refresh_signal = ui_stats_refresh_signal
        self._ui_unlock_signal = ui_unlock_signal
        self._transition_fsm = transition_fsm
        self._get_current_fsm_state = get_current_fsm_state
        self._is_shutdown_requested = is_shutdown_requested

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

    # ------------------------------------------------------------------ #
    # User-triggered orchestration — runs on the main thread, synchronously
    # from the Presenter's Slot (BOT-144). See `ScanCoordinator`'s own
    # section for why `_transition_fsm` is safe to call only here.
    # ------------------------------------------------------------------ #

    def request_clear_data(self, symbol: str, interval: str) -> None:
        """Orchestrates clearing one symbol/interval's data, triggered from the UI."""
        if self._is_shutdown_requested():
            return
        self._ui_log_signal(f"Requesting data clear for {symbol} ({interval})...")
        self._transition_fsm(UIMode.CLEARING)
        self._thread_manager.submit(self.run_clear_data, symbol, interval)

    def request_purge_all(self) -> None:
        """Orchestrates purging the entire Storage Vault, triggered from the UI."""
        if self._is_shutdown_requested():
            return
        self._ui_log_signal("Requesting PURGE of all Storage Vault databases...")
        self._transition_fsm(UIMode.CLEARING)
        self._thread_manager.submit(self.run_purge_all)

    def request_vacuum(self) -> None:
        """Orchestrates a VACUUM pass, triggered from the UI.

        No FSM transition here, matching the pre-`BOT-144` slot exactly —
        VACUUM never locked the UI into a busy state.
        """
        if self._is_shutdown_requested():
            return
        self._ui_log_signal("Running SQLite VACUUM optimization...")
        self._thread_manager.submit(self.run_vacuum)
