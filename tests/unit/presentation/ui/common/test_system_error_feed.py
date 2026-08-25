"""Tests for `SystemErrorFeed` (`EPIC-008G`).

These are the evidence the task asks for under *"phải hoạt động trở lại"*: both
failure paths had **zero subscribers**, so a UI slot that raised or a
background task that died left no trace anywhere a user could see.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.presentation.ui.common.system_error_feed import (
    SystemErrorFeed,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.system_error_report import (
    SystemErrorReport,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.runtime.tasks.events import TaskFailed


@dataclass
class _Collected:
    reports: list[SystemErrorReport]


def _feed_with_collector(qapp):
    bus = MemoryEventBus()
    feed = SystemErrorFeed(bus)
    collected = _Collected(reports=[])
    feed.errorReported.connect(collected.reports.append)
    return bus, feed, collected


def test_a_failing_ui_slot_reaches_a_subscriber(qapp):
    """`safe_ui_action` publishes `UiActionFailedEvent` with a full traceback.
    Before this feed nothing listened, so the traceback went nowhere."""
    bus, _feed, collected = _feed_with_collector(qapp)

    bus.emit(
        UiActionFailedEvent(
            function_name="_on_run_clicked",
            exception_type="ValueError",
            message="bad input",
            traceback="Traceback (most recent call last):\n  ...\nValueError: bad input",
        )
    )

    assert len(collected.reports) == 1
    report = collected.reports[0]
    assert report.source == "_on_run_clicked"
    assert "ValueError" in report.summary and "bad input" in report.summary
    # The whole point of BOT-061: the traceback must survive, not just the
    # one-line message.
    assert "Traceback" in report.detail


def test_a_failed_background_task_reaches_the_same_subscriber(qapp):
    """The second dead path. A different event shape entirely, normalised into
    the same report so screens never learn two shapes."""
    bus, _feed, collected = _feed_with_collector(qapp)

    bus.emit(
        TaskFailed(
            task_id="sync-1",
            task_name="BulkSync",
            error=RuntimeError("exchange unreachable"),
        )
    )

    assert len(collected.reports) == 1
    report = collected.reports[0]
    assert report.source == "BulkSync"
    assert "RuntimeError" in report.summary
    assert "exchange unreachable" in report.summary


def test_both_sources_share_one_subscriber(qapp):
    """One subscriber, many displays — the epic's core rule. Two unrelated
    failure types arrive on a single signal, in order."""
    bus, _feed, collected = _feed_with_collector(qapp)

    bus.emit(
        UiActionFailedEvent(
            function_name="slot_a",
            exception_type="KeyError",
            message="k",
            traceback="tb",
        )
    )
    bus.emit(TaskFailed(task_id="t", task_name="TaskB", error=OSError("disk")))

    assert [r.source for r in collected.reports] == ["slot_a", "TaskB"]


def test_stop_unsubscribes_both(qapp):
    """A screen tearing down must not leave the feed delivering into a deleted
    object — the leak `BasePresenter.dispose()` closes for presenters."""
    bus, feed, collected = _feed_with_collector(qapp)

    feed.stop()
    bus.emit(
        UiActionFailedEvent(
            function_name="slot", exception_type="E", message="m", traceback="tb"
        )
    )
    bus.emit(TaskFailed(task_id="t", task_name="T", error=RuntimeError("x")))

    assert collected.reports == []


def test_stop_is_idempotent(qapp):
    _bus, feed, _collected = _feed_with_collector(qapp)

    feed.stop()
    feed.stop()  # must not raise
