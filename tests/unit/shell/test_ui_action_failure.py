"""`EPIC-038A` — a UI slot that raised reaches the run log and the channels.

Before the task, `SystemFailureLog` and `NotificationEventHandler` each
subscribed to `UiActionFailedEvent` themselves, so these cases lived in their
test files. The event's type is the Engine's Qt package, so the subscription now
sits in `UiActionFailureSubscriber` (the GUI wiring); the cases moved with it,
with the same assertions, against the same two sinks.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_system_failure_reporter import (
    ISystemFailureReporter,
)
from Sagittarius_Elite_Warrior.src.shell.system_failure_log import SystemFailureLog
from Sagittarius_Elite_Warrior.src.shell.system_failure_relay import (
    SystemFailureRelay,
)
from Sagittarius_Elite_Warrior.src.shell.ui_action_failure import (
    UiActionFailureSubscriber,
    from_ui_action_failed,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.failure_doubles import (
    RecordingChannel,
    RecordingLogger,
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


class _RecordingReporter(ISystemFailureReporter):
    def __init__(self) -> None:
        self.reports: list[tuple[str, str]] = []

    def report_failure(self, source: str, summary: str) -> None:
        self.reports.append((source, summary))


class _Subscribed:
    """The subscriber built over the real sinks, as `add_gui_wiring` builds it."""

    def __init__(self) -> None:
        self.bus = MemoryEventBus()
        self.logger = RecordingLogger()
        self.channel = RecordingChannel()
        self.reporter = _RecordingReporter()
        relay = SystemFailureRelay(self.bus, lambda: self.reporter, RecordingLogger())
        relay.add_channel(self.channel)
        self.subscriber = UiActionFailureSubscriber(
            self.bus, SystemFailureLog(self.bus, self.logger), relay
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


def test_a_failing_ui_slot_reaches_the_alert_module_with_the_slot_as_its_source() -> (
    None
):
    """The relay is what the UI subscriber calls, so the alert module hears a UI failure
    through the same port as a failed task; the traceback stays in the log."""
    wired = _Subscribed()

    wired.bus.emit(_failed_slot())

    [(source, summary)] = wired.reporter.reports
    assert source == "_on_start_clicked"
    assert "AttributeError" in summary
    assert "Traceback" not in summary
