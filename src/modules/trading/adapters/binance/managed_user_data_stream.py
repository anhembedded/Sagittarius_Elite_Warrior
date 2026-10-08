"""`EPIC-035B` — the task lifecycle both Binance user-data streams share.

`SpotUserDataStream` and `FuturesUserDataStream` differ in the socket they open
and the payloads they parse; how a stream task is started, stopped, fenced and
cleared when it ends is one mechanism, kept here once (the audit's H3 lived in
both copies).

  · **The generation fence** (`BUG-094`): bumped by every `start()` and
    `stop()`; a coroutine of an older generation never mutates shared state,
    and never clears a newer task's handle.
  · **The handle is cleared in one place**: the `finally` of the spawned
    coroutine (`_run_until_over`), guarded by the generation. A task that ends
    by itself therefore no longer leaves `start()` answering "already running"
    for ever, and `is_running` reports what is true.
  · **Health**: `stop()` publishes `STOPPED`; the supervisor publishes the rest.

@par Extension cases (`architecture-rule.md` §7.2.1)
A third venue stream is one more subclass: `_run_stream` and a task name.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_stream_supervisor import (
    ReconnectPolicy,
    UserStreamSupervisor,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.UserDataStream")


class ManagedUserDataStream(IUserDataStream, ABC):
    """A user-data stream whose task is started, stopped and cleared here."""

    def __init__(
        self,
        events: VenueEventEmitter,
        task_manager: ITaskManager,
        task_name: str,
        reconnect_policy: ReconnectPolicy,
    ) -> None:
        self._task_manager = task_manager
        self._task_name = task_name
        self._task_handle: ITaskHandle | None = None
        self._token: CancellationToken | None = None
        #: `BUG-094` fencing: bumped on every `start()`/`stop()` so a still-
        #: tearing-down `_run_stream()` never mutates shared state once
        #: superseded (`ITaskHandle.cancel()` only *signals* cooperative
        #: cancellation; it does not wait for the teardown).
        self._generation = 0
        #: Start/stop run on the caller's thread and the task's end on the
        #: engine's: the handle and the generation change under this lock.
        self._lifecycle = threading.Lock()
        #: Retry, backoff and health for any failure.
        self._supervisor = UserStreamSupervisor(task_name, events, reconnect_policy)

    @property
    def is_running(self) -> bool:
        return self._task_handle is not None

    def start(self) -> bool:
        with self._lifecycle:
            if self._task_handle is not None:
                logger.warning("User data stream is already running. Stop it first.")
                return False

            self._token = CancellationToken()
            self._generation += 1
            self._prepare_start()
            logger.info("Starting %s...", self._task_name)
            self._task_handle = self._task_manager.spawn(
                self._run_until_over(self._token, self._generation),
                name=self._task_name,
                token=self._token,
                critical=True,
            )
            return True

    def stop(self) -> bool:
        with self._lifecycle:
            if self._task_handle is None:
                logger.debug("Stop requested but user data stream is not running.")
                return False

            logger.info("Stopping %s...", self._task_name)
            # `BUG-094` — bumped here too, not just in `start()`: fences a
            # still-tearing-down `_run_stream()` the instant `stop()` is
            # called, before any concurrent `start()` even has a chance to run.
            self._generation += 1
            if self._token is not None:
                self._token.cancel()
            self._task_handle.cancel()
            self._task_handle = None
            self._token = None
        self._supervisor.publish_stopped()
        return True

    def _prepare_start(self) -> None:
        """Reset what a stream keeps from one run to the next. Called under
        the lifecycle lock, before the task is spawned."""

    @abstractmethod
    async def _run_stream(self, token: CancellationToken, generation: int) -> None:
        """Connect and read until `token` is cancelled or `generation` is
        superseded; return early when there is nothing to connect with."""

    async def _run_until_over(self, token: CancellationToken, generation: int) -> None:
        try:
            await self._run_stream(token, generation)
        finally:
            with self._lifecycle:
                if generation == self._generation:
                    self._task_handle = None
                    self._token = None
