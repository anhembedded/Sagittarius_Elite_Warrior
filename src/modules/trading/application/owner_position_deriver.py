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
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.checkpointed_replay import (
    ReplayStart,
    replay_owner_fills,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_position_checkpoints import (
    IOwnerPositionCheckpoints,
    OwnerPositionCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    OwnerPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.owner_position_policy import (
    PositionFill,
    position_after,
)

logger = logging.getLogger("App.Trading.OwnerPosition")


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
        claim: OwnerPositionClaim,
        history: IAccountHistoryReader,
        now: datetime,
    ) -> OwnerPositionDerivation:
        """@brief The position of `claim`'s owner at `now`, the fills it counted, and a
        checkpoint saved for the next derivation.
        @throws InventoryBeyondLookbackError The read would start further back than the venue's
        history reaches, and no checkpoint covers the gap.
        @throws AccountHistoryUnavailableError The venue did not answer."""
        checkpoint = self._checkpoint_for(claim)
        found = replay_owner_fills(
            claim,
            history,
            now,
            _start_of(claim, checkpoint),
            lambda position, trade: position_after(position, position_fill_of(trade)),
        )
        self._checkpoints.save(
            OwnerPositionCheckpoint(
                tag=claim.tag,
                run_started_at=claim.run_started_at,
                position=found.state,
                last_trade_id=found.last_trade_id,
                open_order_ids=found.open_order_ids,
                read_from=found.next_read_from,
                open_order_remaining=found.open_order_remaining,
            )
        )
        logger.info(
            "Derived position for %s on %s: %s at %s (%d fill(s) from %s).",
            claim.tag,
            claim.symbol,
            found.state.quantity,
            found.state.average_entry,
            len(found.counted_trade_ids),
            "a checkpoint" if checkpoint is not None else "the run start",
        )
        return OwnerPositionDerivation(
            found.state, found.counted_trade_ids, found.counted_through
        )

    def _checkpoint_for(
        self, claim: OwnerPositionClaim
    ) -> OwnerPositionCheckpoint | None:
        checkpoint = self._checkpoints.load(claim.tag)
        if checkpoint is None:
            return None
        if not checkpoint.belongs_to(claim.tag, claim.run_started_at):
            logger.info(
                "Position checkpoint for %s belongs to another run; deriving in full.",
                claim.tag,
            )
            return None
        return checkpoint


def _start_of(
    claim: OwnerPositionClaim, checkpoint: OwnerPositionCheckpoint | None
) -> ReplayStart[OwnerPosition]:
    if checkpoint is None:
        return ReplayStart(EMPTY_POSITION, claim.run_started_at)
    return ReplayStart(
        checkpoint.position,
        checkpoint.read_from,
        checkpoint.last_trade_id,
        checkpoint.open_order_ids,
        checkpoint.open_order_remaining,
    )


def position_fill_of(trade: TradeRecord) -> PositionFill:
    """@brief `trade` as the owner's position takes it: a commission in the
    quote asset counts, one in another asset is left out."""
    fee = trade.fee if trade.fee_asset == BUDGET_QUOTE_ASSET else Decimal(0)
    return PositionFill(trade.side, trade.quantity, trade.price, fee)
