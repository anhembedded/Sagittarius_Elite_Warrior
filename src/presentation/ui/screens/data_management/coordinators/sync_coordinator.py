from collections.abc import Callable
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_report import (
    SyncProgressReport,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators.action_kinds import (
    DataManagementActionKind,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

_CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"


class SyncCoordinator:
    """Coordinates single and bulk market data synchronization from Binance, progress events, and cancellation."""

    def __init__(
        self,
        view_model: DataManagementViewModel,
        dispatcher: IDispatcher,
        thread_manager: IThreadManager,
        tracker: ActionOwnershipTracker[DataManagementActionKind, object, UIMode],
        ui_log_signal: Callable[[str], None],
        ui_error_log_signal: Callable[[str], None],
        ui_single_sync_progress_signal: Callable[[int, int, bool, str], None],
        ui_sync_complete_signal: Callable[[], None],
        ui_unlock_signal: Callable[[], None],
        transition_fsm: Callable[[UIMode], bool],
        get_current_fsm_state: Callable[[], UIMode],
        is_shutdown_requested: Callable[[], bool],
    ) -> None:
        self._view_model = view_model
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._tracker = tracker
        self._ui_log_signal = ui_log_signal
        self._ui_error_log_signal = ui_error_log_signal
        self._ui_single_sync_progress_signal = ui_single_sync_progress_signal
        self._ui_sync_complete_signal = ui_sync_complete_signal
        self._ui_unlock_signal = ui_unlock_signal
        self._transition_fsm = transition_fsm
        self._get_current_fsm_state = get_current_fsm_state
        self._is_shutdown_requested = is_shutdown_requested

        self._cancellation_token: CancellationToken | None = None

    @property
    def cancellation_token(self) -> CancellationToken | None:
        return self._cancellation_token

    def cancel(self) -> None:
        """Idempotently cancel any currently active sync task."""
        if self._cancellation_token is not None:
            self._cancellation_token.cancel()

    def run_single_sync(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None,
        end_time: datetime | None,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: dispatches SyncMarketDataCommand for a single target."""
        token_to_use = cancellation_token or self._cancellation_token
        action = self._tracker.begin_action(
            DataManagementActionKind.SYNC_SINGLE,
            {
                "symbol": symbol,
                "interval": interval,
                "start_time": start_time,
                "end_time": end_time,
            },
            self._get_current_fsm_state(),
        )
        try:
            cmd = SyncMarketDataCommand(
                symbols=[symbol],
                interval=TimeFrame(interval),
                start_time=start_time,
                end_time=end_time,
                cancellation_requested=(
                    token_to_use.is_cancelled if token_to_use else None
                ),
            )
            self._dispatcher.dispatch(SyncMarketDataCommand, cmd)
            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.SYNC_SINGLE
            ):
                self._tracker.log_stale_callback(
                    "single_sync",
                    action.action_id,
                    DataManagementActionKind.SYNC_SINGLE,
                )
                return

            if token_to_use is not None and token_to_use.is_cancelled():
                self._ui_log_signal(f"Đã dừng đồng bộ {symbol} ({interval}).")
                self._tracker.finish_action(action.action_id, ActionOutcome.CANCELLED)
            else:
                self._ui_log_signal(
                    f"Sync completed successfully for {symbol} ({interval})."
                )
                self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
                self._ui_sync_complete_signal()
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Sync failed: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._cancellation_token = None
            self._ui_unlock_signal()

    def run_bulk_sync(
        self,
        targets: list[tuple[str, str]],
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: dispatches BulkSyncMarketDataCommand."""
        token_to_use = cancellation_token or self._cancellation_token
        action = self._tracker.begin_action(
            DataManagementActionKind.SYNC_BULK,
            {"targets": targets},
            self._get_current_fsm_state(),
        )
        try:
            cmd = BulkSyncMarketDataCommand(
                targets=targets,
                cancellation_requested=(
                    token_to_use.is_cancelled if token_to_use else None
                ),
            )
            self._dispatcher.dispatch(BulkSyncMarketDataCommand, cmd)
            if not self._tracker.is_current_pending(
                action.action_id, DataManagementActionKind.SYNC_BULK
            ):
                self._tracker.log_stale_callback(
                    "bulk_sync",
                    action.action_id,
                    DataManagementActionKind.SYNC_BULK,
                )
                return

            if token_to_use is not None and token_to_use.is_cancelled():
                self._ui_log_signal("Đã dừng quá trình đồng bộ hàng loạt.")
                self._tracker.finish_action(action.action_id, ActionOutcome.CANCELLED)
            else:
                self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Failed to dispatch bulk sync: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._cancellation_token = None
            self._ui_unlock_signal()

    def handle_bulk_sync_progress(self, event: BulkSyncProgressEvent) -> None:
        """Bridge BulkSyncProgressEvent Domain Events -> Qt Signals."""
        if event.message:
            self._ui_log_signal(event.message)

        if event.total_targets > 0:
            msg = f"Đang đồng bộ: {event.current_index}/{event.total_targets} mục"
            if event.symbol and event.interval:
                msg += f" ({event.symbol} {event.interval})"
            self._ui_single_sync_progress_signal(
                event.current_index, event.total_targets, True, msg
            )

        if event.is_complete or event.has_error:
            if event.is_complete:
                self._ui_sync_complete_signal()
            self._ui_unlock_signal()

    def publish_single_sync_progress(self, report: SyncProgressReport) -> None:
        """Đẩy một `SyncProgressReport` (đã chuẩn hoá bởi `SyncProgressFeed`)
        lên UI.

        Trước `EPIC-008G` hàm này nhận thẳng `SingleSyncProgressEvent` từ bus và
        **tự ghép chuỗi** — nơi duy nhất trong app có câu chữ tiến độ, nên màn
        thứ hai muốn hiển thị sẽ phải ghép bản riêng. Câu chữ giờ nằm ở
        `SyncProgressReport.to_message()`."""
        self._ui_single_sync_progress_signal(
            report.current, report.total, True, report.to_message()
        )

    def custom_time_range(self) -> tuple[datetime | None, datetime | None]:
        """Parse custom time range from view model."""
        if not self._view_model.useCustomTime:
            return None, None

        start_raw = self._view_model.fromDateTime.strip()
        end_raw = self._view_model.toDateTime.strip()

        if not start_raw:
            return None, None

        start = self.parse_datetime(start_raw)
        if start is None:
            return None, None

        end = self.parse_datetime(end_raw) if end_raw else None
        return start, end

    @staticmethod
    def parse_datetime(raw: str) -> datetime | None:
        try:
            return datetime.strptime(raw.strip(), _CUSTOM_TIME_FORMAT).replace(
                tzinfo=UTC
            )
        except (ValueError, AttributeError):
            return None
