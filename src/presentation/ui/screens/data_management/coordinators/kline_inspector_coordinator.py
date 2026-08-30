from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
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
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class KLineInspectorCoordinator:
    """Coordinates raw historical KLine inspection and database integrity audit."""

    def __init__(
        self,
        dispatcher: IDispatcher,
        thread_manager: IThreadManager,
        tracker: ActionOwnershipTracker[DataManagementActionKind, object, UIMode],
        ui_error_log_signal: Callable[[str], None],
        ui_kline_inspector_signal: Callable[[str, str, list[object]], None],
        ui_audit_result_signal: Callable[
            [bool, int, str, list[dict[str, object]]], None
        ],
        get_current_fsm_state: Callable[[], UIMode],
    ) -> None:
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._tracker = tracker
        self._ui_error_log_signal = ui_error_log_signal
        self._ui_kline_inspector_signal = ui_kline_inspector_signal
        self._ui_audit_result_signal = ui_audit_result_signal
        self._get_current_fsm_state = get_current_fsm_state

    def run_inspect_klines(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        """Background worker: queries historical klines and delivers to UI."""
        action = self._tracker.begin_action(
            DataManagementActionKind.INSPECT_KLINES,
            {"symbol": symbol, "interval": interval},
            self._get_current_fsm_state(),
        )
        try:
            query = GetHistoricalKlinesQuery(
                symbol=symbol,
                interval=interval,
                limit=10000,
                order_by_desc=False,
            )
            klines = self._dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.INSPECT_KLINES
            ):
                self._tracker.log_stale_callback(
                    "inspect_klines",
                    action.action_id,
                    DataManagementActionKind.INSPECT_KLINES,
                )
                return

            self._ui_kline_inspector_signal(symbol, interval, klines or [])
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001
            self._ui_error_log_signal(f"Failed to inspect klines: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)

    def run_audit(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        """Background worker: runs integrity audit on the selected shard."""
        action = self._tracker.begin_action(
            DataManagementActionKind.RUN_AUDIT,
            {"symbol": symbol, "interval": interval},
            self._get_current_fsm_state(),
        )
        try:
            query = AuditDatabaseIntegrityQuery(
                symbol=symbol, interval=TimeFrame(interval)
            )
            result: DatabaseAuditResultDTO = self._dispatcher.dispatch(
                AuditDatabaseIntegrityQuery, query
            )
            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.RUN_AUDIT
            ):
                self._tracker.log_stale_callback(
                    "run_audit", action.action_id, DataManagementActionKind.RUN_AUDIT
                )
                return

            if result.is_clean:
                summary = (
                    f"Dữ liệu toàn vẹn 100%! Đã kiểm định {result.total_checked:,} nến, "
                    f"không phát hiện nến lỗi."
                )
            else:
                summary = (
                    f"Cảnh báo: Phát hiện {result.anomaly_count:,} nến bất thường trong "
                    f"{result.total_checked:,} nến đã kiểm định."
                )

            anomalies_list = [
                {
                    "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": a.anomaly_type,
                    "description": a.description,
                    "raw": str(a.raw_values),
                }
                for a in result.anomalies
            ]
            self._ui_audit_result_signal(
                result.is_clean,
                result.anomaly_count,
                summary,
                anomalies_list,
            )
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001
            self._ui_error_log_signal(f"Failed to audit database: {exc}")
            self._ui_audit_result_signal(False, 0, f"Lỗi kiểm định: {exc}", [])
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
