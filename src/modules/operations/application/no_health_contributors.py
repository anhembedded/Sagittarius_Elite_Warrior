"""The contributors there are before any module declares one (`EPIC-038C`).

An honest empty list: the snapshot then carries the host's identity and state
and no sections, and `status` prints exactly that. The shell's collector of
`declare_health` declarations replaces this binding when `IOperationsRegistry`
exists (see the task's Resume section); the publisher does not change.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
    IHealthContributors,
)


class NoHealthContributors(IHealthContributors):
    def contributors(self) -> tuple[IHealthContributor, ...]:
        return ()
