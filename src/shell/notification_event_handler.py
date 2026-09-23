"""`NotificationEventHandler` — `BOT-018`: surfaces a notable runtime failure
beyond the log file `SystemFailureLog` already writes to.

@details
`SystemFailureLog` (`BUG-126`) already turns `UiActionFailedEvent`/
`TaskFailed` into an `ERROR` log line — necessary, but easy to miss if
nobody is watching the log file. This subscriber fans the same two events,
plus a bulk data-sync failure (`BulkSyncProgressEvent` with
`has_error=True`), out to zero or more `INotificationChannel`s (a UI toast,
a Telegram message) instead of duplicating what already reaches the log —
message text for the two failure events is read from
`system_error_report.py`'s own normalisers rather than re-derived here.

Channels are added after construction (`add_channel`), not passed as a
complete list up front, because the UI channel needs a `MainWindow` that
does not exist yet when the composition root builds this — the same
two-phase pattern `app_bootstrapper.py` already uses for
`INavigationService`.

Debounce: only the immediately-previous message is remembered, and an
identical repeat is dropped. This is deliberately the simplest fix for the
concrete risk the task names (a reconnect loop repeating the exact same
failure many times a second), not a time-windowed rate limiter — nothing
here has called for one yet (`architecture-rule.md` §7.2.1).

**Delivery always runs off the thread that published the event**
(`ITaskManager.spawn`), never inline in `_notify()`. Two independent reasons
forced this, not one: `TaskFailed` (`runtime.tasks.failed`) is always
published from a background worker — `base_feed.py`'s own docstring names
it as the textbook case for "touching a Qt object off the main thread is
the `BUG-031` bug class" — so a Qt-touching channel synchronously called
from `_notify()` would corrupt Qt state exactly that way (caught in review,
PR #259). Separately, `UiActionFailedEvent` is published from the main
thread (a UI slot raised), and `TelegramNotificationChannel.send()` is a
blocking network call with a 5 s timeout — calling it inline there would
freeze the UI thread on every UI-slot failure, `ui-presentation-rule.md`
§2's "the UI thread never blocks". Dispatching unconditionally, regardless
of which thread produced the event, is one mechanism that closes both
holes rather than two special cases; `UiToastNotificationChannel` still
hops back to the main thread itself for the actual widget touch (its own
docstring explains why that part cannot move here).
"""

from __future__ import annotations

import functools

from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.shell.system_error_report import (
    from_task_failed,
    from_ui_action_failed,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.runtime.tasks.events import TaskFailed

#: The greppable subsystem tag `logging-rule.md` §8 requires.
_TAG = "[notification]"
_DELIVERY_TASK_NAME = "notification-delivery"


class NotificationEventHandler:
    """Subscribes once to the three failure sources `BOT-018` names and fans
    each one out to every registered `INotificationChannel`."""

    def __init__(
        self, event_bus: IEventBus, logger: ILogger, task_manager: ITaskManager
    ) -> None:
        self._logger = logger
        self._task_manager = task_manager
        self._channels: list[INotificationChannel] = []
        self._last_message: str | None = None
        event_bus.on(BulkSyncProgressEvent, self._on_bulk_sync_progress)
        event_bus.on(UiActionFailedEvent, self._on_ui_action_failed)
        event_bus.on(TaskFailed, self._on_task_failed)

    def add_channel(self, channel: INotificationChannel) -> None:
        self._channels.append(channel)

    def _on_bulk_sync_progress(self, event: BulkSyncProgressEvent) -> None:
        if not event.has_error:
            return
        self._notify(
            f"Data sync failed — {event.symbol} ({event.interval}): {event.message}"
        )

    def _on_ui_action_failed(self, event: UiActionFailedEvent) -> None:
        self._notify(from_ui_action_failed(event).summary)

    def _on_task_failed(self, event: TaskFailed) -> None:
        self._notify(from_task_failed(event).summary)

    def _notify(self, message: str) -> None:
        if message == self._last_message:
            return
        self._last_message = message
        for channel in self._channels:
            self._task_manager.spawn(
                functools.partial(self._deliver, channel, message),
                name=_DELIVERY_TASK_NAME,
            )

    def _deliver(self, channel: INotificationChannel, message: str) -> None:
        try:
            channel.send(message)
        except Exception as exc:  # noqa: BLE001 - channel boundary, see the comment below
            # A channel boundary (`i_notification_channel.py`'s own
            # contract says a channel must not raise) — this is the
            # backstop for an implementation that breaks that contract.
            # One misbehaving channel must not stop the remaining
            # channels, or the background task that carried this one.
            self._logger.warning(
                f"{_TAG} {type(channel).__name__} raised delivering "
                f"a notification: {type(exc).__name__}: {exc}"
            )
