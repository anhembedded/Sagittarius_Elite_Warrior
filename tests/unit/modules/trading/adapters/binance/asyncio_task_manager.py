"""An `ITaskManager` that runs what it is given as a task on the running loop.

What a user-data stream test needs and a `Mock()` cannot give: a spawned
coroutine that really runs, ends by itself, and leaves a handle the stream
can be asked about. Subclasses the real ports (`testing-rule.md` §2).
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
from sagittarius_engine.runtime.tasks.background_task import TaskState
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class AsyncioTaskHandle(ITaskHandle):
    """A handle over one asyncio task."""

    def __init__(
        self, task: asyncio.Task[None], name: str, token: CancellationToken
    ) -> None:
        self._task = task
        self._name = name
        self._token = token

    @property
    def id(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    @property
    def token(self) -> CancellationToken:
        return self._token

    @property
    def future(self) -> Any | None:
        return self._task

    @property
    def status(self) -> TaskState:
        return TaskState.RUNNING if not self._task.done() else TaskState.COMPLETED

    @property
    def progress(self) -> float:
        return 0.0

    @property
    def task(self) -> asyncio.Task[None]:
        return self._task

    def cancel(self) -> None:
        self._token.cancel()


class AsyncioTaskManager(ITaskManager):
    """Spawns each coroutine as a task and remembers every handle."""

    def __init__(self) -> None:
        self.handles: list[AsyncioTaskHandle] = []

    def spawn(  # type: ignore[override]
        self,
        coro: Coroutine[Any, Any, None],
        name: str,
        token: CancellationToken | None = None,
        critical: bool = False,
    ) -> AsyncioTaskHandle:
        handle = AsyncioTaskHandle(
            asyncio.ensure_future(coro), name, token or CancellationToken()
        )
        self.handles.append(handle)
        return handle

    def get_active_tasks(self) -> list[ITaskHandle]:
        return [h for h in self.handles if not h.task.done()]

    def shutdown(self, timeout: float = 5.0) -> None:
        for handle in self.handles:
            handle.cancel()
