"""`EPIC-029` ADR D6 — a checkpoint of an owner's inventory, which trading
computed itself, so a re-derivation reads history only from it onward.

@details The venue's history reaches back `MAX_HISTORY_LOOKBACK` (30 days),
and a Grid can run longer. A checkpoint records the inventory as derived up
to one fill (`last_trade_id`), the owner's orders that were still open then
(their later fills are the owner's too, though the orders predate the
read), and the moment the next read starts from.

A checkpoint belongs to one run of one tag: one whose tag or run start does
not match the registration is discarded, and the inventory is derived again
in full. It is never supplied by the owner (ADR D6).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)


@dataclass(frozen=True)
class OwnerInventoryCheckpoint:
    """An owner's inventory as derived up to one fill."""

    tag: str
    run_started_at: datetime
    inventory: OwnerInventory
    #: The last fill counted; `None` when none was.
    last_trade_id: int | None
    #: The exchange ids of the owner's orders still open at the checkpoint.
    open_order_ids: frozenset[int]
    #: Where the next read of the history starts.
    read_from: datetime

    def belongs_to(self, tag: str, run_started_at: datetime) -> bool:
        return self.tag == tag and self.run_started_at == run_started_at


class IOwnerInventoryCheckpoints(ABC):
    """Where trading keeps its inventory checkpoints, one per tag."""

    @abstractmethod
    def load(self, tag: str) -> OwnerInventoryCheckpoint | None:
        """@brief The checkpoint saved for `tag`, or `None` when there is
        none or it cannot be read (it is then derived again in full)."""

    @abstractmethod
    def save(self, checkpoint: OwnerInventoryCheckpoint) -> None:
        """@brief Replaces the checkpoint for `checkpoint.tag`."""
