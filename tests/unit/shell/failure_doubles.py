"""Real-interface doubles for the failure sinks' tests (`CS-001`).

Shared by `test_system_failure_log.py`, `test_system_failure_relay.py` and
`tests/unit/shell/test_ui_action_failure.py` (`EPIC-038A` moved the
UI-failure subscription from the shell sinks to the GUI wiring, so the same
sinks are now exercised from two directories). Each subclasses the interface it
stands in for, so a method added to `ILogger`, `ITaskManager`, `ITaskHandle` or
`INotificationChannel` breaks the double at definition time instead of letting
it agree with a call that does not exist (`testing-rule.md` §2).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager


class RecordingLogger(ILogger):
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


class ImmediateTaskHandle(ITaskHandle):
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


class SynchronousTaskManager(ITaskManager):
    """Runs every `spawn()`ed callable inline, on the calling thread."""

    def spawn(
        self,
        callable_or_coro: Callable[..., Any] | Any,
        name: str | None = None,
        token: Any = None,
        critical: bool = False,
    ) -> ITaskHandle:
        callable_or_coro()
        return ImmediateTaskHandle(name or "")

    def get_active_tasks(self) -> list[ITaskHandle]:
        return []

    def shutdown(self, timeout: float = 5.0) -> None:
        pass


class RecordingChannel(INotificationChannel):
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, message: str) -> None:
        self.sent.append(message)
