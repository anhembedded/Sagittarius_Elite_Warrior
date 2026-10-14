"""An in-memory `IOwnerPositionCheckpoints`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_position_checkpoints import (
    IOwnerPositionCheckpoints,
    OwnerPositionCheckpoint,
)


class FakeOwnerPositionCheckpoints(IOwnerPositionCheckpoints):
    def __init__(self, *checkpoints: OwnerPositionCheckpoint) -> None:
        self.saved: dict[str, OwnerPositionCheckpoint] = {
            checkpoint.tag: checkpoint for checkpoint in checkpoints
        }

    def load(self, tag: str) -> OwnerPositionCheckpoint | None:
        return self.saved.get(tag)

    def save(self, checkpoint: OwnerPositionCheckpoint) -> None:
        self.saved[checkpoint.tag] = checkpoint
