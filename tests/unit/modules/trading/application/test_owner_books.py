"""`EPIC-029` ADR D6 — `OwnerBooks`, every budgeted owner's book on one venue.

@details Real `OwnerBooks` over real `OwnerBook`s; the fills are what the
venue's stream reports (`VenueEventEmitter` calls `apply_fill`).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)

_TAG = "a3f9c1"
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag=_TAG,
    symbol="BTCUSDT",
    run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
    budget=OwnerBudget(10, Decimal(5000), timedelta(0), 60, timedelta(minutes=1)),
)
_FILL = (Decimal(50000), Decimal("0.002"))
_BOUGHT = OwnerInventory(Decimal("0.002"), Decimal(100))


def _buy(symbol: str = "BTCUSDT", client_id: str = f"SEW-{_TAG}-0000000001") -> Order:
    return Order(
        client_order_id=ClientOrderId(client_id),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
        status=OrderStatus.FILLED,
    )


def _installed() -> OwnerBooks:
    books = OwnerBooks()
    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY))
    return books


def _inventory(books: OwnerBooks) -> OwnerInventory:
    return books.shares()[0].inventory


def test_a_tagged_fill_on_another_symbol_moves_no_inventory() -> None:
    books = _installed()

    books.apply_fill(_buy(symbol="ETHUSDT"), _FILL, None, 1)

    assert _inventory(books) == EMPTY_INVENTORY


def test_a_held_fill_the_derivation_did_not_count_is_replayed() -> None:
    books = OwnerBooks()
    held = books.open_buffer(_TAG, "BTCUSDT")
    books.apply_fill(_buy(), _FILL, None, 7)

    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY), held)

    assert _inventory(books) == _BOUGHT


def test_a_held_fill_the_derivation_counted_is_not_replayed() -> None:
    books = OwnerBooks()
    held = books.open_buffer(_TAG, "BTCUSDT")
    books.apply_fill(_buy(), _FILL, None, 7)

    books.install(
        _TAG, OwnerBook(_REGISTRATION, _BOUGHT), held, lambda trade_id: trade_id == 7
    )

    assert _inventory(books) == _BOUGHT


def test_a_buffer_holds_only_its_tag_on_its_symbol() -> None:
    books = OwnerBooks()
    held = books.open_buffer(_TAG, "BTCUSDT")
    books.apply_fill(_buy(symbol="ETHUSDT"), _FILL, None, 1)
    books.apply_fill(_buy(client_id="SEW-b00000-0000000001"), _FILL, None, 2)
    books.apply_fill(_buy(client_id="web_3f9a1c2b7d4e4b0c"), _FILL, None, 3)

    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY), held)

    assert _inventory(books) == EMPTY_INVENTORY


def test_a_closed_buffer_holds_nothing_more() -> None:
    books = OwnerBooks()
    held = books.open_buffer(_TAG, "BTCUSDT")
    books.close_buffer(held)
    books.apply_fill(_buy(), _FILL, None, 7)

    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY), held)

    assert _inventory(books) == EMPTY_INVENTORY


def test_a_held_fill_still_reaches_the_book_already_installed() -> None:
    """A re-registration of the same owner: the old book stays current until
    the new one replaces it."""
    books = _installed()
    books.open_buffer(_TAG, "BTCUSDT")

    books.apply_fill(_buy(), _FILL, None, 7)

    assert _inventory(books) == _BOUGHT


def test_an_end_held_during_a_registration_releases_the_adopted_order() -> None:
    books = OwnerBooks()
    held = books.open_buffer(_TAG, "BTCUSDT")
    resting = replace(_buy(), status=OrderStatus.NEW, price=Decimal(50000))
    books.apply_end(replace(resting, status=OrderStatus.CANCELED))
    book = OwnerBook(_REGISTRATION, EMPTY_INVENTORY)
    book.adopt_open(resting, Decimal(100))

    books.install(_TAG, book, held)

    facts = books.facts(_TAG, "bot-1", _buy(), datetime(2026, 10, 3, tzinfo=UTC))
    assert facts is not None
    assert facts.open_order_count == 0
