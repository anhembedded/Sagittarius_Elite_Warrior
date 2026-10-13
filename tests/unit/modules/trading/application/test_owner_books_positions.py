"""`EPIC-039D` - `OwnerBooks` holds a Futures owner's book beside Spot's, under
the same lock discipline and the same event buffer."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_book import (
    OwnerPositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    OwnerPosition,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    BUDGET,
    REGISTRATION,
    RUN,
    STEP,
    TAG,
    order,
)

BUY = OrderSide.BUY


def _fill(books: OwnerBooks, number: int, quantity: str, trade_id: int | None) -> None:
    books.apply_fill(
        order(number, BUY, quantity, status=OrderStatus.FILLED),
        (Decimal(60000), Decimal(quantity)),
        None,
        trade_id,
    )


def test_a_stream_gap_buffer_replays_uncounted_fills_into_the_position_book() -> None:
    books = OwnerBooks()
    held = books.open_buffer(TAG, "BTCUSDT")
    # Reported while the registration reads the history: 11 is in what it read,
    # 12 is not, and 11 is reported a second time as well.
    _fill(books, 1, "0.010", 11)
    _fill(books, 2, "0.020", 12)
    _fill(books, 1, "0.010", 11)
    derived_position = OwnerPosition(
        Decimal("0.010"), Decimal(60000), Decimal(0), Decimal(0)
    )

    books.install(
        TAG,
        OwnerPositionBook(
            REGISTRATION, derived_position, STEP, lambda trade_id: trade_id == 11
        ),
        held,
        lambda trade_id: trade_id == 11,
    )

    position = books.position_of(TAG, "bot-f0")
    assert position is not None
    assert position.quantity == Decimal("0.030")  # 0.010 derived + 0.020 replayed, once


def test_a_fill_of_another_symbol_or_tag_moves_no_position() -> None:
    books = OwnerBooks()
    books.install(TAG, OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP))

    books.apply_fill(
        order(1, BUY, "0.010", client_order_id="SEW-b00000-0000000001"),
        (Decimal(60000), Decimal("0.010")),
        None,
        5,
    )

    position = books.position_of(TAG, "bot-f0")
    assert position is not None and position.quantity == Decimal(0)


def test_a_futures_owner_has_no_share_in_the_spot_liquidation() -> None:
    books = OwnerBooks()
    spot = OwnerBudgetRegistration(
        "bot-s",
        "b00000",
        "ETHUSDT",
        RUN,
        BUDGET.__class__(
            10, Decimal(1000), BUDGET.min_order_spacing, 60, BUDGET.window
        ),
    )
    books.install(TAG, OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP))
    books.install("b00000", OwnerBook(spot, EMPTY_INVENTORY))

    assert [share.tag for share in books.shares()] == ["b00000"]


def test_a_position_is_read_only_by_the_owner_that_holds_the_tag() -> None:
    books = OwnerBooks()
    books.install(TAG, OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP))

    assert books.position_of(TAG, "someone-else") is None
    assert books.position_of("zzzzzz", "bot-f0") is None


def test_the_cross_check_reaches_every_futures_owner_on_the_symbol_only() -> None:
    books = OwnerBooks()
    books.install(TAG, OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP))

    assert books.cross_check("ETHUSDT", Decimal(5)) == ()
    (found,) = books.cross_check("BTCUSDT", Decimal(5))

    assert found.kind is PositionDivergenceKind.POSITION_MISMATCH
    assert books.cross_check("BTCUSDT", Decimal(5)) == ()  # reported once
