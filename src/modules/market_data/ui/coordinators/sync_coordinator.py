import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.bulk_sync_market_data.sync_target import (
    SyncTarget,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.sync_progress_report import (
    SyncProgressReport,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators.action_kinds import (
    DataManagementActionKind,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import (
    DATETIME_FORMAT,
    UIMode,
)
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class SyncCoordinator:
    """Coordinates single and bulk market data synchronization from Binance, progress events, and cancellation."""

    def __init__(
        self,
        view_model: DataManagementViewModel,
        dispatcher: IDispatcher,
        market_data_sync: IMarketDataSync,
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
        self._market_data_sync = market_data_sync
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
        # BOT-122 (was a set of (symbol, interval) targets under BOT-121 — a
        # business-key coincidence, not an identity: two different actions
        # can legitimately target the same symbol+interval): the
        # correlation_id THIS coordinator generated for its own in-flight
        # dispatch — one id whether it's a single sync or a whole bulk batch,
        # since every target of one bulk sync shares its batch's id (see
        # `run_bulk_sync`). `SyncProgressFeed` broadcasts every
        # SingleSyncProgressEvent to both this screen and Backtest's; without
        # this a Backtest sync running at the same time would move this
        # screen's progress log using its numbers.
        self._active_correlation_id: str | None = None

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
        """Background worker: asks `IMarketDataSync` to sync one target.

        `EPIC-025` PR 0.5 — it no longer builds `SyncMarketDataCommand`: that
        is market_data's internal, and this screen now names only the port.
        The bulk path below still dispatches, because `BulkSyncMarketDataCommand`
        has no published port yet (Phase 1).
        """
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
        self._active_correlation_id = uuid.uuid4().hex
        try:
            self._market_data_sync.sync(
                MarketDataSyncRequest(
                    symbols=(symbol,),
                    interval=TimeFrame(interval),
                    start_time=start_time,
                    end_time=end_time,
                    cancellation_requested=(
                        token_to_use.is_cancelled if token_to_use else None
                    ),
                    correlation_id=self._active_correlation_id,
                )
            )
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
                self._ui_log_signal(f"Sync stopped for {symbol} ({interval}).")
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
            self._active_correlation_id = None
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
        self._active_correlation_id = uuid.uuid4().hex
        try:
            cmd = BulkSyncMarketDataCommand(
                targets=[
                    SyncTarget(symbol=symbol, interval=TimeFrame(interval))
                    for symbol, interval in targets
                ],
                cancellation_requested=(
                    token_to_use.is_cancelled if token_to_use else None
                ),
                correlation_id=self._active_correlation_id,
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
                self._ui_log_signal("Bulk sync process stopped.")
                self._tracker.finish_action(action.action_id, ActionOutcome.CANCELLED)
            else:
                self._tracker.finish_action(action.action_id, ActionOutcome.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self._ui_error_log_signal(f"Failed to dispatch bulk sync: {exc}")
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
        finally:
            self._cancellation_token = None
            self._active_correlation_id = None
            self._ui_unlock_signal()

    def handle_bulk_sync_progress(self, event: BulkSyncProgressEvent) -> None:
        """Bridge BulkSyncProgressEvent Domain Events -> Qt Signals."""
        if event.message:
            self._ui_log_signal(event.message)

        if event.total_targets > 0:
            msg = f"Syncing: {event.current_index}/{event.total_targets} items"
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
        `SyncProgressReport.to_message()`.

        BOT-122: `report` may belong to a sync Backtest started, not one of
        this screen's own — `SyncProgressFeed` fans every
        `SingleSyncProgressEvent` out to both screens. Only apply it if its
        `correlation_id` matches the one THIS coordinator's own
        `run_single_sync()`/`run_bulk_sync()` is actually waiting on."""
        if (
            self._active_correlation_id is None
            or report.correlation_id != self._active_correlation_id
        ):
            return
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
            return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
        except (ValueError, AttributeError):
            return None

    # ------------------------------------------------------------------ #
    # User-triggered orchestration — runs on the main thread, synchronously
    # from the Presenter's Slot (BOT-144). See `ScanCoordinator`'s own
    # section for why `_transition_fsm` is safe to call only here, never
    # from `run_*()` above.
    #
    # Creating the `CancellationToken` here, in the coordinator that owns
    # the action, rather than on the Presenter, is what makes this
    # coordinator's own `cancel()`/`self._cancellation_token` (above) live:
    # previously nothing ever assigned a real token to that field, so
    # `cancel()` was a silent no-op and the Presenter's own separate token
    # field did the real work. Moving token creation to where the action is
    # now orchestrated closes that gap as a direct consequence of the move,
    # not a separate behavior change.
    # ------------------------------------------------------------------ #

    def request_single_sync(self, symbol: str, interval: str | None = None) -> None:
        """Orchestrates a sync for one symbol/interval, triggered from the UI.

        Shared by the toolbar "Sync" button (current selection) and a
        per-row "Sync" action (explicit `interval`).
        """
        if self._is_shutdown_requested():
            return

        start_time, end_time = self.custom_time_range()
        if self._view_model.useCustomTime:
            if start_time is None:
                self._ui_error_log_signal(
                    f"Invalid custom time range — expected format {DATETIME_FORMAT}."
                )
                return
            if end_time is not None and start_time > end_time:
                self._ui_error_log_signal(
                    "Invalid time range: 'From' date must be before 'To' date."
                )
                return

        target_interval = interval or (
            self._view_model.selectedInterval or TimeFrame.ONE_MINUTE.value
        )
        self._ui_log_signal(
            f"Starting sync from Binance for {symbol} ({target_interval})..."
        )
        self._transition_fsm(UIMode.SYNCING)
        self._view_model.set_progress(value=0, maximum=0, visible=True)

        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self.run_single_sync,
            symbol,
            target_interval,
            start_time,
            end_time,
            self._cancellation_token,
        )

    def request_bulk_sync(self) -> None:
        """Orchestrates "Sync All Gaps", triggered from the UI."""
        if self._is_shutdown_requested():
            return

        targets = self._view_model.status_model.gap_targets()
        if not targets:
            self._ui_log_signal("No gaps found to sync.")
            return

        self._ui_log_signal(
            f"Found {len(targets)} targets to sync. Starting sequential bulk sync..."
        )
        self._transition_fsm(UIMode.SYNCING)
        self._view_model.set_progress(value=0, maximum=len(targets), visible=True)

        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self.run_bulk_sync, targets, self._cancellation_token
        )
