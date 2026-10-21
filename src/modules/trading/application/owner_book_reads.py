"""`BOT-207` — what is asked of the budgeted owners' books on one venue: the read side of
`OwnerBooks`.

@details Built over the same `OwnerBookState` as the lifecycle side, so every read takes the lock
a fill or an install takes and sees the books before or after one, never between. Nothing here
changes a book. `TradingSessionState` holds one instance beside `OwnerBooks`; a collaborator that
only reads (the budget check, the reconcilers, Emergency Stop) is handed this, not the side that
writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book_state import (
    OwnerBookState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetFacts,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
    PositionDivergence,
)


@dataclass(frozen=True)
class OwnerShare:
    """One owner's inventory on its symbol, as Emergency Stop reads it
    before it clears the books."""

    tag: str
    symbol: str
    inventory: OwnerInventory


class OwnerBookReads:
    """@brief The read side of the budgeted owners' books on one venue."""

    def __init__(self, state: OwnerBookState) -> None:
        self._state = state

    def holder_of(self, tag: str) -> str | None:
        with self._state.lock:
            book = self._state.by_tag.get(tag)
            return None if book is None else book.owner_id

    def has_owner_on(self, symbol: str) -> bool:
        """@brief Whether a budgeted owner has a book on `symbol`."""
        with self._state.lock:
            return any(book.symbol == symbol for book in self._state.by_tag.values())

    def facts(
        self, tag: str, owner_id: str, order: Order, now: datetime
    ) -> OwnerBudgetFacts | None:
        """@brief What `order` from `owner_id` is judged against, or `None`
        when `tag` has no book, another owner holds it, or the order is on
        another symbol: a budget binds one symbol, so a tagged order elsewhere
        has none (`OWNER_BUDGET_MISSING`), and the bot's inventory of one coin
        never pays for a sell of another (the `EPIC-029A` review)."""
        with self._state.lock:
            book = self._state.by_tag.get(tag)
            if book is None or book.owner_id != owner_id or book.symbol != order.symbol:
                return None
            return book.facts_for(order, now)

    def position_of(self, tag: str, owner_id: str) -> OwnerPosition | None:
        """@brief The signed position `owner_id` holds under `tag`, or `None`
        when `tag` has no book, another owner holds it, or it is a Spot book.
        @details The live read behind `IExposureBook` once `EPIC-039H`'s
        executor needs one (today the bots side reads the registration's
        answer); until then tests are its callers."""
        with self._state.lock:
            book = self._state.by_tag.get(tag)
            if book is None or book.owner_id != owner_id:
                return None
            return book.held_position()

    def shares(self) -> tuple[OwnerShare, ...]:
        """@brief Every Spot owner's inventory, frozen, sorted by tag. A
        Futures owner holds a position, not an inventory: it has no share in
        Emergency Stop's Spot liquidation."""
        with self._state.lock:
            shares = (
                (tag, book.symbol, book.held_inventory())
                for tag, book in sorted(self._state.by_tag.items())
            )
            return tuple(
                OwnerShare(tag, symbol, inventory)
                for tag, symbol, inventory in shares
                if inventory is not None
            )

    def agrees_with_last_report(self, tag: str, owner_id: str) -> bool:
        """@brief Whether `owner_id`'s book under `tag` holds what the exchange last reported
        (`BUG-216`); `False` when `tag` has no book or another owner holds it."""
        with self._state.lock:
            book = self._state.by_tag.get(tag)
            return (
                book is not None
                and book.owner_id == owner_id
                and book.agrees_with_last_report()
            )

    def cross_check_owner(
        self, tag: str, exchange_quantity: Decimal
    ) -> PositionDivergence | None:
        """@brief Compares `tag`'s position with `exchange_quantity`; `None`
        when they agree, `tag` has no book, or it is no Futures book."""
        with self._state.lock:
            book = self._state.by_tag.get(tag)
            return None if book is None else book.cross_check(exchange_quantity)

    def cross_check(
        self, symbol: str, exchange_quantity: Decimal
    ) -> tuple[PositionDivergence, ...]:
        """@brief Compares every Futures owner's position on `symbol` with
        `exchange_quantity` (`positionRisk`), returning each new divergence."""
        with self._state.lock:
            checked = (
                book.cross_check(exchange_quantity)
                for book in self._state.by_tag.values()
                if book.symbol == symbol
            )
            return tuple(found for found in checked if found is not None)
