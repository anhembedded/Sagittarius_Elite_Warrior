"""`EPIC-029` ADR D6 — an owner's inventory, derived from the venue's
history of its tagged orders.

@details The caller never supplies an inventory. On registration, trading
reads the owner's symbol's order history since the run started, keeps the
orders carrying the owner's tag, and replays their fills from the trade
history (joined by the exchange order id), less the fees charged in the
base asset (`owner_inventory_policy.py`). So:

- a store that claims more than the exchange shows changes nothing;
- base a previous run kept is not counted, since its orders predate
  `run_started_at` (it is reported instead, `earlier_runs_deriver.py`, `BUG-196`);
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
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.checkpointed_replay import (
    InventoryBeyondLookbackError,
    ReplayStart,
    replay_owner_fills,
    still_open_orders,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_inventory_checkpoints import (
    IOwnerInventoryCheckpoints,
    OwnerInventoryCheckpoint,
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

__all__ = [
    "InventoryBeyondLookbackError",
    "OwnerInventoryDerivation",
    "OwnerInventoryDeriver",
    "owner_fill_of",
    "still_open_orders",
]


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
        found = replay_owner_fills(
            registration,
            history,
            now,
            _start_of(registration, checkpoint),
            lambda inventory, trade: inventory_after(
                inventory, owner_fill_of(trade, registration.base_asset)
            ),
        )
        self._checkpoints.save(
            OwnerInventoryCheckpoint(
                tag=registration.tag,
                run_started_at=registration.run_started_at,
                inventory=found.state,
                last_trade_id=found.last_trade_id,
                open_order_ids=found.open_order_ids,
                read_from=found.next_read_from,
                open_order_remaining=found.open_order_remaining,
            )
        )
        logger.info(
            "Derived inventory for %s on %s: %s %s at cost %s (from %s, %d order(s)).",
            registration.tag,
            registration.symbol,
            found.state.quantity,
            registration.base_asset,
            found.state.cost,
            "a checkpoint" if checkpoint is not None else "the run start",
            found.orders_read,
        )
        return OwnerInventoryDerivation(
            found.state, found.counted_trade_ids, found.counted_through
        )

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


def _start_of(
    registration: OwnerBudgetRegistration, checkpoint: OwnerInventoryCheckpoint | None
) -> ReplayStart[OwnerInventory]:
    if checkpoint is None:
        return ReplayStart(EMPTY_INVENTORY, registration.run_started_at)
    return ReplayStart(
        checkpoint.inventory,
        checkpoint.read_from,
        checkpoint.last_trade_id,
        checkpoint.open_order_ids,
        checkpoint.open_order_remaining,
    )


def owner_fill_of(trade: TradeRecord, base_asset: str) -> OwnerFill:
    """@brief `trade` as the owner's inventory takes it: a fee in the base
    asset leaves less base than was traded."""
    base_fee = trade.fee if trade.fee_asset == base_asset else Decimal(0)
    return OwnerFill(trade.side, trade.quantity, trade.quote_quantity, base_fee)
