"""`RunHost` as an Engine hosted service (`EPIC-038D`).

The Engine starts every `IHostedService` at the end of `app.boot()` (after each
module's `boot()` has restored the bots) and stops them in reverse at the start
of `app.stop()` (before the modules shut down and close the workers). The host's
`begin()` and `end()` are exactly those two moments; this class only forwards
them, because application code may not import an Engine type.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host import (
    RunHost,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService


class HostedRunHost(IHostedService):
    def __init__(self, host: RunHost) -> None:
        self._host = host

    def start(self, context: IEngineContext) -> None:
        self._host.begin()

    def stop(self, context: IEngineContext) -> None:
        self._host.end()
