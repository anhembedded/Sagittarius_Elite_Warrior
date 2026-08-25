from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
        IEventPublisher,
    )


class BulkSyncProgressReporter:
    """
    @brief Progress Reporter (Observer / Builder Pattern) for Bulk Sync lifecycle.
    @details Encapsulates progress calculation, status message formatting, and
    progress event emissions through IEventPublisher.
    """

    def __init__(self, event_publisher: IEventPublisher, total_targets: int) -> None:
        self._event_publisher = event_publisher
        self._total_targets = max(0, int(total_targets))
        self._completed_count = 0

    @property
    def completed_count(self) -> int:
        return self._completed_count

    @property
    def total_targets(self) -> int:
        return self._total_targets

    def report_target(
        self,
        symbol: str,
        interval: str,
        has_error: bool = False,
        error_msg: str = "",
    ) -> None:
        """Increments completed count and emits a per-target progress event."""
        self._completed_count += 1
        message = (
            f"[{self._completed_count}/{self._total_targets}] {symbol} ({interval}) complete."
            if not has_error
            else f"Failed: {error_msg}"
        )
        self._event_publisher.publish(
            BulkSyncProgressEvent(
                current_index=self._completed_count,
                total_targets=self._total_targets,
                symbol=symbol,
                interval=interval,
                has_error=has_error,
                message=message,
            )
        )

    def report_empty(self) -> None:
        """Emits an immediate completion event when the target list is empty."""
        self._event_publisher.publish(
            BulkSyncProgressEvent(
                current_index=0,
                total_targets=0,
                symbol="",
                interval="",
                is_complete=True,
                message="No targets to sync.",
            )
        )

    def report_completed(self) -> None:
        """Emits the final batch completion event."""
        self._event_publisher.publish(
            BulkSyncProgressEvent(
                current_index=self._total_targets,
                total_targets=self._total_targets,
                symbol="",
                interval="",
                is_complete=True,
                message="Bulk sync completed successfully.",
            )
        )
