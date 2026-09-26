"""`IMarketDataSync`, implemented over the command the handler already runs.

**What this adds, and what it deliberately does not.** It translates a
published `MarketDataSyncRequest` into `SyncMarketDataCommand` and dispatches
it. That is all. It does not fetch, does not decide where history starts, does
not publish progress — `SyncMarketDataCommandHandler` does all of that, and
duplicating any of it here would give the app two answers to the same question.

**Why it dispatches instead of calling the handler.** Dispatching keeps one
execution path for a sync no matter who asked: the same in-flight guard
(`InFlightSyncGuard`), the same progress events, the same handler construction.
Holding the handler directly would mean this service owned its dependencies —
the very coupling `i_command_dispatcher.py`'s docstring exists to prevent.

**Where it sits.** `application/`, not `adapters/`: an adapter speaks to
something outside the process, and this speaks to the module's own use case.
It is the module's *outward-facing* face of an inward-facing capability, which
is exactly what a published port's implementation is.
"""

from __future__ import annotations

import uuid

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)


class MarketDataSyncService(IMarketDataSync):
    """The module's answer to "make sure this history is on disk"."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def sync(self, request: MarketDataSyncRequest) -> None:
        command = SyncMarketDataCommand(
            symbols=list(request.symbols),
            interval=request.interval,
            market=request.market,
            start_time=request.start_time,
            end_time=request.end_time,
            cancellation_requested=request.cancellation_requested,
            # Generated here when the caller passed none, rather than left to
            # the command's own `default_factory`: the port promises that
            # every started sync carries an id, and `correlation_id=None`
            # would hand the model a literal `None` instead of letting the
            # factory run. The first version of this passed the field through
            # `**kwargs` to keep the factory in play, and mypy was right to
            # reject it — an unpacked `dict[str, str]` lands on whichever
            # parameter position it likes, `days_back_if_empty: int` included.
            correlation_id=request.correlation_id or uuid.uuid4().hex,
        )
        # The result is discarded on purpose: the handler returns `None`, and
        # `IMarketDataSync.sync()` publishes that same nothing.
        self._dispatcher.dispatch(SyncMarketDataCommand, command)
