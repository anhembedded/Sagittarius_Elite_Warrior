from collections.abc import Callable
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.application.use_cases.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    GetDatabaseGapsQuery,
    GetDatabaseGapsResult,
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
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class GapCoordinator:
    """Coordinates database gap inspection and single/all gap repair operations."""

    def __init__(
        self,
        dispatcher: IDispatcher,
        thread_manager: IThreadManager,
        tracker: ActionOwnershipTracker[DataManagementActionKind, object, UIMode],
        ui_log_signal: Callable[[str], None],
        ui_error_log_signal: Callable[[str], None],
        ui_gap_inspector_signal: Callable[
            [
                str,
                str,
                int,
                int,
                float,
                list[dict[str, object]],
                list[dict[str, object]],
            ],
            None,
        ],
        ui_unlock_signal: Callable[[], None],
        transition_fsm: Callable[[UIMode], bool],
        get_current_fsm_state: Callable[[], UIMode],
        is_shutdown_requested: Callable[[], bool],
        on_check_status_callback: Callable[[str, str], None],
    ) -> None:
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._tracker = tracker
        self._ui_log_signal = ui_log_signal
        self._ui_error_log_signal = ui_error_log_signal
        self._ui_gap_inspector_signal = ui_gap_inspector_signal
        self._ui_unlock_signal = ui_unlock_signal
        self._transition_fsm = transition_fsm
        self._get_current_fsm_state = get_current_fsm_state
        self._is_shutdown_requested = is_shutdown_requested
        self._on_check_status_callback = on_check_status_callback

        self._cancellation_token: CancellationToken | None = None

    @property
    def cancellation_token(self) -> CancellationToken | None:
        return self._cancellation_token

    def cancel(self) -> None:
        """Idempotently cancel any currently active gap repair task."""
        if self._cancellation_token is not None:
            self._cancellation_token.cancel()

    def run_inspect_gaps(self, symbol: str, interval: str) -> None:
        """Background worker: dispatches GetDatabaseGapsQuery and opens modal."""
        action = self._tracker.begin_action(
            DataManagementActionKind.INSPECT_GAPS,
            {"symbol": symbol, "interval": interval},
            self._get_current_fsm_state(),
        )
        try:
            query = GetDatabaseGapsQuery(symbol=symbol, interval=interval)
            result: GetDatabaseGapsResult = self._dispatcher.dispatch(
                GetDatabaseGapsQuery, query
            )
            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.INSPECT_GAPS
            ):
                self._tracker.log_stale_callback(
                    "inspect_gaps",
                    action.action_id,
                    DataManagementActionKind.INSPECT_GAPS,
                )
                return

            gaps_data = [
                {
                    "gap_id": g.gap_id,
                    "symbol": g.symbol,
                    "interval": g.interval,
                    "start_time": g.start_time,
                    "end_time": g.end_time,
                    "fetch_start_time": g.fetch_start_time,
                    "fetch_end_time": g.fetch_end_time,
                    "duration_text": g.duration_text,
                    "missing_candles": g.missing_candles,
                }
                for g in result.gaps
            ]
            segments_data = [
                {
                    "is_gap": s.is_gap,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "ratio": s.ratio,
                    "candle_count": s.candle_count,
                }
                for s in result.coverage_segments
            ]
            self._ui_gap_inspector_signal(
                result.symbol,
                result.interval,
                result.total_gaps,
                result.total_missing_candles,
                result.coverage_percentage,
                gaps_data,
                segments_data,
            )
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001
            self._ui_error_log_signal(f"Error inspecting gaps for {symbol}: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)

    def run_repair_gap(
        self,
        symbol: str,
        interval: str,
        start_iso: str,
        end_iso: str,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: downloads missing klines for a single gap."""
        token_to_use = cancellation_token or self._cancellation_token
        action = self._tracker.begin_action(
            DataManagementActionKind.REPAIR_GAP,
            {
                "symbol": symbol,
                "interval": interval,
                "start_time": start_iso,
                "end_time": end_iso,
            },
            self._get_current_fsm_state(),
        )
        try:
            start_dt = datetime.fromisoformat(start_iso).replace(tzinfo=UTC)
            end_dt = datetime.fromisoformat(end_iso).replace(tzinfo=UTC)
            interval_vo = TimeFrame(interval)

            cmd = RepairDataGapCommand(
                symbol=symbol,
                interval=interval_vo,
                start_time=start_dt,
                end_time=end_dt,
                cancellation_requested=(
                    token_to_use.is_cancelled if token_to_use else None
                ),
            )
            result: RepairDataGapResult = self._dispatcher.dispatch(
                RepairDataGapCommand, cmd
            )

            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.REPAIR_GAP
            ):
                self._tracker.log_stale_callback(
                    "repair_gap",
                    action.action_id,
                    DataManagementActionKind.REPAIR_GAP,
                )
                return

            if result.success:
                self._ui_log_signal(result.message)
                self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
            else:
                self._ui_error_log_signal(result.message)
                self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)

            if token_to_use is None or not token_to_use.is_cancelled():
                self.run_inspect_gaps(symbol, interval)
                self._on_check_status_callback(symbol, interval)
        except Exception as exc:  # noqa: BLE001
            self._ui_error_log_signal(f"Failed to repair gap: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._cancellation_token = None
            self._ui_unlock_signal()

    def run_repair_all_gaps(
        self,
        symbol: str,
        interval: str,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: sequentially repairs all detected gaps."""
        token_to_use = cancellation_token or self._cancellation_token
        action = self._tracker.begin_action(
            DataManagementActionKind.REPAIR_ALL_GAPS,
            {"symbol": symbol, "interval": interval},
            self._get_current_fsm_state(),
        )
        try:
            query = GetDatabaseGapsQuery(symbol=symbol, interval=interval)
            result: GetDatabaseGapsResult = self._dispatcher.dispatch(
                GetDatabaseGapsQuery, query
            )

            for gap in result.gaps:
                if token_to_use is not None and token_to_use.is_cancelled():
                    self._ui_log_signal("Đã dừng quá trình vá lỗ hổng.")
                    self._tracker.finish_action(
                        action.action_id, ActionOutcome.CANCELLED
                    )
                    return
                start_dt = datetime.fromisoformat(gap.fetch_start_time).replace(
                    tzinfo=UTC
                )
                end_dt = datetime.fromisoformat(gap.fetch_end_time).replace(tzinfo=UTC)
                interval_vo = TimeFrame(interval)
                cmd = RepairDataGapCommand(
                    symbol=symbol,
                    interval=interval_vo,
                    start_time=start_dt,
                    end_time=end_dt,
                    cancellation_requested=(
                        token_to_use.is_cancelled if token_to_use else None
                    ),
                )
                self._dispatcher.dispatch(RepairDataGapCommand, cmd)

            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.REPAIR_ALL_GAPS
            ):
                self._tracker.log_stale_callback(
                    "repair_all_gaps",
                    action.action_id,
                    DataManagementActionKind.REPAIR_ALL_GAPS,
                )
                return

            self._ui_log_signal(
                f"Đã hoàn tất vá tất cả {result.total_gaps} lỗ hổng cho {symbol} ({interval})."
            )
            self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)

            if token_to_use is None or not token_to_use.is_cancelled():
                self.run_inspect_gaps(symbol, interval)
                self._on_check_status_callback(symbol, interval)
        except Exception as exc:  # noqa: BLE001
            self._ui_error_log_signal(f"Failed to repair all gaps: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._cancellation_token = None
            self._ui_unlock_signal()
