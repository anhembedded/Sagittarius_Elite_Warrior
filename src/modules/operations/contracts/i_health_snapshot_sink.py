"""Where a published snapshot goes (`EPIC-038C`).

@par Extension cases
  · a Prometheus textfile or an HTTP push - one more implementation, handed to
    the publisher; the publisher and the contributors do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)


class IHealthSnapshotSink(ABC):
    @abstractmethod
    def publish(self, snapshot: HealthSnapshot) -> None:
        """Make `snapshot` the current one. Atomic: a reader sees the previous
        snapshot or this one, never half of either."""
