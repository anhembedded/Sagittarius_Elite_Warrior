"""`EPIC-029` ADR D6 — an owner's inventory, derived from the venue's
history of its tagged orders.

@details The caller never supplies an inventory. On registration, trading
reads the owner's symbol's order history since the run started, keeps the
orders carrying the owner's tag, and replays their fills from the trade
history (joined by the exchange order id), less the fees charged in the
base asset (`owner_inventory_policy.py`). So:

- a store that claims more than the exchange shows changes nothing;
- base a previous run kept is not counted, since its orders predate
  `run_started_at`;
- a fee in BNB leaves the inventory whole, and one in the base asset does
  not.

A checkpoint (`IOwnerInventoryCheckpoints`) bounds the read for a run longer
than the venue's 30-day history: the next derivation starts from it, and
also counts the later fills of orders that were open when it was taken.
One whose tag or run start does not match is ignored, and the inventory is
derived in full.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_inventory_checkpoints import (
    IOwnerInventoryCheckpoints,
    OwnerInventoryCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    is_terminal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_inventory_policy import (
    OwnerFill,
    inventory_after,
)

logger = logging.getLogger("App.Trading.OwnerInventory")

#: The next read starts this far before the derivation, so a fill the venue
#: lists a moment late is still read; `last_trade_id` keeps it from being
#: counted twice.
_READ_OVERLAP = timedelta(minutes=1)


@dataclass(frozen=True)
class OwnerInventoryDerivation:
    """The inventory a derivation found, and which of the owner's fills it
    counted, so a fill the venue's stream also reported is counted once
    (`OwnerBooks.install`, the `EPIC-029A` review)."""

    inventory: OwnerInventory
    #: The trade ids this derivation replayed.
    counted_trade_ids: frozenset[int]
    #: The checkpoint's last trade id: every owner fill at or below it was
    #: counted by an earlier derivation. `None` without a checkpoint.
    counted_through: int | None

    def counted(self, trade_id: int | None) -> bool:
        """@brief Whether the fill with `trade_id` is already in the
        inventory. A fill without an id (no venue sends one on Spot) is not."""
        if trade_id is None:
            return False
        if self.counted_through is not None and trade_id <= self.counted_through:
            return True
        return trade_id in self.counted_trade_ids


class InventoryBeyondLookbackError(ValueError):
    """The derivation would have to read further back than the venue's
    history reaches, and no checkpoint covers the gap."""

    def __init__(self, read_from: datetime) -> None:
        super().__init__(
            f"the owner's history starts {read_from.isoformat()}, more than "
            f"{MAX_HISTORY_LOOKBACK.days} days back, and no checkpoint covers it"
        )
        self.read_from = read_from


class OwnerInventoryDeriver:
    """Derives an owner's inventory from exchange evidence."""

    def __init__(self, checkpoints: IOwnerInventoryCheckpoints) -> None:
        self._checkpoints = checkpoints

    def derive(
        self,
        registration: OwnerBudgetRegistration,
        history: IAccountHistoryReader,
        now: datetime,
    ) -> OwnerInventoryDerivation:
        """@brief The inventory of `registration`'s owner at `now`, the fills
        it counted, and a checkpoint saved for the next derivation.
        @throws InventoryBeyondLookbackError The read would start further
        back than the venue's history reaches.
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
        inventory = checkpoint.inventory if checkpoint is not None else EMPTY_INVENTORY
        last_trade_id = checkpoint.last_trade_id if checkpoint is not None else None
        counted_through = last_trade_id
        replayed: set[int] = set()
        for trade in history.trade_history(registration.symbol, read_from):
            if trade.order_id not in owned or (
                last_trade_id is not None and trade.trade_id <= last_trade_id
            ):
                continue
            inventory = inventory_after(inventory, _owner_fill(trade, registration))
            replayed.add(trade.trade_id)
            last_trade_id = trade.trade_id
        self._checkpoints.save(
            OwnerInventoryCheckpoint(
                tag=registration.tag,
                run_started_at=registration.run_started_at,
                inventory=inventory,
                last_trade_id=last_trade_id,
                open_order_ids=_still_open(orders, carried_open),
                read_from=max(read_from, now - _READ_OVERLAP),
            )
        )
        logger.info(
            "Derived inventory for %s on %s: %s %s at cost %s (from %s, %d order(s)).",
            registration.tag,
            registration.symbol,
            inventory.quantity,
            registration.base_asset,
            inventory.cost,
            "a checkpoint" if checkpoint is not None else "the run start",
            len(orders),
        )
        return OwnerInventoryDerivation(inventory, frozenset(replayed), counted_through)

    def _checkpoint_for(
        self, registration: OwnerBudgetRegistration
    ) -> OwnerInventoryCheckpoint | None:
        checkpoint = self._checkpoints.load(registration.tag)
        if checkpoint is None:
            return None
        if not checkpoint.belongs_to(registration.tag, registration.run_started_at):
            logger.info(
                "Inventory checkpoint for %s belongs to another run; deriving in full.",
                registration.tag,
            )
            return None
        return checkpoint


def _owner_fill(trade: TradeRecord, registration: OwnerBudgetRegistration) -> OwnerFill:
    base_fee = trade.fee if trade.fee_asset == registration.base_asset else Decimal(0)
    return OwnerFill(trade.side, trade.quantity, trade.quote_quantity, base_fee)


def _still_open(
    orders: tuple[OrderRecord, ...], carried_open: frozenset[int]
) -> frozenset[int]:
    """The owner's orders that may still fill: those read and not over, and
    those carried from the checkpoint that this read did not see end."""
    ended = {
        record.exchange_order_id
        for record in orders
        if is_terminal(record.order.status)
    }
    read_open = {record.exchange_order_id for record in orders} - ended
    return frozenset(read_open | (carried_open - ended))
