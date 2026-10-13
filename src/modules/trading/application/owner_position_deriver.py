"""`EPIC-039D` — an owner's signed position, derived from the venue's history
of its tagged orders (ADR D6, `DECISION` O11).

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

**No checkpoint yet:** a run older than the venue's history window
(`MAX_HISTORY_LOOKBACK`) cannot be derived and is refused, as Spot's is without
one (`InventoryBeyondLookbackError`). Spot's `IOwnerInventoryCheckpoints` bounds
the read for a long run; a position checkpoint is the same idea behind a second
port, left for `EPIC-039H`, which is the first to run a Futures bot for weeks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    MAX_HISTORY_LOOKBACK,
    IAccountHistoryReader,
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


@dataclass(frozen=True)
class OwnerPositionDerivation:
    """The position a derivation found, and which of the owner's fills it
    counted, so a fill the venue's stream also reported is counted once
    (`OwnerBooks.install`)."""

    position: OwnerPosition
    #: The trade ids this derivation replayed.
    counted_trade_ids: frozenset[int]

    @property
    def fill_count(self) -> int:
        return len(self.counted_trade_ids)

    def counted(self, trade_id: int | None) -> bool:
        """@brief Whether the fill with `trade_id` is already in the position."""
        return trade_id is not None and trade_id in self.counted_trade_ids


class OwnerPositionDeriver:
    """Derives an owner's position from exchange evidence."""

    def derive(
        self,
        registration: OwnerBudgetRegistration,
        history: IAccountHistoryReader,
        now: datetime,
    ) -> OwnerPositionDerivation:
        """@brief The position of `registration`'s owner at `now`.
        @throws InventoryBeyondLookbackError The run started further back than
        the venue's history reaches.
        @throws AccountHistoryUnavailableError The venue did not answer."""
        read_from = registration.run_started_at
        if now - read_from > MAX_HISTORY_LOOKBACK:
            raise InventoryBeyondLookbackError(read_from)
        owned = {
            record.exchange_order_id
            for record in history.order_history(registration.symbol, read_from)
            if tag_of(str(record.order.client_order_id)) == registration.tag
        }
        position = EMPTY_POSITION
        replayed: set[int] = set()
        for trade in history.trade_history(registration.symbol, read_from):
            if trade.order_id not in owned:
                continue
            position = position_after(position, position_fill_of(trade))
            replayed.add(trade.trade_id)
        logger.info(
            "Derived position for %s on %s: %s at %s (%d fill(s) since %s).",
            registration.tag,
            registration.symbol,
            position.quantity,
            position.average_entry,
            len(replayed),
            read_from.isoformat(),
        )
        return OwnerPositionDerivation(position, frozenset(replayed))


def position_fill_of(trade: TradeRecord) -> PositionFill:
    """@brief `trade` as the owner's position takes it: a commission in the
    quote asset counts, one in another asset is left out."""
    fee = trade.fee if trade.fee_asset == BUDGET_QUOTE_ASSET else Decimal(0)
    return PositionFill(trade.side, trade.quantity, trade.price, fee)
