"""`EPIC-038A` — a UI slot that raised reaches the run log and the channels.

Before the task, `SystemFailureLog` and `NotificationEventHandler` each
subscribed to `UiActionFailedEvent` themselves, so these cases lived in their
test files. The event's type is the Engine's Qt package, so the subscription now
sits in `UiActionFailureSubscriber` (the GUI wiring); the cases moved with it,
with the same assertions, against the same two sinks.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.shell.notification_event_handler import (
    NotificationEventHandler,
)
from Sagittarius_Elite_Warrior.src.shell.system_failure_log import SystemFailureLog
from Sagittarius_Elite_Warrior.src.shell.ui_action_failure import (
    UiActionFailureSubscriber,
    from_ui_action_failed,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.failure_doubles import (
    RecordingChannel,
    RecordingLogger,
    SynchronousTaskManager,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _failed_slot() -> UiActionFailedEvent:
    return UiActionFailedEvent(
        function_name="_on_start_clicked",
        exception_type="AttributeError",
        message="'MemoryEventBus' object has no attribute 'publish'",
        traceback="Traceback (most recent call last):\n  line one\n  line two",
    )


class _Subscribed:
    """The subscriber built over the real sinks, as `add_gui_wiring` builds it."""

    def __init__(self) -> None:
        self.bus = MemoryEventBus()
        self.logger = RecordingLogger()
        self.channel = RecordingChannel()
        notifications = NotificationEventHandler(
            self.bus, RecordingLogger(), SynchronousTaskManager()
        )
        notifications.add_channel(self.channel)
        self.subscriber = UiActionFailureSubscriber(
            self.bus, SystemFailureLog(self.bus, self.logger), notifications
        )


def test_a_failed_ui_action_names_the_slot_and_keeps_the_traceback() -> None:
    report = from_ui_action_failed(
        UiActionFailedEvent(
            function_name="_on_start_clicked",
            exception_type="AttributeError",
            message="no attribute 'publish'",
            traceback="Traceback (most recent call last):\n  line one\n  line two",
        )
    )

    assert report.source == "_on_start_clicked"
    assert "AttributeError" in report.summary
    assert "no attribute 'publish'" in report.summary
    # The whole traceback, not its first line: `BOT-061` is the investigation
    # that cost, and the reason `detail` is a separate field at all.
    assert report.detail.count("\n") == 2


def test_a_failing_ui_slot_is_logged_with_its_traceback() -> None:
    """`safe_ui_action` publishes a full traceback. The summary line carries the
    slot name and the exception; the traceback follows on its own line, because
    `BOT-061` cost a misdirected investigation when only the short message
    survived."""
    wired = _Subscribed()

    wired.bus.emit(_failed_slot())

    errors = wired.logger.lines.get("error", [])
    assert any(
        "_on_start_clicked" in line and "AttributeError" in line for line in errors
    ), f"no error line named the failing slot and its exception: {errors}"
    assert any("Traceback (most recent call last)" in line for line in errors), (
        f"the traceback never reached the log: {errors}"
    )


def test_a_failing_ui_slot_is_logged_at_error_and_nowhere_else() -> None:
    """`ci-local.ps1`'s "Run Log Scan" greps `- (WARNING|ERROR|CRITICAL) -`. A
    failure reported at `INFO` or `DEBUG` would satisfy the test above and still
    be invisible to the gate and to `--dev`'s default threshold."""
    wired = _Subscribed()

    wired.bus.emit(_failed_slot())

    assert set(wired.logger.lines) == {"error"}, sorted(wired.logger.lines)


def test_a_failing_ui_slot_notifies_with_the_same_summary_the_log_gets() -> None:
    wired = _Subscribed()

    wired.bus.emit(_failed_slot())

    assert len(wired.channel.sent) == 1
    assert "_on_start_clicked" in wired.channel.sent[0]
    assert "AttributeError" in wired.channel.sent[0]
    # The full traceback is the log's detail line, never the notification.
    assert "Traceback" not in wired.channel.sent[0]


def test_an_identical_repeated_ui_failure_is_debounced_in_the_channels() -> None:
    """The handler's debounce still applies to the event it no longer hears
    itself: the subscriber goes through `notify()`, not around it."""
    wired = _Subscribed()

    wired.bus.emit(_failed_slot())
    wired.bus.emit(_failed_slot())

    assert len(wired.channel.sent) == 1
