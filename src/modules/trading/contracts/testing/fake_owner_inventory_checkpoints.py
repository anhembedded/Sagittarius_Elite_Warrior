"""An in-memory `IOwnerInventoryCheckpoints`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_inventory_checkpoints import (
    IOwnerInventoryCheckpoints,
    OwnerInventoryCheckpoint,
)


class FakeOwnerInventoryCheckpoints(IOwnerInventoryCheckpoints):
    def __init__(self, *checkpoints: OwnerInventoryCheckpoint) -> None:
        self.saved: dict[str, OwnerInventoryCheckpoint] = {
            checkpoint.tag: checkpoint for checkpoint in checkpoints
        }

    def load(self, tag: str) -> OwnerInventoryCheckpoint | None:
        return self.saved.get(tag)

    def save(self, checkpoint: OwnerInventoryCheckpoint) -> None:
        self.saved[checkpoint.tag] = checkpoint
