"""`EPIC-029` ADR D6 / `EPIC-039H` — the replay of an owner's tagged fills, from a checkpoint or
from the run's start. The one loop under both `OwnerInventoryDeriver` (Spot) and
`OwnerPositionDeriver` (Futures).

@details The venue's history reaches back `MAX_HISTORY_LOOKBACK` (30 days) and a run can be
longer, so a derivation may start from the figures a checkpoint saved. What is the same on every
venue is here: where the read starts, which orders are the owner's (tagged, plus the orders the
checkpoint carried as still open), which fills are skipped as already counted (`last_trade_id`),
which orders are still open for the next checkpoint, and the overlap that keeps a fill listed a
moment late. What differs is the state and how one fill changes it (`fold`): an inventory with its
cost on Spot, a signed position with its entry on Futures. A correction to the window or the
overlap is made once, here.

Plausible extensions, each a local change: another account kind (Coin-M, margin) is one more fold
and one more state; a different overlap is the constant below.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    is_terminal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

#: The next read starts this far before the derivation, so a fill the venue lists a moment late is
#: still read; `last_trade_id` keeps it from being counted twice.
READ_OVERLAP = timedelta(minutes=1)


class InventoryBeyondLookbackError(ValueError):
    """The derivation would have to read further back than the venue's history reaches, and no
    checkpoint covers the gap. (Named for Spot's inventory, where it began; a position raises it
    too, and every caller already catches it by this name.)"""

    def __init__(self, read_from: datetime) -> None:
        super().__init__(
            f"the owner's history starts {read_from.isoformat()}, more than "
            f"{MAX_HISTORY_LOOKBACK.days} days back, and no checkpoint covers it"
        )
        self.read_from = read_from


@dataclass(frozen=True)
class ReplayStart[S]:
    """Where a derivation starts: the run's beginning, or what a checkpoint saved."""

    state: S
    read_from: datetime
    last_trade_id: int | None = None
    open_order_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class Replayed[S]:
    """What a replay found, and what the next checkpoint holds."""

    state: S
    #: The trade ids this replay counted.
    counted_trade_ids: frozenset[int]
    #: The start's last trade id: every owner fill at or below it was counted before.
    counted_through: int | None
    #: The last fill counted, for the next checkpoint (`None` when none was ever).
    last_trade_id: int | None
    #: The owner's orders that may still fill, for the next checkpoint.
    open_order_ids: frozenset[int]
    #: Where the next read starts.
    next_read_from: datetime
    #: How many of the owner's orders this read saw.
    orders_read: int


def replay_owner_fills[S](
    claim: OwnerPositionClaim,
    history: IAccountHistoryReader,
    now: datetime,
    start: ReplayStart[S],
    fold: Callable[[S, TradeRecord], S],
) -> Replayed[S]:
    """@brief The owner's state at `now`, folded from `start` over the owner's fills.
    @throws InventoryBeyondLookbackError The read would start further back than the venue's
    history reaches.
    @throws AccountHistoryUnavailableError The venue did not answer."""
    if now - start.read_from > MAX_HISTORY_LOOKBACK:
        raise InventoryBeyondLookbackError(start.read_from)
    orders = tuple(
        record
        for record in history.order_history(claim.symbol, start.read_from)
        if tag_of(str(record.order.client_order_id)) == claim.tag
    )
    owned = {record.exchange_order_id for record in orders} | start.open_order_ids
    state = start.state
    last_trade_id = start.last_trade_id
    replayed: set[int] = set()
    for trade in history.trade_history(claim.symbol, start.read_from):
        if trade.order_id not in owned or (
            last_trade_id is not None and trade.trade_id <= last_trade_id
        ):
            continue
        state = fold(state, trade)
        replayed.add(trade.trade_id)
        last_trade_id = trade.trade_id
    return Replayed(
        state,
        frozenset(replayed),
        start.last_trade_id,
        last_trade_id,
        still_open_orders(orders, start.open_order_ids),
        max(start.read_from, now - READ_OVERLAP),
        len(orders),
    )


def still_open_orders(
    orders: tuple[OrderRecord, ...], carried_open: frozenset[int]
) -> frozenset[int]:
    """The owner's orders that may still fill: those read and not over, and those carried from the
    checkpoint that this read did not see end."""
    ended = {
        record.exchange_order_id
        for record in orders
        if is_terminal(record.order.status)
    }
    read_open = {record.exchange_order_id for record in orders} - ended
    return frozenset(read_open | (carried_open - ended))
