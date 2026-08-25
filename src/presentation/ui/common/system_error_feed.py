"""
@brief `SystemErrorFeed` — the single subscriber for failures that were
previously reported to nobody.

@details
`EPIC-008`'s §1 named this as one of three things broken at runtime rather
than merely untidy: `safe_ui_action` publishes `UiActionFailedEvent` with a
full traceback whenever a UI slot raises, and `TaskManager` publishes
`runtime.tasks.failed` whenever a background task dies. Both had **zero
subscribers**. A failure in either path left no trace anywhere a user could
see — the exact reason the epic is P1.

`UiActionFailedEvent`'s own docstring even instructs readers to
*"subscribe via `event_bus.on(UiActionFailedEvent, handler)`"*. Nothing in the
design ever required it, so nobody did; `EPIC-008H`'s guard is what stops that
recurring.

@par One subscriber, many displays
This is the epic's core rule made concrete (`README` §2). The feed subscribes
**once**, normalises both event shapes into a `SystemErrorReport`, and re-emits
on a Qt signal. Screens connect to that signal to display it. They do not each
subscribe to the bus, because then every screen would carry its own copy of the
normalising logic — which is how `HealthUpdatedEvent` ended up with three
separate formatters of the same dict.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.system_error_report import (
    SystemErrorReport,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.runtime.tasks.events import TaskFailed


class SystemErrorFeed(BaseFeed):
    """
    @brief Listens for failures on the event bus and re-broadcasts them to any
    screen that wants to show them.
    """

    #: Carries a `SystemErrorReport`. `object` rather than several positional
    #: arguments so adding a field later cannot silently reorder a connection
    #: (`EPIC-008G` §3).
    errorReported = Signal(object)

    def _subscribe(self) -> None:
        """@brief Both failure paths, one subscriber each. `BaseFeed` wraps
        the bus in `QtEventBridge`, so `runtime.tasks.failed` — published from a
        worker thread — is delivered on the main thread."""
        self._events.on(UiActionFailedEvent, self._on_ui_action_failed)
        self._events.on(TaskFailed, self._on_task_failed)

    def _on_ui_action_failed(self, event: Any) -> None:
        self.errorReported.emit(
            SystemErrorReport(
                source=getattr(event, "function_name", "unknown slot"),
                summary=(
                    f"Lỗi giao diện trong {getattr(event, 'function_name', '?')}: "
                    f"{getattr(event, 'exception_type', 'Exception')}: "
                    f"{getattr(event, 'message', '')}"
                ),
                detail=getattr(event, "traceback", "") or "",
            )
        )

    def _on_task_failed(self, event: Any) -> None:
        error = getattr(event, "error", None)
        task_name = getattr(event, "task_name", None) or getattr(
            event, "task_id", "unknown task"
        )
        self.errorReported.emit(
            SystemErrorReport(
                source=str(task_name),
                summary=(
                    f"Tác vụ nền '{task_name}' thất bại: "
                    f"{type(error).__name__ if error is not None else 'Unknown'}: "
                    f"{error}"
                ),
                detail=str(error) if error is not None else "",
            )
        )
