"""`operations` — running the application unattended (`EPIC-038`, decision D4).

**The context's one question:** *how does an operator, or a supervisor, know
this process is alive and well, and make it start and stop cleanly?* It listens
to the other contexts and is depended on by none (`DESIGN_2026-10-09_headless_operation.md`
§3). It declares two dependencies: `bots`, a read of the bots' status report for
`status`, and `alerting`, whether a bot's halt has a channel (`EPIC-036G`).

What it holds today:

  - the health line's format and the host-state vocabulary (`EPIC-038G`);
  - the **health snapshot** (`EPIC-038C`, decision D5): while this copy is the
    writable one, `boot()` writes `state/health.json` and the scheduler rewrites
    it every `HEALTH_INTERVAL_SECONDS`; `shutdown()` writes it once more with the
    host `STOPPED`. A read-only copy writes nothing - it must not overwrite the
    file of the host it is looking at;
  - **`status`**, which reads that file, the instance lock and the bots, and
    opens no port.

  - the `preflight` command with the machine-level checks (`EPIC-038F`): disk
    space, data-root writability and the Python floor; the checks that need the
    exchange are declared by `trading`, the module that knows the key and the
    clock.

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
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_source import (
    IHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)
from sagittarius_engine.interfaces.i_config import IConfig
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
    dependencies: list[str] = ["bots", "alerting"]  # noqa: RUF012 — the Engine reads a plain attribute

    _publishing: HealthPublishing | None = None
    _job: ScheduledJob | None = None

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

    def shutdown(self, context: IEngineContext) -> None:
        """Last snapshot with the host `STOPPED`, so `status` can tell a clean
        stop from a crash (a crash leaves `SERVING` and a free lock)."""
        if self._job is not None:
            self._job.cancel()
            self._job = None
        if self._publishing is not None:
            self._publishing.end()
            self._publishing = None


def _snapshot_path() -> Path:
    return data_root() / "state" / "health.json"


def _disk_space(_resolver: PortResolver) -> DiskSpaceCheck:
    root = data_root()
    return DiskSpaceCheck({"data root": root, "log directory": root / "logs"})


def _data_root_writable(_resolver: PortResolver) -> DataRootWritableCheck:
    return DataRootWritableCheck(Path(data_root()))


def _python_floor(_resolver: PortResolver) -> PythonFloorCheck:
    return PythonFloorCheck()
