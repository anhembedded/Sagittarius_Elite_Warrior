"""`EPIC-029` ADR D6 — every budgeted owner's book on one venue, by tag.

@details Reached from three threads: the order pool (an owner's order is
judged and recorded), the venue's websocket (a fill or an end is applied
before it is published) and the session handlers (a budget is registered,
or every budget cleared). One lock guards the books; nothing here makes a
network call, so it is held only for the dict and the arithmetic.

`TradingSessionState` holds one instance per venue and clears it whenever
the switch moves: a budget lasts one session (ADR D6 r2). A fill whose
client order id carries no tag, or a tag with no book, is not an owner's
and is ignored here.

A registration reads the venue's history, then installs the book: a fill
reported between those two moments is in neither unless it is held. So a
registration opens an `OwnerEventBuffer` before its reads; every fill and
end of that tag on that symbol is kept in it, and `install` replays the
ones the derivation did not count (by trade id) into the new book under
the same lock that applies the next live event (the `EPIC-029A` review).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
    nothing_counted,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetFacts,
    OwnerInventory,
)


@dataclass(frozen=True)
class OwnerShare:
    """One owner's inventory on its symbol, as Emergency Stop reads it
    before it clears the books."""

    tag: str
    symbol: str
    inventory: OwnerInventory


@dataclass(frozen=True)
class _HeldFill:
    order: Order
    fill: tuple[Decimal, Decimal]
    fee: tuple[Decimal, str] | None
    trade_id: int | None


class OwnerEventBuffer:
    """The fills and ends of one tag on one symbol, held while that tag's
    budget is being registered."""

    def __init__(self, tag: str, symbol: str) -> None:
        self.tag = tag
        self.symbol = symbol
        self._events: list[_HeldFill | Order] = []

    def holds(self, tag: str, order: Order) -> bool:
        return tag == self.tag and order.symbol == self.symbol

    def hold(self, event: _HeldFill | Order) -> None:
        self._events.append(event)

    def replay_into(
        self, book: OwnerBook, counted: Callable[[int | None], bool]
    ) -> None:
        """@brief Applies every held end, and every held fill `counted` does
        not report as already in the book's inventory, in arrival order."""
        for event in self._events:
            if isinstance(event, Order):
                book.apply_end(event)
            elif not counted(event.trade_id):
                book.apply_fill(event.order, event.fill, event.fee, event.trade_id)


class OwnerBooks:
    """The budgeted owners' books on one venue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_tag: dict[str, OwnerBook] = {}
        self._buffers: list[OwnerEventBuffer] = []

    def open_buffer(self, tag: str, symbol: str) -> OwnerEventBuffer:
        """@brief Starts holding `tag`'s fills and ends on `symbol` until the
        buffer is installed with a book or closed."""
        buffer = OwnerEventBuffer(tag, symbol)
        with self._lock:
            self._buffers.append(buffer)
        return buffer

    def close_buffer(self, buffer: OwnerEventBuffer) -> None:
        """@brief Stops holding events for `buffer`; idempotent."""
        with self._lock:
            self._drop(buffer)

    def install(
        self,
        tag: str,
        book: OwnerBook,
        held: OwnerEventBuffer | None = None,
        counted: Callable[[int | None], bool] = nothing_counted,
    ) -> None:
        """@brief Makes `book` the book for `tag`, replacing any before it,
        after replaying into it what `held` kept that `counted` says the
        book's inventory does not hold yet; `held` is closed."""
        with self._lock:
            if held is not None:
                held.replay_into(book, counted)
                self._drop(held)
            self._by_tag[tag] = book

    def clear(self) -> None:
        with self._lock:
            self._by_tag.clear()

    def clear_owner(self, owner_id: str) -> None:
        """@brief Drops `owner_id`'s books; another owner's stay."""
        with self._lock:
            for tag in [t for t, b in self._by_tag.items() if b.owner_id == owner_id]:
                del self._by_tag[tag]

    def holder_of(self, tag: str) -> str | None:
        with self._lock:
            book = self._by_tag.get(tag)
            return None if book is None else book.owner_id

    def facts(
        self, tag: str, owner_id: str, order: Order, now: datetime
    ) -> OwnerBudgetFacts | None:
        """@brief What `order` from `owner_id` is judged against, or `None`
        when `tag` has no book, another owner holds it, or the order is on
        another symbol: a budget binds one symbol, so a tagged order elsewhere
        has none (`OWNER_BUDGET_MISSING`), and the bot's inventory of one coin
        never pays for a sell of another (the `EPIC-029A` review)."""
        with self._lock:
            book = self._by_tag.get(tag)
            if book is None or book.owner_id != owner_id or book.symbol != order.symbol:
                return None
            return book.facts(order.side, order.quantity, now)

    def record_sent(
        self, tag: str, order: Order, notional: Decimal, when: datetime
    ) -> None:
        with self._lock:
            book = self._by_tag.get(tag)
            if book is not None:
                book.record_sent(order, notional, when)

    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
        trade_id: int | None = None,
    ) -> None:
        """@brief Applies one fill to the book of the owner whose tag the
        order carries, if any, and holds it for a registration of that tag
        under way. `trade_id` is the venue's id of this fill."""
        with self._lock:
            self._hold(order, _HeldFill(order, fill, fee, trade_id))
            book = self._book_of(order)
            if book is not None:
                book.apply_fill(order, fill, fee, trade_id)

    def apply_end(self, order: Order) -> None:
        with self._lock:
            self._hold(order, order)
            book = self._book_of(order)
            if book is not None:
                book.apply_end(order)

    def shares(self) -> tuple[OwnerShare, ...]:
        """@brief Every owner's inventory, frozen, sorted by tag."""
        with self._lock:
            return tuple(
                OwnerShare(tag, book.symbol, book.inventory)
                for tag, book in sorted(self._by_tag.items())
            )

    def _hold(self, order: Order, event: _HeldFill | Order) -> None:
        tag = tag_of(str(order.client_order_id))
        if tag is None:
            return
        for buffer in self._buffers:
            if buffer.holds(tag, order):
                buffer.hold(event)

    def _drop(self, buffer: OwnerEventBuffer) -> None:
        self._buffers = [b for b in self._buffers if b is not buffer]

    def _book_of(self, order: Order) -> OwnerBook | None:
        """The book of the owner whose tag `order` carries, on that book's
        symbol only: a tagged fill on another symbol moves no inventory."""
        tag = tag_of(str(order.client_order_id))
        book = None if tag is None else self._by_tag.get(tag)
        return book if book is not None and book.symbol == order.symbol else None
