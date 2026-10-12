"""The shell's side of what modules contribute to running unattended (`EPIC-038F`).

`IOperationsRegistry` is what a module sees: declarations in, nothing out.
`IPreflightCheckTable` is what `operations` sees: the finished table, nothing to
add. One object satisfies both, so each side names only the half it may use —
the shape `CliRegistry` has, for the same reason (`architecture-rule.md` §7).

**An id may be claimed once.** A check id is an identity (`--skip <id>` has to
mean one check), so a second claim raises `ContributionError` naming both
modules at boot, not on the first `preflight` an operator runs.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IOperationsRegistry,
    IPreflightCheckTable,
    PreflightCheckDescriptor,
)

logger = logging.getLogger("App.Shell.OperationsRegistry")


class OperationsRegistry(IOperationsRegistry, IPreflightCheckTable):
    """Collects what every module contributes, and hands `operations` a table."""

    def __init__(self) -> None:
        self._preflight: dict[str, PreflightCheckDescriptor] = {}

    # -- the module-facing side (IOperationsRegistry) ----------------------

    def declare_preflight(self, descriptor: PreflightCheckDescriptor) -> None:
        claimed = self._preflight.get(descriptor.check_id)
        if claimed is not None:
            raise ContributionError(
                f"{descriptor.contributor_id!r} declared the pre-flight check "
                f"{descriptor.check_id!r}, which {claimed.contributor_id!r} already "
                "owns. A check id is an identity (`--skip` names it): rename one."
            )
        self._preflight[descriptor.check_id] = descriptor
        logger.debug(
            "[preflight] check %r declared by %r.",
            descriptor.check_id,
            descriptor.contributor_id,
        )

    # -- the operations-facing side (IPreflightCheckTable) -----------------

    def descriptors(self) -> tuple[PreflightCheckDescriptor, ...]:
        return tuple(self._preflight[check_id] for check_id in sorted(self._preflight))
