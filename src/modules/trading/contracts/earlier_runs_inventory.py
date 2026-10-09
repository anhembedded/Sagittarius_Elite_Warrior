"""`BUG-196` — the base an owner's earlier runs left, which a new run does not trade.

@details A run counts only its own orders (ADR D6): the inventory trading
derives starts at `run_started_at`. Base a halted or stopped run kept is
therefore nobody's, and the owner is told about it instead of finding it
unexplained on the account. Trading answers from the venue's history of the
owner's tagged orders before `until`, capped by the account's free base so a
coin the user sold or moved by hand is not claimed.

The history reaches back `MAX_HISTORY_LOOKBACK` only; an owner older than that
is answered from the part the venue still lists (`counted_from` says where it
starts). "Adopt into this run" is the extension this value is the seam for: a
future command takes the answer's quantity and cost into the next run's
registration, and nothing here changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EarlierRunsRequest:
    """Which owner, and the moment its current (or next) run begins."""

    tag: str
    symbol: str
    base_asset: str
    #: The owner's first possible order (the bot's creation): the read starts
    #: here, or `MAX_HISTORY_LOOKBACK` back when that is nearer.
    since: datetime
    #: Fills before this instant belong to earlier runs.
    until: datetime

    def __post_init__(self) -> None:
        if self.since.tzinfo is None or self.until.tzinfo is None:
            raise ValueError("an earlier-runs request needs timezone-aware instants")


@dataclass(frozen=True, slots=True)
class EarlierRunsInventory:
    """What earlier runs left, or why that is not known."""

    quantity: Decimal = Decimal(0)
    #: The cost basis of `quantity`, in the quote asset.
    cost: Decimal = Decimal(0)
    #: The earliest instant the answer covers.
    counted_from: datetime | None = None
    #: Non-empty when the venue did not answer; the quantity is then zero and
    #: means "not known", not "none".
    unavailable: str = ""

    @property
    def is_known(self) -> bool:
        return not self.unavailable

    @property
    def is_left(self) -> bool:
        return self.quantity > 0
