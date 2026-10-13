"""`EPIC-039D` — an owner's signed position, derived from the venue's
history of its tagged orders (ADR D6, `DECISION` O11).

@details The Futures twin of `OwnerInventoryDeriver`, with the same inputs
(tag, symbol, `run_started_at`) and the same shape: read the symbol's order
history since the run started, keep the orders carrying the owner's tag,
replay their fills from the trade history (joined by the exchange order id)
through `position_after`. So:

- a store that claims more than the exchange shows changes nothing;
- a position older than the run is not counted: its fills predate
  `run_started_at` (it is reported as a `ForeignPosition` instead,
  `OwnerPositionRegistrar`);
- a forced close (`autoclose-`) or a fill of an order the owner did not tag is
  not replayed, which is what lets the cross-check see it;
- a commission in the quote asset is counted, one in another asset is not
  converted.

A checkpoint (`IOwnerPositionCheckpoints`, `EPIC-039H`) bounds the read for a run longer than the
venue's 30-day history, exactly as Spot's does for its inventory: the next derivation starts from
it and also counts the later fills of the orders that were open when it was taken. One whose tag
or run start does not match is ignored and the position is derived in full.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
    still_open_orders,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_position_checkpoints import (
    IOwnerPositionCheckpoints,
    OwnerPositionCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    OwnerPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_position_policy import (
    PositionFill,
    position_after,
)

logger = logging.getLogger("App.Trading.OwnerPosition")

#: The next read starts this far before the derivation, so a fill the venue lists a moment late is
#: still read; `last_trade_id` keeps it from being counted twice.
_READ_OVERLAP = timedelta(minutes=1)


@dataclass(frozen=True)
class OwnerPositionDerivation:
    """The position a derivation found, and which of the owner's fills it
    counted, so a fill the venue's stream also reported is counted once
    (`OwnerBooks.install`)."""

    position: OwnerPosition
    #: The trade ids this derivation replayed.
    counted_trade_ids: frozenset[int]
    #: The checkpoint's last trade id: every owner fill at or below it was counted by an earlier
    #: derivation. `None` without a checkpoint.
    counted_through: int | None = None

    @property
    def fill_count(self) -> int:
        return len(self.counted_trade_ids)

    def counted(self, trade_id: int | None) -> bool:
        """@brief Whether the fill with `trade_id` is already in the position."""
        if trade_id is None:
            return False
        if self.counted_through is not None and trade_id <= self.counted_through:
            return True
        return trade_id in self.counted_trade_ids


class OwnerPositionDeriver:
    """Derives an owner's position from exchange evidence."""

    def __init__(self, checkpoints: IOwnerPositionCheckpoints) -> None:
        self._checkpoints = checkpoints

    def derive(
        self,
        registration: OwnerBudgetRegistration,
        history: IAccountHistoryReader,
        now: datetime,
    ) -> OwnerPositionDerivation:
        """@brief The position of `registration`'s owner at `now`, the fills it counted, and a
        checkpoint saved for the next derivation.
        @throws InventoryBeyondLookbackError The read would start further back than the venue's
        history reaches, and no checkpoint covers the gap.
        @throws AccountHistoryUnavailableError The venue did not answer."""
        checkpoint = self._checkpoint_for(registration)
        read_from = (
            checkpoint.read_from
            if checkpoint is not None
            else registration.run_started_at
        )
        if now - read_from > MAX_HISTORY_LOOKBACK:
            raise InventoryBeyondLookbackError(read_from)
        orders = tuple(
            record
            for record in history.order_history(registration.symbol, read_from)
            if tag_of(str(record.order.client_order_id)) == registration.tag
        )
        carried_open = (
            checkpoint.open_order_ids if checkpoint is not None else frozenset()
        )
        owned = {record.exchange_order_id for record in orders} | carried_open
        position = checkpoint.position if checkpoint is not None else EMPTY_POSITION
        last_trade_id = checkpoint.last_trade_id if checkpoint is not None else None
        counted_through = last_trade_id
        replayed: set[int] = set()
        for trade in history.trade_history(registration.symbol, read_from):
            if trade.order_id not in owned or (
                last_trade_id is not None and trade.trade_id <= last_trade_id
            ):
                continue
            position = position_after(position, position_fill_of(trade))
            replayed.add(trade.trade_id)
            last_trade_id = trade.trade_id
        self._checkpoints.save(
            OwnerPositionCheckpoint(
                tag=registration.tag,
                run_started_at=registration.run_started_at,
                position=position,
                last_trade_id=last_trade_id,
                open_order_ids=still_open_orders(orders, carried_open),
                read_from=max(read_from, now - _READ_OVERLAP),
            )
        )
        logger.info(
            "Derived position for %s on %s: %s at %s (%d fill(s) from %s).",
            registration.tag,
            registration.symbol,
            position.quantity,
            position.average_entry,
            len(replayed),
            "a checkpoint" if checkpoint is not None else "the run start",
        )
        return OwnerPositionDerivation(position, frozenset(replayed), counted_through)

    def _checkpoint_for(
        self, registration: OwnerBudgetRegistration
    ) -> OwnerPositionCheckpoint | None:
        checkpoint = self._checkpoints.load(registration.tag)
        if checkpoint is None:
            return None
        if not checkpoint.belongs_to(registration.tag, registration.run_started_at):
            logger.info(
                "Position checkpoint for %s belongs to another run; deriving in full.",
                registration.tag,
            )
            return None
        return checkpoint


def position_fill_of(trade: TradeRecord) -> PositionFill:
    """@brief `trade` as the owner's position takes it: a commission in the
    quote asset counts, one in another asset is left out."""
    fee = trade.fee if trade.fee_asset == BUDGET_QUOTE_ASSET else Decimal(0)
    return PositionFill(trade.side, trade.quantity, trade.price, fee)
