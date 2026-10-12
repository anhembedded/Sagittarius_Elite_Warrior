"""`IOperationsClock` on the system clock (`EPIC-038C`)."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)


class SystemOperationsClock(IOperationsClock):
    def now(self) -> datetime:
        return datetime.now(UTC)
