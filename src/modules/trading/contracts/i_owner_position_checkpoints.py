"""`EPIC-039H` — a checkpoint of an owner's position, which trading computed itself, so a
re-derivation reads history only from it onward.

@details The twin of `IOwnerInventoryCheckpoints`, for the signed position of a Futures owner. The
venue's history reaches back `MAX_HISTORY_LOOKBACK` (30 days) and a Futures Grid can run longer; a
checkpoint records the position as derived up to one fill (`last_trade_id`), the owner's orders
that were still open then (their later fills are the owner's too, though the orders predate the
read), and the moment the next read starts from.

A checkpoint belongs to one run of one tag: one whose tag or run start does not match the
registration is discarded and the position is derived again in full. It is never supplied by the
owner (ADR D6).

Plausible extensions, each a local change: a second symbol per owner is a key beside the tag; a
Hedge-Mode pair of positions is a second `OwnerPosition` field.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
)


@dataclass(frozen=True)
class OwnerPositionCheckpoint:
    """An owner's position as derived up to one fill."""

    tag: str
    run_started_at: datetime
    position: OwnerPosition
    #: The last fill counted; `None` when none was.
    last_trade_id: int | None
    #: The exchange ids of the owner's orders still open at the checkpoint.
    open_order_ids: frozenset[int]
    #: Where the next read of the history starts.
    read_from: datetime

    def belongs_to(self, tag: str, run_started_at: datetime) -> bool:
        return self.tag == tag and self.run_started_at == run_started_at


class IOwnerPositionCheckpoints(ABC):
    """Where trading keeps its position checkpoints, one per tag."""

    @abstractmethod
    def load(self, tag: str) -> OwnerPositionCheckpoint | None:
        """@brief The checkpoint saved for `tag`, or `None` when there is none or it cannot be
        read (the position is then derived again in full)."""

    @abstractmethod
    def save(self, checkpoint: OwnerPositionCheckpoint) -> None:
        """@brief Replaces the checkpoint for `checkpoint.tag`."""
