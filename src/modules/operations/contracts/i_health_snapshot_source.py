"""Where a reader gets the snapshot a host last published (`EPIC-038C`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)


class HealthSnapshotUnreadableError(ValueError):
    """There is a snapshot and it cannot be understood (bad JSON, an unknown schema)."""


class IHealthSnapshotSource(ABC):
    @abstractmethod
    def read(self) -> HealthSnapshot | None:
        """The last published snapshot, or `None` when none was ever published.

        @raise HealthSnapshotUnreadableError A snapshot exists and is not one
            this build understands."""
