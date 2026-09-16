"""Regression tests for `BUG-126` — a swallowed failure must reach a subscriber.

The bug was not in any line of logic. `SystemErrorFeed` normalised both failure
events correctly and its own test file was green; nothing ever **constructed**
it, so at runtime `UiActionFailedEvent` and `TaskFailed` had zero subscribers —
the exact P1 finding `EPIC-008` §1 was opened to fix, still true two epics
later.

That is why the first test here boots the **real object graph**. A test that
constructs the subscriber itself cannot fail for this bug, however carefully it
asserts afterwards: it supplies the very step production was missing
(`bug-fix-rule.md` §4 on picking the tier the failure actually lives at). The
second and third tests then cover what the subscriber does once it exists.

All **five** assertions of the deleted `test_system_error_feed.py` are
accounted for, and the accounting lives here rather than in the commit message
because this is the file a later reader will check it against:

| deleted assertion | now proved by |
| :--- | :--- |
| a failing UI slot reaches a subscriber | `test_a_failing_ui_slot_is_logged` |
| a failed background task reaches a subscriber | `test_a_failed_background_task_is_logged` |
| both sources share one subscriber | `test_the_real_graph_subscribes_somebody_to_both_failure_events` — one level up, it is the *graph* that must have a subscriber for each |
| `stop()` unsubscribes | `tests/unit/support/ui_kit/test_base_feed.py::test_stop_unsubscribes` |
| `stop()` is idempotent | `tests/unit/support/ui_kit/test_base_feed.py::test_stop_is_idempotent` |

The last two were never this feed's to prove — they are `BaseFeed`'s contract,
asserted on `BaseFeed` itself and again by each of the three feeds that still
subclass it. Nothing was dropped, and the report shape got *stronger* coverage:
`tests/unit/shell/test_system_error_report.py` reaches the two normalisers
directly, where the deleted file reached them through a `QObject`, a
`QtEventBridge` and a Qt signal.

`tests/unit/architecture/test_a_bus_subscriber_is_constructed.py` is the third
half of the fix: it fails on *any* future subscriber that nothing builds, which
is the blind spot rather than this one instance of it.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.system_failure_log import SystemFailureLog
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
    """A real `ILogger`, not a shape assembled from the calls under test.

    `CS-001` is the case study for the alternative: `BUG-124`'s hand-written bus
    double carried `publish` **and** `emit` **and** an invented `subscribe`, so
    it agreed with a call that does not exist. Subclassing the interface means
    this double cannot drift from it — a method added to `ILogger` breaks this
    class at definition time, which is the point (`testing-rule.md` §2).
    """

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


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    config_manager.load_json(os.path.join(_CONFIG_DIR, "app_config.json"))
    config_manager.load_json(os.path.join(_CONFIG_DIR, "user_config.json"))
    app = create_app(config_manager)
    yield app
    app.stop()


def test_the_real_graph_subscribes_somebody_to_both_failure_events(booted_app):
    """`BUG-126` itself. Asserted against the bus the composition root built,
    because "somebody is listening" is a property of the graph and of nothing
    smaller."""
    bus = booted_app.event_bus
    assert isinstance(bus, MemoryEventBus)

    unheard = [
        event_type.__name__
        for event_type in (UiActionFailedEvent, TaskFailed)
        if not bus.get_handlers(event_type)
    ]

    assert unheard == [], (
        f"{unheard} reach nobody after create_app(). A failure published on one "
        "of these leaves no trace anywhere a user or the CI log scan can see — "
        "EPIC-008 §1's P1 finding. Something must subscribe at boot; see "
        "src/shell/system_failure_log.py."
    )


def test_a_failing_ui_slot_is_logged():
    """`safe_ui_action` publishes a full traceback. The summary line carries the
    slot name and the exception; the traceback follows on its own line, because
    `BOT-061` cost a misdirected investigation when only the short message
    survived."""
    bus = MemoryEventBus()
    logger = _RecordingLogger()
    SystemFailureLog(bus, logger)

    bus.emit(
        UiActionFailedEvent(
            function_name="_on_start_clicked",
            exception_type="AttributeError",
            message="'MemoryEventBus' object has no attribute 'publish'",
            traceback="Traceback (most recent call last):\n  ...",
        )
    )

    errors = logger.lines.get("error", [])
    assert any(
        "_on_start_clicked" in line and "AttributeError" in line for line in errors
    ), f"no error line named the failing slot and its exception: {errors}"
    assert any("Traceback (most recent call last)" in line for line in errors), (
        f"the traceback never reached the log: {errors}"
    )


def test_a_failed_background_task_is_logged():
    """The other path, published from a worker thread. Nothing here hops to the
    main thread: a logger is thread-safe, which is why this sink needs no
    `QtEventBridge` and works with no `QApplication` at all."""
    bus = MemoryEventBus()
    logger = _RecordingLogger()
    SystemFailureLog(bus, logger)

    bus.emit(
        TaskFailed(
            task_id="task-7",
            task_name="historical-sync",
            error=ValueError("candle grid drifted"),
        )
    )

    errors = logger.lines.get("error", [])
    assert any(
        "historical-sync" in line and "candle grid drifted" in line for line in errors
    ), f"no error line named the failed task and its cause: {errors}"


def test_nothing_is_logged_at_a_level_the_log_scan_ignores():
    """`ci-local.ps1`'s "Run Log Scan" greps `- (WARNING|ERROR|CRITICAL) -`. A
    failure reported at `INFO` or `DEBUG` would satisfy the two tests above and
    still be invisible to the gate and to `--dev`'s default threshold, which is
    the same class of silence `BUG-126` is about."""
    bus = MemoryEventBus()
    logger = _RecordingLogger()
    SystemFailureLog(bus, logger)

    bus.emit(
        UiActionFailedEvent(
            function_name="_on_click",
            exception_type="RuntimeError",
            message="boom",
            traceback="Traceback...",
        )
    )

    assert set(logger.lines) == {"error"}, (
        "a swallowed failure must be reported at ERROR and nowhere else; got "
        f"{sorted(logger.lines)}"
    )
