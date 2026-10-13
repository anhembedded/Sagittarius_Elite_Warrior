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
    HealthContributorDescriptor,
    HealthProbeDescriptor,
    IHealthContributorTable,
    IHealthProbeTable,
    IOperationsRegistry,
    IPreflightCheckTable,
    PreflightCheckDescriptor,
)

logger = logging.getLogger("App.Shell.OperationsRegistry")


class OperationsRegistry(
    IOperationsRegistry,
    IPreflightCheckTable,
    IHealthContributorTable,
    IHealthProbeTable,
):
    """Collects what every module contributes, and hands `operations` a table."""

    def __init__(self) -> None:
        self._preflight: dict[str, PreflightCheckDescriptor] = {}
        self._health: dict[str, HealthContributorDescriptor] = {}
        self._probes: dict[str, HealthProbeDescriptor] = {}

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

    def declare_health(self, descriptor: HealthContributorDescriptor) -> None:
        claimed = self._health.get(descriptor.name)
        if claimed is not None:
            raise ContributionError(
                f"{descriptor.contributor_id!r} declared the health section "
                f"{descriptor.name!r}, which {claimed.contributor_id!r} already "
                "owns. A section name is a key in health.json: rename one."
            )
        self._health[descriptor.name] = descriptor
        logger.debug(
            "[health] section %r declared by %r.",
            descriptor.name,
            descriptor.contributor_id,
        )

    def declare_probe(self, descriptor: HealthProbeDescriptor) -> None:
        claimed = self._probes.get(descriptor.name)
        if claimed is not None:
            raise ContributionError(
                f"{descriptor.contributor_id!r} declared the health probe "
                f"{descriptor.name!r}, which {claimed.contributor_id!r} already "
                "owns. A probe name is an identity in the host's log: rename one."
            )
        self._probes[descriptor.name] = descriptor
        logger.debug(
            "[health] probe %r declared by %r.",
            descriptor.name,
            descriptor.contributor_id,
        )

    # -- the operations-facing side (the tables) ---------------------------

    def health_descriptors(self) -> tuple[HealthContributorDescriptor, ...]:
        return tuple(self._health[name] for name in sorted(self._health))

    def descriptors(self) -> tuple[PreflightCheckDescriptor, ...]:
        return tuple(self._preflight[check_id] for check_id in sorted(self._preflight))

    def probe_descriptors(self) -> tuple[HealthProbeDescriptor, ...]:
        return tuple(self._probes[name] for name in sorted(self._probes))
