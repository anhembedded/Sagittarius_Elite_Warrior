"""The `run` host listens to its command directory (`EPIC-038J`, decision O4, channel A).

An Engine hosted service registered by `RunCommand` and by nothing else: the desktop app and a
read-only copy never read the directory. At the end of `boot()` - after every module has
restored its bots - it makes the directory private and starts a one-second scheduler job that
runs `HostCommandProcessor.poll`; at the start of `stop()` it cancels the job, so no command is
dispatched into a closing app. A directory it cannot make private means **no control**, logged
once at ERROR; the host serves as it did before this existed.

No port is opened and no thread is started here: the Engine's scheduler is the only clock.
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    prepare_private_directory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_processor import (
    HostCommandProcessor,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob, Scheduler

logger = logging.getLogger("App.Operations.Control")

POLL_INTERVAL_S = 1


class HostedControlPoller(IHostedService):
    def __init__(self, processor: HostCommandProcessor, directory: Path) -> None:
        self._processor = processor
        self._directory = directory
        self._job: ScheduledJob | None = None

    def start(self, context: IEngineContext) -> None:
        problem = prepare_private_directory(self._directory)
        if problem:
            logger.error("[control] off: %s", problem)
            return
        self._job = (
            context.container.resolve(Scheduler)
            .every(seconds=POLL_INTERVAL_S)
            .do(self.poll_once)
        )
        logger.info(
            "[control] accepting bot stop, pause and resume from %s every %d s",
            self._directory,
            POLL_INTERVAL_S,
        )

    def poll_once(self) -> None:
        """What the scheduler runs each second: take the waiting commands, once."""
        self._processor.poll()

    def stop(self, context: IEngineContext) -> None:
        if self._job is not None:
            self._job.cancel()
            self._job = None
