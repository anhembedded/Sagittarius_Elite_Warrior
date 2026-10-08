"""`EPIC-029E` — what a running Grid bot knows about its own ladder (ADR D9, D10).

The executor's worker is the one writer of this record; the store keeps it
between runs (ADR D4). It is the bot's own account, **never** a safety input:
trading derives the inventory from exchange evidence (D6), and reconciliation
compares this record's inventory with that derivation (`INVENTORY_MISMATCH`).

  · **Levels** carry the lifecycle state of `grid_level_fsm_matrix.py`, the
    order resting there and the recent times an order there ended.
  · **An order's executed quantity is accumulated here** (D10): a fill event
    carries only that fill. `carried_executed` is what an earlier order at the
    level executed before it ended; the re-placed order sends only the rest,
    and the counter order is sized from both.
  · **`buy_quantity`** is what a BUY at the level buys: its share of the
    capital at its own price, rounded down to the step. Every level has one,
    because a SELL level becomes a BUY level when the price comes back.
  · **`paired_buy_price`** on a SELL says what its base cost at the level
    below, so the completed cycle's profit is booked once, when it sells.
  · **`held`** are the counter orders a pause kept back; resume places them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    HOLDS_ORDER,
    LevelEvent,
    LevelState,
    next_level_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ZERO = Decimal(0)


class GridReason(str, Enum):
    """Why a Grid bot halted, stopped or exited (ADR §3.1, §3.3, §3.4). Shown to
    the user beside the state, so each names a fact, not a guess."""

    START_REFUSED = "start_refused"
    LEVEL_KEEPS_ENDING = "level_keeps_ending"
    ORDER_REJECTED = "order_rejected"
    ORDER_REFUSED = "order_refused"
    ORDER_FAILED = "order_failed"
    #: A step outside any order failed (a price, terms or history read).
    TASK_FAILED = "task_failed"
    #: Reconciliation could not read order history; it retries on the next enable.
    HISTORY_UNAVAILABLE = "history_unavailable"
    EXIT_SLICE_FAILED = "exit_slice_failed"
    INVENTORY_MISMATCH = "inventory_mismatch"
    HOLDING_BELOW_INVENTORY = "holding_below_inventory"
    DUPLICATE_LEVEL_ORDER = "duplicate_level_order"
    UNKNOWN_TAGGED_ORDER = "unknown_tagged_order"
    LEASE_HELD = "lease_held"
    SWITCH_OFF = "switch_off"
    #: No price tick for longer than the bot may go without one (`EPIC-035A`):
    #: it cannot watch its stop loss, so it stops placing and takes its ladder off.
    PRICE_FEED_STALE = "price_feed_stale"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    USER_STOP = "user_stop"


@dataclass(frozen=True, slots=True)
class LevelOrder:
    """The order resting at one level, as the bot placed it."""

    client_order_id: str
    side: OrderSide
    price: Decimal
    #: What this exchange order was sent for.
    quantity: Decimal
    executed: Decimal = _ZERO
    base_fee: Decimal = _ZERO
    quote_fee: Decimal = _ZERO
    #: What an earlier order at this level executed before it ended.
    carried_executed: Decimal = _ZERO
    carried_base_fee: Decimal = _ZERO
    #: For a counter SELL: the buy price one level below, and that buy's fees
    #: in the quote asset. `None` for a SELL whose base the opening bought.
    paired_buy_price: Decimal | None = None
    paired_buy_fee_quote: Decimal = _ZERO

    @property
    def is_filled(self) -> bool:
        return self.executed >= self.quantity

    @property
    def total_executed(self) -> Decimal:
        return self.carried_executed + self.executed

    @property
    def total_base_fee(self) -> Decimal:
        return self.carried_base_fee + self.base_fee


@dataclass(frozen=True, slots=True)
class HeldOrder:
    """An order the bot owes a level but has not placed (a pause held it)."""

    level_index: int
    side: OrderSide
    quantity: Decimal
    paired_buy_price: Decimal | None = None
    paired_buy_fee_quote: Decimal = _ZERO
    carried_executed: Decimal = _ZERO
    carried_base_fee: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class RuntimeLevel:
    """One rung, its state and its order."""

    index: int
    price: Decimal
    buy_quantity: Decimal
    state: LevelState = LevelState.EMPTY
    order: LevelOrder | None = None
    #: When orders here ended without filling, most recent last.
    ended_at: tuple[datetime, ...] = ()

    def moved(self, event: LevelEvent, order: LevelOrder | None) -> RuntimeLevel:
        """The level after `event`, holding `order` (`None` when it holds none)."""
        state = next_level_state(self.state, event)
        return replace(self, state=state, order=order if state in HOLDS_ORDER else None)


@dataclass(frozen=True, slots=True)
class GridRuntime:
    """The whole ladder and what it has earned."""

    levels: tuple[RuntimeLevel, ...]
    inventory: Decimal = _ZERO
    cost: Decimal = _ZERO
    realised_profit: Decimal = _ZERO
    completed_cycles: int = 0
    held: tuple[HeldOrder, ...] = ()
    reason: GridReason | None = None
    reason_detail: str = ""
    #: What the stop in progress does with the base: sell it (the user's
    #: choice, or forced by a stop loss or take profit) or keep it. Kept so a
    #: stop that waits through a switch-off or a restart finishes as asked.
    sell_base_on_stop: bool = False

    def level_of(self, client_order_id: str) -> RuntimeLevel | None:
        for level in self.levels:
            if (
                level.order is not None
                and level.order.client_order_id == client_order_id
            ):
                return level
        return None

    def with_level(self, level: RuntimeLevel) -> GridRuntime:
        levels = tuple(
            level if old.index == level.index else old for old in self.levels
        )
        return replace(self, levels=levels)

    def updating_level(
        self, index: int, change: Callable[[RuntimeLevel], RuntimeLevel]
    ) -> GridRuntime:
        return self.with_level(change(self.levels[index]))

    def level_at(self, price: Decimal) -> RuntimeLevel | None:
        return next((level for level in self.levels if level.price == price), None)

    def with_reason(self, reason: GridReason, detail: str) -> GridRuntime:
        return replace(self, reason=reason, reason_detail=detail)

    @property
    def open_orders(self) -> tuple[LevelOrder, ...]:
        return tuple(level.order for level in self.levels if level.order is not None)

    @property
    def average_cost(self) -> Decimal | None:
        return self.cost / self.inventory if self.inventory > 0 else None
