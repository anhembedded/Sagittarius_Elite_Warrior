"""What the `run` host asks of the health snapshot (`EPIC-038D`).

The host owns the host state (`BOOTING`, `SERVING`, `DRAINING`, ...); the
snapshot the host publishes says it. The host therefore sets the state and asks
for a snapshot now, at each transition, so `status` learns of a drain within
a moment instead of up to a health interval later. The periodic snapshot, the
probes that run before it and the health line that follows it are the
implementation's business.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)


class IHostHealth(ABC):
    @abstractmethod
    def set_state(self, state: HostState) -> None:
        """What every snapshot from now on says the host is doing."""

    @abstractmethod
    def publish_now(self) -> None:
        """Write a snapshot (and the health line) now. Never raises."""
