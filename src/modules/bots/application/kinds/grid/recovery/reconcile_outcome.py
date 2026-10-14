"""What a reconcile step answers when it does not return a ladder (split from
`grid_reconciler.py`, which sat at the 400-line ceiling)."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)


@dataclass(frozen=True, slots=True)
class ReconcileMismatch:
    """A step found the exchange and the ladder disagree, and why."""

    reason: GridReason
    detail: str


@dataclass(frozen=True, slots=True)
class ReconcileWait:
    """The exchange did not answer a read: nothing was changed. What a
    RECOVERING bot shows while it waits for the next try."""

    reason: GridReason
    detail: str
