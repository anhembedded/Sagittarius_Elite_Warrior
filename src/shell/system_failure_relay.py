"""`SystemFailureRelay` - `EPIC-036B`: the app's own failures reach the owner.

Replaces `NotificationEventHandler` (`BOT-018`). `SystemFailureLog` (`BUG-126`) already turns
`TaskFailed` into an `ERROR` log line - necessary, but easy to miss when nobody watches the
log. This subscriber hears the Qt-free failure sources (`TaskFailed`, and a bulk data-sync
failure, `BulkSyncProgressEvent` with `has_error=True`), normalises each once
(`system_error_report.py`, not re-derived) and relays it to two places:

  - the **alerting module**, through `ISystemFailureReporter`: one `APP_FAILURE` alert, deduped
    by the hub, delivered off-box by its lanes (Discord on a headless host);
  - the **in-app toast** (`UiToastNotificationChannel`, added once a window exists): the same
    text, as a second consumer of the same report. Decided here, not routed through an
    `IAlertChannel`: a toast is a notice inside the app, `EPIC-036` leaves it out of the
    alerting module, and an outbox with a 24 h expiry is the wrong home for a message that
    means nothing once the window is closed.

`UiActionFailedEvent` is fed in through `relay()` by the GUI's own subscriber
(`ui_action_failure.py`): its type is the Engine's Qt package, which a process with no UI must
not import.

**No delivery thread, no debounce of its own.** The old handler spawned every send because
`TelegramNotificationChannel.send` blocked for up to 5 s. Nothing here blocks: the reporter
only records (`IAlertPublisher`'s contract) and the toast hops to the main thread itself. The
repeat control is the hub's dedup, which counts instead of dropping.

The reporter is resolved on each failure, not at construction: the composition root builds this
before the bounded contexts register, and a process whose command did not need `alerting`
never binds it.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_system_failure_reporter import (
    ISystemFailureReporter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.shell.system_error_report import (
    SystemErrorReport,
    from_task_failed,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.runtime.tasks.events import TaskFailed

#: The greppable subsystem tag `logging-rule.md` §8 requires.
_TAG = "[notification]"


class SystemFailureRelay:
    """Subscribes once to the Qt-free failure sources and relays each report."""

    def __init__(
        self,
        event_bus: IEventBus,
        reporter: Callable[[], ISystemFailureReporter | None],
        logger: ILogger,
    ) -> None:
        self._reporter = reporter
        self._logger = logger
        self._channels: list[INotificationChannel] = []
        event_bus.on(BulkSyncProgressEvent, self._on_bulk_sync_progress)
        event_bus.on(TaskFailed, self._on_task_failed)

    def add_channel(self, channel: INotificationChannel) -> None:
        """The in-app toast, added when the window exists."""
        self._channels.append(channel)

    def _on_bulk_sync_progress(self, event: BulkSyncProgressEvent) -> None:
        if not event.has_error:
            return
        self.relay(
            SystemErrorReport(
                source=f"data sync {event.symbol} ({event.interval})",
                summary=(
                    f"Data sync failed — {event.symbol} ({event.interval}): "
                    f"{event.message}"
                ),
                detail=event.message,
            )
        )

    def _on_task_failed(self, event: TaskFailed) -> None:
        self.relay(from_task_failed(event))

    def relay(self, report: SystemErrorReport) -> None:
        """Public so the GUI's UI-failure subscriber (`EPIC-038A`) can feed it the one event
        this relay does not subscribe to."""
        self._report_to_alerting(report)
        for channel in self._channels:
            try:
                channel.send(report.summary)
            except Exception as exc:  # noqa: BLE001 - channel boundary
                # `i_notification_channel.py`'s contract says a channel must not raise; this is
                # the backstop, so one broken channel cannot stop the rest or the publisher.
                self._logger.warning(
                    f"{_TAG} {type(channel).__name__} raised delivering "
                    f"a notification: {type(exc).__name__}: {exc}"
                )

    def _report_to_alerting(self, report: SystemErrorReport) -> None:
        try:
            reporter = self._reporter()
            if reporter is not None:
                reporter.report_failure(report.source, report.summary)
        except Exception as exc:  # noqa: BLE001 - a failure path must go on
            self._logger.warning(
                f"{_TAG} the alert module did not take the failure of "
                f"{report.source}: {type(exc).__name__}: {exc}"
            )
