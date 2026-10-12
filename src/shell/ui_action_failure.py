"""A UI slot raised: normalise the event and hand it to the failure sinks.

`EPIC-038A` moved this out of the shared composition (`composition_root.py`,
`SystemFailureLog`, `NotificationEventHandler`). `UiActionFailedEvent` comes from the
Engine's `pyside_mvc` package, whose `__init__` imports the Qt runtime, so
anything that names it needs PySide6 installed. The shared composition
(`shell/composition_root.py`) is what a process with no window builds, so the
event's normaliser and its subscriber live here and `add_gui_wiring` registers
them for the GUI entry point only. Moved, not rewritten: `SystemFailureLog` and
`NotificationEventHandler` heard this event themselves until then, in that
order, and `UiActionFailureSubscriber` calls them in the same order.

`EPIC-036B` replaces `NotificationEventHandler`. This subscriber is the one
place that names it for UI failures, so that epic changes one constructor
argument here and nothing in the shell.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.shell.notification_event_handler import (
    NotificationEventHandler,
)
from Sagittarius_Elite_Warrior.src.shell.system_error_report import SystemErrorReport
from Sagittarius_Elite_Warrior.src.shell.system_failure_log import SystemFailureLog
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


def from_ui_action_failed(event: UiActionFailedEvent) -> SystemErrorReport:
    """A UI slot raised and `safe_ui_action` caught it.

    Reads the event's fields by name rather than by `getattr` probing. The
    version of this code that `BUG-126` replaced probed every field with a
    default — `getattr(event, "function_name", "unknown slot")` — against a
    frozen dataclass whose fields are all required, so the defaults could never
    fire and the type checker could never help. `architecture-rule.md` §2.1
    calls that shape out by name.
    """
    return SystemErrorReport(
        source=event.function_name,
        summary=(
            f"UI error in {event.function_name}: "
            f"{event.exception_type}: {event.message}"
        ),
        detail=event.traceback,
    )


class UiActionFailureSubscriber:
    """Subscribes once to `UiActionFailedEvent`; each one reaches the run log
    (`SystemFailureLog`) and the notification channels
    (`NotificationEventHandler`)."""

    def __init__(
        self,
        event_bus: IEventBus,
        failure_log: SystemFailureLog,
        notifications: NotificationEventHandler,
    ) -> None:
        self._failure_log = failure_log
        self._notifications = notifications
        event_bus.on(UiActionFailedEvent, self._on_ui_action_failed)

    def _on_ui_action_failed(self, event: UiActionFailedEvent) -> None:
        report = from_ui_action_failed(event)
        self._failure_log.report(report)
        self._notifications.notify(report.summary)
