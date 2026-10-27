"""`operations` — running the application unattended (`EPIC-038`, decision D4).

**The context's one question:** *how does an operator, or a supervisor, know
this process is alive and well, and make it start and stop cleanly?* It listens
to the other contexts and is depended on by none (`DESIGN_2026-10-09_headless_operation.md`
§3). It declares four dependencies: `bots`, a read of the bots' status report for
`status`, `alerting`, whether a bot's halt has a channel (`EPIC-036G`), `market_data`, the kline ticks the market-data
file records (`EPIC-047H`), and `trading`, the budget caps the host-facts file holds and the bridge reads back
(`EPIC-047C`) and the venue's weight the refresh is held to (`EPIC-047H`).

What it holds today:

  - the health line's format and the host-state vocabulary (`EPIC-038G`);
  - the **health snapshot** (`EPIC-038C`, decision D5): while this copy is the
    writable one, `boot()` writes `state/health.json` and the scheduler rewrites
    it every `HEALTH_INTERVAL_SECONDS`; `shutdown()` writes it once more with the
    host `STOPPED`. A read-only copy writes nothing - it must not overwrite the
    file of the host it is looking at;
  - the **host-facts file** (`EPIC-047B`, decision G7a): the facts only the running host holds -
    the enabled venues, whether each has a key, who holds a symbol's lease, the owner's budget
    caps and the exchange's latest answer for each bot - written to `state/host-facts.json` on a
    change and at a heartbeat, owner-only and atomically, from a worker thread of its own, for a
    second process (the bridge, `EPIC-047C`) that can reach nothing in the host's memory;
  - **what the host serves the VPS tab besides the facts** (`EPIC-047H`, decision record 2026-10-27): the
    **market-data file** (`state/market-data.json`: the last price, the mark and the forming candles of each
    symbol the host already streams, written at most once a second), the **host-reads file**
    (`state/host-reads.json`: the planner inputs, the fills and the symbol rules the host read again) and the
    **refresh** that reads them under a weight ceiling at `ROUTINE` priority, each on a worker thread of its
    own. All three only read: they place, cancel and start nothing, and they open no connection of their own;
  - **`status`**, which reads that file, the instance lock and the bots, and
    opens no port.

  - the `preflight` command with the machine-level checks (`EPIC-038F`): disk
    space, data-root writability and the Python floor; the checks that need the
    exchange are declared by `trading`, the module that knows the key and the
    clock.

  - **control of a running host** (`EPIC-038J`, decision O4, channel A): `bot stop`, `bot pause`
    and `bot resume` write a command file into `state/control/`; the `run` host reads it once a
    second, believes it only if the operating system's permissions vouch for it, dispatches the
    screen's own command once, and audits every step. No port is opened. The module binds the
    operator's `IHostControl` (every copy) and the host's `HostedControlPoller` (registered by
    `run` alone);

  - the **`run` host** (`EPIC-038D`): `main.py run` serves until told to stop. The
    module binds what the host shares with the snapshot machinery - the health cadence
    (interval, host state, the probes before a snapshot and the health line after it),
    the alert-channel answer and the process-memory reader - and `boot()` reads the
    cadence, so a `run` that configured it before the boot gets its own interval and
    states from the same job every writable copy runs.

`subscribe` and `contribute` are inherited no-ops.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributors,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IHealthContributorTable,
    IOperationsRegistry,
    PortResolver,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alerting_status import (
    IAlertingStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.alerting_alert_channels import (
    AlertingAlertChannels,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.data_root_writable_check import (
    DataRootWritableCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.disk_space_check import (
    DiskSpaceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_sink import (
    FileHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_sink import (
    FileHostFactsSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_source import (
    FileHostFactsSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.process_memory import (
    default_process_memory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.python_floor_check import (
    PythonFloorCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.system_operations_clock import (
    SystemOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.declared_health_contributors import (
    DeclaredHealthContributors,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_cadence import (
    HealthCadence,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
    HostIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publishing import (
    HealthPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_section_collector import (
    HealthSectionCollector,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publisher import (
    HostFactsPublisher,
    first_revision_after,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publishing import (
    HostFactsPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status import (
    GetHostStatusQuery,
    GetHostStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.preflight_cli_handler import (
    PreflightCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_cli_handler import (
    RunCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.status_cli_handler import (
    StatusCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.control_bindings import (
    bind_control,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.vps_feed_bindings import (
    bind_vps_feed,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.vps_feed_host import (
    VpsFeedHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    FACTS_HEARTBEAT_SECONDS,
    FACTS_POLL_SECONDS,
    HOST_FACTS_FILE_NAME,
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_source import (
    IHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_codec import (
    IHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_sink import (
    IHostFactsSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_source import (
    IHostFactsSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob, Scheduler

logger = logging.getLogger("App.Operations")

#: How long one contributor may take to answer before its section is `unavailable`.
CONTRIBUTOR_DEADLINE_SECONDS = 2.0


class OperationsModule(BoundedContextModule):
    """The vocabulary of an unattended run, the host's snapshot and `status`."""

    module_id = "operations"

    #: Reads the bots' status report and the alerting module's status (`EPIC-036G`);
    #: checked by `test_module_declarations.py`.
    dependencies: list[str] = ["bots", "alerting", "market_data", "trading"]  # noqa: RUF012 — the Engine reads a plain attribute

    _publishing: HealthPublishing | None = None
    _job: ScheduledJob | None = None
    _facts_publishing: HostFactsPublishing | None = None
    _facts_job: ScheduledJob | None = None
    _feed: VpsFeedHost | None = None

    def register(self, context: IEngineContext) -> None:
        container = context.container
        container.singleton(IOperationsClock, SystemOperationsClock())
        # `EPIC-038D` - what `run` configures before the boot and the module reads in it.
        container.singleton(HealthCadence, HealthCadence())
        # `EPIC-036G` (D5): the alerting module says whether a bot's halt has a channel.
        container.singleton(
            IAlertChannels,
            lambda resolver: AlertingAlertChannels(resolver.resolve(IAlertingStatus)),
        )
        container.singleton(IProcessMemory, default_process_memory())
        container.singleton(
            IHealthSnapshotSource, FileHealthSnapshotSource(_snapshot_path())
        )
        container.singleton(
            IHealthSnapshotSink, FileHealthSnapshotSink(_snapshot_path())
        )
        container.singleton(
            IHealthContributors,
            lambda resolver: DeclaredHealthContributors(
                resolver.resolve(IHealthContributorTable), resolver
            ),
        )
        container.bind(GetHostStatusQuery, GetHostStatusQueryHandler)
        # `EPIC-047B` - the facts only the running host holds, written for a second process.
        container.singleton(IHostFactsCodec, JsonHostFactsCodec())
        container.singleton(
            IHostFactsSink,
            lambda resolver: FileHostFactsSink(
                _host_facts_path(), resolver.resolve(IHostFactsCodec)
            ),
        )
        container.singleton(
            IHostFactsSource,
            lambda resolver: FileHostFactsSource(
                _host_facts_path(), resolver.resolve(IHostFactsCodec)
            ),
        )
        # `EPIC-038J` - control of a running host through the command directory (channel A).
        bind_control(container)
        # `EPIC-047H` - what the host reads and writes for the VPS tab besides the facts.
        bind_vps_feed(container)

    def declare_cli(self, registry: ICliRegistry) -> None:
        registry.declare(
            CliCommandDescriptor(
                name="status", handler=StatusCliHandler, contributor_id=self.module_id
            )
        )
        registry.declare(
            CliCommandDescriptor("preflight", PreflightCliHandler, self.module_id)
        )
        registry.declare(CliCommandDescriptor("run", RunCliHandler, self.module_id))

    def declare_operations(self, registry: IOperationsRegistry) -> None:
        for check_id, factory in (
            ("disk-space", _disk_space),
            ("data-root-writable", _data_root_writable),
            ("python-floor", _python_floor),
        ):
            registry.declare_preflight(
                PreflightCheckDescriptor(check_id, factory, self.module_id)
            )

    def boot(self, context: IEngineContext) -> None:
        container = context.container
        if container.resolve(IInstanceAccess).read_only:
            logger.info("[health-snapshot] not written: this copy is read-only")
            return
        clock = container.resolve(IOperationsClock)
        cadence = container.resolve(HealthCadence)
        publisher = HealthPublisher(
            container.resolve(IHealthContributors),
            container.resolve(IHealthSnapshotSink),
            HealthSectionCollector(CONTRIBUTOR_DEADLINE_SECONDS),
            clock,
            HostIdentity(
                app_version=str(
                    container.resolve(IConfig).get(ConfigKeys.APP_VERSION.value, "")
                ),
                pid=os.getpid(),
                started_at=clock.now(),
                interval_s=cadence.interval_s,
            ),
        )
        publishing = HealthPublishing(publisher, cadence)
        publishing.begin()
        self._publishing = publishing
        self._job = (
            container.resolve(Scheduler)
            .every(seconds=cadence.interval_s)
            .do(publishing.tick)
        )
        logger.info(
            "[health-snapshot] writing %s every %ss",
            _snapshot_path(),
            cadence.interval_s,
        )
        self._begin_host_facts(container, clock)
        self._feed = VpsFeedHost()
        self._feed.begin(context, clock)

    def _begin_host_facts(self, container: IContainer, clock: IOperationsClock) -> None:
        """`EPIC-047B`: the host's facts, looked at every `FACTS_POLL_SECONDS` on a worker thread
        of their own and written on a change or at the heartbeat."""
        publisher = HostFactsPublisher(
            container.resolve(IHostHeldFacts),
            container.resolve(IHostFactsSink),
            clock,
            os.getpid(),
            first_revision_after(
                _header_of_the_file_found(container.resolve(IHostFactsSource)),
                clock.now(),
            ),
        )
        publishing = HostFactsPublishing(publisher)
        publishing.begin()
        self._facts_publishing = publishing
        self._facts_job = (
            container.resolve(Scheduler)
            .every(seconds=FACTS_POLL_SECONDS)
            .do(publishing.tick)
        )
        logger.info(
            "[host-facts] writing %s on a change and at least every %ss",
            _host_facts_path(),
            FACTS_HEARTBEAT_SECONDS,
        )

    def shutdown(self, context: IEngineContext) -> None:
        """Last snapshot with the host `STOPPED`, so `status` can tell a clean
        stop from a crash (a crash leaves `SERVING` and a free lock)."""
        if self._job is not None:
            self._job.cancel()
            self._job = None
        if self._publishing is not None:
            self._publishing.end()
            self._publishing = None
        if self._facts_job is not None:
            self._facts_job.cancel()
            self._facts_job = None
        if self._facts_publishing is not None:
            self._facts_publishing.end()
            self._facts_publishing = None
        if self._feed is not None:
            self._feed.end()
            self._feed = None


def _snapshot_path() -> Path:
    return data_root() / "state" / "health.json"


def _host_facts_path() -> Path:
    return data_root() / "state" / HOST_FACTS_FILE_NAME


def _header_of_the_file_found(source: IHostFactsSource) -> HostFactsHeader | None:
    """The previous run's header, so revisions continue; a file that cannot be read starts afresh."""
    try:
        return source.read_header()
    except HostFactsUnreadableError as failure:
        logger.info("[host-facts] the file found at start-up is replaced: %s", failure)
        return None


def _disk_space(_resolver: PortResolver) -> DiskSpaceCheck:
    root = data_root()
    return DiskSpaceCheck({"data root": root, "log directory": root / "logs"})


def _data_root_writable(_resolver: PortResolver) -> DataRootWritableCheck:
    return DataRootWritableCheck(Path(data_root()))


def _python_floor(_resolver: PortResolver) -> PythonFloorCheck:
    return PythonFloorCheck()
