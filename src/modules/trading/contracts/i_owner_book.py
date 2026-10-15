"""`EPIC-029` ADR D6 / `EPIC-039D` — what `OwnerBooks` needs of one owner's book.

@details A budgeted owner's book is the venue's evidence about it, kept
current by the venue's fills: Spot's holds an inventory (`OwnerBook`), a
Futures owner's holds a signed position (`OwnerPositionBook`). `OwnerBooks`,
the event buffer and the session state speak only this port, so which book an
owner has is decided once, where the registration installs it, and never by a
branch inside a book.

Not thread-safe: `TradingSessionState` holds the books and calls them under
its lock.

Plausible extensions, each a local change: a Hedge-Mode book (a second
position behind the same port), a Coin-M book (another implementation, chosen
where the registration installs it).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetFacts,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
    PositionDivergence,
)


class IOwnerBook(ABC):
    """One budgeted owner's open orders, holding and recent sends."""

    @property
    @abstractmethod
    def owner_id(self) -> str:
        """Who the budget belongs to."""

    @property
    @abstractmethod
    def symbol(self) -> str:
        """The one symbol the budget binds."""

    @property
    @abstractmethod
    def budget(self) -> OwnerBudget:
        """What the owner may have on the venue at once."""

    @abstractmethod
    def facts_for(self, order: Order, now: datetime) -> OwnerBudgetFacts:
        """@brief What `TradingLimitPolicy` judges `order`, sent at `now`, against."""

    @abstractmethod
    def record_sent(self, order: Order, notional: Decimal, when: datetime) -> None:
        """@brief `order` reached the venue at `when`; `notional` is what it commits."""

    @abstractmethod
    def adopt_open(self, order: Order, notional: Decimal) -> None:
        """@brief `order` was already resting when the budget was registered."""

    @abstractmethod
    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
        trade_id: int | None = None,
    ) -> None:
        """@brief One fill of `order`: `fill` is `(price, quantity)` of this
        fill alone. A fill already counted (`trade_id`) changes nothing."""

    @abstractmethod
    def apply_end(self, order: Order) -> None:
        """@brief `order` is over without filling whole."""

    @abstractmethod
    def held_inventory(self) -> OwnerInventory | None:
        """@brief The base held and its cost, for Emergency Stop's Spot
        liquidation; `None` for a book that holds a position instead."""

    @abstractmethod
    def held_position(self) -> OwnerPosition | None:
        """@brief The signed position and its average entry (`EPIC-039D`);
        `None` for a book that holds an inventory instead."""

    @abstractmethod
    def agrees_with_last_report(self) -> bool:
        """@brief Whether the position the book holds matches, to within a step, the last
        figure the exchange reported for it (`BUG-216`). Pure: it changes nothing and reads no
        venue.
        @return `False` when the exchange has reported no figure yet, when they differ, and for
        a book that holds no position."""

    @abstractmethod
    def cross_check(self, exchange_quantity: Decimal) -> PositionDivergence | None:
        """@brief Compares what the book holds with `exchange_quantity`
        (`positionRisk`'s signed amount on the symbol, zero when flat).
        @return The divergence when it is new, `None` when they agree, the
        book holds no position to compare, or this disagreement was already
        returned."""
