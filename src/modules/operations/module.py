"""`operations` — running the application unattended (`EPIC-038`, decision D4).

**The context's one question:** *how does an operator, or a supervisor, know
this process is alive and well, and make it start and stop cleanly?* It listens
to the other contexts and is depended on by none (`DESIGN_2026-10-09_headless_operation.md`
§3).

It holds the health line's format and host-state vocabulary (`EPIC-038G`) and
the `preflight` command with the machine-level checks (`EPIC-038F`): disk
space, data-root writability and the Python floor. The checks that need the
exchange are declared by `trading`, the module that knows the key and the
clock. The `run` host and `status` arrive with `EPIC-038D` and `038C`. Hooks
not implemented here (`subscribe`, `contribute`) are inherited no-ops.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IOperationsRegistry,
    PortResolver,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.data_root_writable_check import (
    DataRootWritableCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.disk_space_check import (
    DiskSpaceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.python_floor_check import (
    PythonFloorCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.preflight_cli_handler import (
    PreflightCliHandler,
)


class OperationsModule(BoundedContextModule):
    """The vocabulary of an unattended run."""

    module_id = "operations"

    #: Reads no other context's `contracts/`; checked by `test_module_declarations.py`.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context: object) -> None:
        """Nothing to bind yet: the format is a pure function, not a service."""

    def declare_cli(self, registry: ICliRegistry) -> None:
        registry.declare(
            CliCommandDescriptor("preflight", PreflightCliHandler, self.module_id)
        )

    def declare_operations(self, registry: IOperationsRegistry) -> None:
        for check_id, factory in (
            ("disk-space", _disk_space),
            ("data-root-writable", _data_root_writable),
            ("python-floor", _python_floor),
        ):
            registry.declare_preflight(
                PreflightCheckDescriptor(check_id, factory, self.module_id)
            )


def _disk_space(_resolver: PortResolver) -> DiskSpaceCheck:
    root = data_root()
    return DiskSpaceCheck({"data root": root, "log directory": root / "logs"})


def _data_root_writable(_resolver: PortResolver) -> DataRootWritableCheck:
    return DataRootWritableCheck(Path(data_root()))


def _python_floor(_resolver: PortResolver) -> PythonFloorCheck:
    return PythonFloorCheck()
