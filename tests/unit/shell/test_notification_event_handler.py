"""`BOT-018` — `NotificationEventHandler` fans failures out to notification
channels beyond the log file `SystemFailureLog` already writes to.

Mirrors `test_system_failure_log.py`'s structure: the first test boots the
real object graph (`BUG-126`'s own lesson — a subscriber only a unit test
constructs proves nothing about production), the rest exercise the
handler directly against a real `MemoryEventBus`.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.notification_event_handler import (
    NotificationEventHandler,
)
from sagittarius_engine.extensions.pyside_mvc.safety.ui_action_events import (
    UiActionFailedEvent,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.runtime.tasks.events import TaskFailed

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "src",
    "config",
)


class _RecordingLogger(ILogger):
    """A real `ILogger`, not a shape assembled from the calls under test
    (`CS-001`, `testing-rule.md` §2)."""

    def __init__(self) -> None:
        self.lines: dict[str, list[str]] = {}

    def _record(self, level: str, message: str) -> None:
        self.lines.setdefault(level, []).append(message)

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("info", message)

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("warning", message)

    def error(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("error", message)

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("debug", message)

    def critical(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("critical", message)

    def trace(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._record("trace", message)


class _RecordingChannel(INotificationChannel):
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, message: str) -> None:
        self.sent.append(message)


class _RaisingChannel(INotificationChannel):
    def send(self, message: str) -> None:
        raise RuntimeError("channel is down")


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    config_manager.load_json(os.path.join(_CONFIG_DIR, "app_config.json"))
    config_manager.load_json(os.path.join(_CONFIG_DIR, "user_config.json"))
    app = create_app(config_manager)
    yield app
    app.stop()


def test_the_real_graph_subscribes_a_notification_handler(booted_app):
    """`test_a_bus_subscriber_is_constructed.py`'s guard covers "named
    somewhere"; this covers the stronger claim `BUG-126` cared about —
    the real graph the composition root builds actually has a live
    subscriber for all three failure sources."""
    bus = booted_app.event_bus
    assert isinstance(bus, MemoryEventBus)

    unheard = [
        event_type.__name__
        for event_type in (BulkSyncProgressEvent, UiActionFailedEvent, TaskFailed)
        if not bus.get_handlers(event_type)
    ]

    assert unheard == [], (
        f"{unheard} reach no subscriber after create_app() — a failure "
        "published on one of these would surface nowhere beyond the log "
        "file. See src/shell/notification_event_handler.py."
    )


def test_a_sync_error_notifies_every_channel():
    bus = MemoryEventBus()
    handler = NotificationEventHandler(bus, _RecordingLogger())
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(
        BulkSyncProgressEvent(
            current_index=3,
            total_targets=10,
            symbol="ETHUSDT",
            interval="1m",
            has_error=True,
            message="Failed: connection reset",
        )
    )

    assert len(channel.sent) == 1
    assert "ETHUSDT" in channel.sent[0]
    assert "connection reset" in channel.sent[0]


def test_a_successful_sync_progress_step_notifies_nobody():
    bus = MemoryEventBus()
    handler = NotificationEventHandler(bus, _RecordingLogger())
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(
        BulkSyncProgressEvent(
            current_index=1,
            total_targets=10,
            symbol="ETHUSDT",
            interval="1m",
            has_error=False,
            message="[1/10] ETHUSDT (1m) complete.",
        )
    )

    assert channel.sent == []


def test_a_failing_ui_slot_notifies_with_the_same_summary_the_log_gets():
    bus = MemoryEventBus()
    handler = NotificationEventHandler(bus, _RecordingLogger())
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(
        UiActionFailedEvent(
            function_name="_on_start_clicked",
            exception_type="AttributeError",
            message="'MemoryEventBus' object has no attribute 'publish'",
            traceback="Traceback (most recent call last):\n  ...",
        )
    )

    assert len(channel.sent) == 1
    assert "_on_start_clicked" in channel.sent[0]
    assert "AttributeError" in channel.sent[0]
    # The full traceback is the log's detail line, never the notification.
    assert "Traceback" not in channel.sent[0]


def test_a_failed_background_task_notifies_every_channel():
    bus = MemoryEventBus()
    handler = NotificationEventHandler(bus, _RecordingLogger())
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(
        TaskFailed(
            task_id="task-7",
            task_name="historical-sync",
            error=ValueError("candle grid drifted"),
        )
    )

    assert len(channel.sent) == 1
    assert "historical-sync" in channel.sent[0]
    assert "candle grid drifted" in channel.sent[0]


def test_an_identical_repeated_failure_is_debounced():
    """The task's own risk note: a reconnect loop must not spam the same
    failure over and over."""
    bus = MemoryEventBus()
    handler = NotificationEventHandler(bus, _RecordingLogger())
    channel = _RecordingChannel()
    handler.add_channel(channel)

    event = TaskFailed(
        task_id="task-1", task_name="ws-reconnect", error=ConnectionError("dropped")
    )
    bus.emit(event)
    bus.emit(event)
    bus.emit(event)

    assert len(channel.sent) == 1


def test_a_different_failure_after_a_repeat_still_notifies():
    bus = MemoryEventBus()
    handler = NotificationEventHandler(bus, _RecordingLogger())
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("first")))
    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("first")))
    bus.emit(TaskFailed(task_id="t2", task_name="job-b", error=ValueError("second")))

    assert len(channel.sent) == 2


def test_a_raising_channel_does_not_stop_the_other_channels_or_crash():
    bus = MemoryEventBus()
    logger = _RecordingLogger()
    handler = NotificationEventHandler(bus, logger)
    good_channel = _RecordingChannel()
    handler.add_channel(_RaisingChannel())
    handler.add_channel(good_channel)

    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("boom")))

    assert len(good_channel.sent) == 1
    warnings = logger.lines.get("warning", [])
    assert any("_RaisingChannel" in line for line in warnings), (
        f"the misbehaving channel's failure was never reported: {warnings}"
    )
