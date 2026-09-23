"""`BOT-018` — `NotificationEventHandler` fans failures out to notification
channels beyond the log file `SystemFailureLog` already writes to.

Mirrors `test_system_failure_log.py`'s structure: the first test boots the
real object graph (`BUG-126`'s own lesson — a subscriber only a unit test
constructs proves nothing about production), the rest exercise the
handler directly against a real `MemoryEventBus`.

`_SynchronousTaskManager` runs a submitted callable immediately, inline,
rather than on a real thread pool: PR #259's review found that
`NotificationEventHandler` must dispatch every channel's `send()` through
`ITaskManager` rather than calling it inline (a Qt-touching channel must
never run on whatever thread published the triggering event —
`runtime.tasks.failed` is always a background thread). A real
`ThreadPoolExecutor`-backed manager would make these tests race against a
worker thread; a synchronous fake derived from the real `ITaskManager` ABC
(`testing-rule.md` §2's sanctioned alternative to the real thing) keeps them
deterministic while still proving the handler goes through the port rather
than calling `channel.send()` itself.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
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
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
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


class _ImmediateTaskHandle(ITaskHandle):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def id(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    @property
    def token(self):
        return None

    @property
    def future(self):
        return None

    @property
    def status(self):
        return None

    @property
    def progress(self) -> float:
        return 100.0

    def cancel(self) -> None:
        pass


class _SynchronousTaskManager(ITaskManager):
    """Runs every `spawn()`ed callable inline, on the calling thread."""

    def spawn(
        self,
        callable_or_coro: Callable[..., Any] | Any,
        name: str | None = None,
        token: Any = None,
        critical: bool = False,
    ) -> ITaskHandle:
        callable_or_coro()
        return _ImmediateTaskHandle(name or "")

    def get_active_tasks(self) -> list[ITaskHandle]:
        return []

    def shutdown(self, timeout: float = 5.0) -> None:
        pass


class _RecordingTaskManager(ITaskManager):
    """Records what was submitted without running it — proves the handler
    defers to the task manager instead of calling `channel.send()` inline."""

    def __init__(self) -> None:
        self.submitted: list[Callable[[], Any]] = []

    def spawn(
        self,
        callable_or_coro: Callable[..., Any] | Any,
        name: str | None = None,
        token: Any = None,
        critical: bool = False,
    ) -> ITaskHandle:
        self.submitted.append(callable_or_coro)
        return _ImmediateTaskHandle(name or "")

    def get_active_tasks(self) -> list[ITaskHandle]:
        return []

    def shutdown(self, timeout: float = 5.0) -> None:
        pass


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
    handler = NotificationEventHandler(
        bus, _RecordingLogger(), _SynchronousTaskManager()
    )
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
    handler = NotificationEventHandler(
        bus, _RecordingLogger(), _SynchronousTaskManager()
    )
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
    handler = NotificationEventHandler(
        bus, _RecordingLogger(), _SynchronousTaskManager()
    )
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
    handler = NotificationEventHandler(
        bus, _RecordingLogger(), _SynchronousTaskManager()
    )
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
    handler = NotificationEventHandler(
        bus, _RecordingLogger(), _SynchronousTaskManager()
    )
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
    handler = NotificationEventHandler(
        bus, _RecordingLogger(), _SynchronousTaskManager()
    )
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("first")))
    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("first")))
    bus.emit(TaskFailed(task_id="t2", task_name="job-b", error=ValueError("second")))

    assert len(channel.sent) == 2


def test_a_raising_channel_does_not_stop_the_other_channels_or_crash():
    bus = MemoryEventBus()
    logger = _RecordingLogger()
    handler = NotificationEventHandler(bus, logger, _SynchronousTaskManager())
    good_channel = _RecordingChannel()
    handler.add_channel(_RaisingChannel())
    handler.add_channel(good_channel)

    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("boom")))

    assert len(good_channel.sent) == 1
    warnings = logger.lines.get("warning", [])
    assert any("_RaisingChannel" in line for line in warnings), (
        f"the misbehaving channel's failure was never reported: {warnings}"
    )


def test_delivery_goes_through_the_task_manager_not_inline():
    """`PR #259` review finding: a Qt-touching channel (`UiToastNotification
    Channel`) must never be called on whatever thread published the
    triggering event — `TaskFailed` is always a background thread
    (`runtime.tasks.failed`). Proven by *not* running the submitted
    callable: if `_notify()` called `channel.send()` directly instead of
    going through `ITaskManager.spawn()`, `channel.sent` would already be
    populated here."""
    bus = MemoryEventBus()
    task_manager = _RecordingTaskManager()
    handler = NotificationEventHandler(bus, _RecordingLogger(), task_manager)
    channel = _RecordingChannel()
    handler.add_channel(channel)

    bus.emit(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("boom")))

    assert channel.sent == [], (
        "the channel was called before the task manager ran anything — "
        "delivery is not actually deferred"
    )
    assert len(task_manager.submitted) == 1

    task_manager.submitted[0]()

    assert channel.sent == ["Background task 'job-a' (id t1) failed: ValueError: boom"]


def test_delivery_from_a_real_background_publisher_still_goes_through_the_task_manager():
    """`TaskFailed` is published from a real worker thread in production
    (`runtime/tasks/task_manager.py`); this reproduces that shape with a
    real `threading.Thread` rather than assuming `MemoryEventBus.emit()`
    behaves the same from any caller. The channel must still see nothing
    until the recorded callable is actually run."""
    bus = MemoryEventBus()
    task_manager = _RecordingTaskManager()
    handler = NotificationEventHandler(bus, _RecordingLogger(), task_manager)
    channel = _RecordingChannel()
    handler.add_channel(channel)

    worker = threading.Thread(
        target=bus.emit,
        args=(TaskFailed(task_id="t1", task_name="job-a", error=ValueError("boom")),),
    )
    worker.start()
    worker.join()

    assert channel.sent == []
    assert len(task_manager.submitted) == 1
