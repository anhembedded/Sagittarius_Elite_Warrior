"""`BOT-112D` — file-based export/import, split out of `ScanCoordinator`.

@details `ScanCoordinator` was already at the `architecture-rule.md` §5.4
400-line ceiling before this feature existed; adding export/import there
would have pushed it well past it. Export/import is its own job family
anyway (moving klines to/from a file, not a vault-lifecycle operation like
clear/purge/VACUUM), the same reasoning that already split gap inspection
into `GapCoordinator` and kline inspection into `KlineInspectorCoordinator`.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.export_market_data import (
    ExportMarketDataCommand,
    ExportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.import_market_data import (
    ImportMarketDataCommand,
    ImportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
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


class ExportImportCoordinator:
    """Coordinates writing stored klines to a file and loading an external
    candle file back into the vault."""

    def __init__(
        self,
        dispatcher: IDispatcher,
        tracker: ActionOwnershipTracker[DataManagementActionKind, object, UIMode],
        ui_log_signal: Callable[[str], None],
        ui_error_log_signal: Callable[[str], None],
        ui_unlock_signal: Callable[[], None],
        ui_stats_refresh_signal: Callable[[], None],
        get_current_fsm_state: Callable[[], UIMode],
    ) -> None:
        self._dispatcher = dispatcher
        self._tracker = tracker
        self._ui_log_signal = ui_log_signal
        self._ui_error_log_signal = ui_error_log_signal
        self._ui_unlock_signal = ui_unlock_signal
        self._ui_stats_refresh_signal = ui_stats_refresh_signal
        self._get_current_fsm_state = get_current_fsm_state

    def run_export(
        self,
        symbol: str,
        interval: str,
        destination_path: str,
        file_format: ExportFileFormat,
    ) -> None:
        """Background worker: dispatches `ExportMarketDataCommand`.
        Read-only — no FSM lock/unlock, same reasoning `ScanCoordinator
        .run_vacuum()` gives: neither mutates the vault, so nothing a
        concurrent action could observe half-done."""
        action = self._tracker.begin_action(
            DataManagementActionKind.EXPORT_DATA,
            {"symbol": symbol, "interval": interval, "path": destination_path},
            self._get_current_fsm_state(),
        )
        try:
            cmd = ExportMarketDataCommand(
                symbol=symbol,
                interval=TimeFrame(interval),
                destination_path=destination_path,
                file_format=file_format,
            )
            # `IDispatcher.dispatch()` is typed against `IDispatchable`, but
            # every coordinator in this package dispatches its own Command
            # dataclasses through it — the same engine-interface mismatch
            # `pyproject.toml`'s `[tool.mypy] exclude` documents as frozen
            # debt for `gap_coordinator.py`/`scan_coordinator.py`/etc. A new
            # file cannot join that list (its own rule: "must be fixed, not
            # added here"), so the identical, already-tolerated shape is
            # suppressed at the two call sites instead of the whole file.
            result: ExportMarketDataResult = self._dispatcher.dispatch(
                ExportMarketDataCommand,  # type: ignore[arg-type]
                cmd,
            )
            if self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.EXPORT_DATA
            ):
                if result.success:
                    self._ui_log_signal(result.message)
                    self._tracker.finish_action(
                        action.action_id, ActionOutcome.SUCCEEDED
                    )
                else:
                    self._ui_error_log_signal(result.message)
                    self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
            else:
                self._tracker.log_stale_callback(
                    "export_data",
                    action.action_id,
                    DataManagementActionKind.EXPORT_DATA,
                )
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Failed to export market data: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)

    def run_import(self, symbol: str, interval: str, source_path: str) -> None:
        """Background worker: dispatches `ImportMarketDataCommand`. Mutates
        the vault, so locks the FSM the way `ScanCoordinator.run_clear_data`/
        `.run_purge_all` do, and refreshes the stat tiles on the way out —
        new candles change coverage the same way a sync would."""
        action = self._tracker.begin_action(
            DataManagementActionKind.IMPORT_DATA,
            {"symbol": symbol, "interval": interval, "path": source_path},
            self._get_current_fsm_state(),
        )
        try:
            cmd = ImportMarketDataCommand(
                symbol=symbol, interval=TimeFrame(interval), source_path=source_path
            )
            # Same frozen `IDispatcher`/`IDispatchable` mismatch as `run_export()`
            # above — see the comment there.
            result: ImportMarketDataResult = self._dispatcher.dispatch(
                ImportMarketDataCommand,  # type: ignore[arg-type]
                cmd,
            )
            if self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.IMPORT_DATA
            ):
                if result.success:
                    self._ui_log_signal(result.message)
                    for warning in result.warnings:
                        self._ui_log_signal(f"  ⚠ {warning}")
                    self._tracker.finish_action(
                        action.action_id, ActionOutcome.SUCCEEDED
                    )
                else:
                    self._ui_error_log_signal(result.message)
                    self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
            else:
                self._tracker.log_stale_callback(
                    "import_data",
                    action.action_id,
                    DataManagementActionKind.IMPORT_DATA,
                )
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Failed to import market data: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._ui_unlock_signal()
            self._ui_stats_refresh_signal()
