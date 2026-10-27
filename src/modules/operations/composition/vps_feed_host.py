"""`EPIC-047H` — the workers that serve the VPS tab, started and ended with the host.

@details What `OperationsModule.boot()` starts for a writable copy and `shutdown()` ends: the market-data file
(a listener on the bus and a writer on a worker of its own), the host-reads file (a writer on its own worker)
and the refresh that fills it (`FactsRefreshing`), each as the host's settings allow (`VpsFeedSettings`). A
setting that is off starts nothing of its part. Nothing here reads the exchange itself.
"""

from __future__ import annotations

import logging
import os

from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_exchange_reads import (
    IHostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.wire_document_file import (
    WireDocumentSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.document_publisher import (
    DocumentPublisher,
    first_revision_after,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.facts_refreshing import (
    FactsRefreshing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publishing import (
    HostFactsPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.market_recorder import (
    MarketRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.wire_roots import (
    HOST_READS_DOCUMENT_ROOT,
    MARKET_DATA_DOCUMENT_ROOT,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HOST_READS_FILE_NAME,
    HOST_READS_HEARTBEAT_SECONDS,
    HOST_READS_POLL_SECONDS,
    HostReadsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_tick_publisher import (
    ITickPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    MARKET_DATA_FILE_NAME,
    MARKET_HEARTBEAT_SECONDS,
    MARKET_POLL_SECONDS,
    MarketDataDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_wire_codec import (
    IWireCodec,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob, Scheduler

logger = logging.getLogger("App.Operations")


class VpsFeedHost:
    """`begin()` -> (the workers run) -> `end()`."""

    def __init__(self) -> None:
        self._publishing: list[HostFactsPublishing] = []
        self._jobs: list[ScheduledJob] = []
        self._refreshing: FactsRefreshing | None = None

    def begin(self, context: IEngineContext, clock: IOperationsClock) -> None:
        container = context.container
        settings = container.resolve(VpsFeedSettings)
        codec = container.resolve(IWireCodec)
        scheduler = container.resolve(Scheduler)
        if settings.market_recorder_enabled:
            recorder = container.resolve(MarketRecorder)
            context.event_bus.on(MarketTickEvent, recorder.on_tick)
            self._write(
                scheduler,
                "market-data",
                MARKET_POLL_SECONDS,
                DocumentPublisher(
                    recorder.snapshot,
                    MarketDataDocument,
                    WireDocumentSink(
                        data_root() / "state" / MARKET_DATA_FILE_NAME,
                        codec,
                        MARKET_DATA_DOCUMENT_ROOT,
                    ),
                    clock,
                    os.getpid(),
                    first_revision_after(None, clock.now()),
                    MARKET_HEARTBEAT_SECONDS,
                ),
            )
        if settings.refresh_enabled:
            self._write(
                scheduler,
                "host-reads",
                HOST_READS_POLL_SECONDS,
                DocumentPublisher(
                    container.resolve(IHostExchangeReads).read,
                    HostReadsDocument,
                    WireDocumentSink(
                        data_root() / "state" / HOST_READS_FILE_NAME,
                        codec,
                        HOST_READS_DOCUMENT_ROOT,
                    ),
                    clock,
                    os.getpid(),
                    first_revision_after(None, clock.now()),
                    HOST_READS_HEARTBEAT_SECONDS,
                ),
            )
            self._refreshing = container.resolve(FactsRefreshing)
            self._refreshing.begin()
        logger.info(
            "[vps-feed] market data %s; exchange facts refreshed %s",
            "recorded"
            if settings.market_recorder_enabled
            else "not recorded (setting)",
            f"every {settings.refresh_interval_s} s under {settings.ceiling_pct:g} % of the venue's minute weight"
            if settings.refresh_enabled
            else "never (setting 0)",
        )

    def end(self) -> None:
        for job in self._jobs:
            job.cancel()
        for worker in self._publishing:
            worker.end()
        self._jobs, self._publishing = [], []
        if self._refreshing is not None:
            self._refreshing.end()
            self._refreshing = None

    def _write(
        self,
        scheduler: Scheduler,
        name: str,
        poll_seconds: int,
        publisher: ITickPublisher,
    ) -> None:
        worker = HostFactsPublishing(publisher, name=name)
        worker.begin()
        self._publishing.append(worker)
        self._jobs.append(scheduler.every(seconds=poll_seconds).do(worker.tick))
