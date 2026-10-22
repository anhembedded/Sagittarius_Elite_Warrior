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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

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
    #: What each of those orders still owes to fill, where the checkpoint knew it (`BOT-228`). An
    #: id with no entry is one an older checkpoint carried: it stays until the run ends.
    open_order_remaining: Mapping[int, Decimal] = field(default_factory=dict)


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
    #: What each of those orders still owes to fill, as far as it is known (`BOT-228`).
    open_order_remaining: Mapping[int, Decimal]
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
    folded: dict[int, Decimal] = {}
    for trade in history.trade_history(claim.symbol, start.read_from):
        if trade.order_id not in owned or (
            last_trade_id is not None and trade.trade_id <= last_trade_id
        ):
            continue
        state = fold(state, trade)
        replayed.add(trade.trade_id)
        folded[trade.order_id] = folded.get(trade.order_id, Decimal(0)) + trade.quantity
        last_trade_id = trade.trade_id
    still_open = still_open_orders(orders, start, folded)
    return Replayed(
        state,
        frozenset(replayed),
        start.last_trade_id,
        last_trade_id,
        still_open.ids,
        still_open.remaining,
        max(start.read_from, now - READ_OVERLAP),
        len(orders),
    )


@dataclass(frozen=True)
class StillOpen:
    """The owner's orders that may still fill, and what each owes where that is known."""

    ids: frozenset[int]
    remaining: Mapping[int, Decimal]


def still_open_orders[S](
    orders: tuple[OrderRecord, ...],
    start: ReplayStart[S],
    folded: Mapping[int, Decimal],
) -> StillOpen:
    """@brief The owner's orders that may still fill: those read and not over, and those carried
    from the checkpoint that this read did not see end.

    @details An order the window does not list (it was created before the read began) is never
    seen to end by the orders read, so its id used to stay for good (`BOT-228`). The fills this
    read folded for it are subtracted from what the checkpoint says it owed, and the id goes when
    nothing is owed: only the owner's own counted fills can say so, never a guess, so an id is
    never dropped while its order may still fill. An order cancelled with nothing filled leaves
    no fill to say it ended, and stays until the run's checkpoint is discarded; a Grid cancels
    rarely, where it fills all day. An id with no figure stays, too: one an older checkpoint
    carried, and one whose order reports a quantity of zero (a `closePosition` stop)."""
    ended = {
        record.exchange_order_id
        for record in orders
        if is_terminal(record.order.status)
    }
    owed: dict[int, Decimal] = {}
    unknown: set[int] = set()
    for record in orders:
        order_id = record.exchange_order_id
        if order_id in ended:
            continue
        before = start.open_order_remaining.get(order_id)
        if before is None and record.order.quantity <= 0:
            # A quantity of zero is a `closePosition` stop (`protective_stop_request.py`): it
            # closes whatever the position is, so no quantity says when it is done.
            unknown.add(order_id)
            continue
        before = record.order.quantity if before is None else before
        owed[order_id] = before - folded.get(order_id, Decimal(0))
    for order_id in start.open_order_ids - ended - owed.keys():
        before_or_none = start.open_order_remaining.get(order_id)
        if before_or_none is None:
            unknown.add(order_id)
        else:
            owed[order_id] = before_or_none - folded.get(order_id, Decimal(0))
    open_owed = {order_id: left for order_id, left in owed.items() if left > 0}
    return StillOpen(frozenset(open_owed) | unknown, open_owed)
