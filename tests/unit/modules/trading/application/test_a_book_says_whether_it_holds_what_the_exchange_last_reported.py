"""`BUG-216` - a Futures owner's book says whether the gap to the exchange's last report has closed.

@details An `ACCOUNT_UPDATE` can outrun the `ORDER_TRADE_UPDATE` that explains it, and the book then
differs from the exchange for a few seconds. The watch that confirms a divergence before halting asks
this instead of registering the budget again (several weighted reads) when the answer is yes. It is a
query: it changes nothing, so asking it cannot hide a divergence the next report would raise.
"""

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    REGISTRATION,
    STEP,
    order,
)

D = Decimal


def _book() -> OwnerPositionBook:
    return OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP)


def _fill(book: OwnerPositionBook, number: int, quantity: str, trade_id: int) -> None:
    book.apply_fill(
        order(number, OrderSide.BUY, quantity, status=OrderStatus.FILLED),
        (D("60000"), D(quantity)),
        None,
        trade_id,
    )


def test_a_book_the_exchange_has_reported_nothing_for_does_not_agree() -> None:
    assert _book().agrees_with_last_report() is False


def test_the_account_report_that_outran_the_fill_disagrees_until_the_fill_lands() -> (
    None
):
    book = _book()

    book.cross_check(
        D("0.010")
    )  # the account says 0.010; the book has not heard the fill
    assert book.agrees_with_last_report() is False

    _fill(book, 1, "0.010", trade_id=1)  # ...the fill arrives
    assert book.agrees_with_last_report() is True


def test_a_fill_that_arrived_first_agrees_with_the_report_that_follows() -> None:
    book = _book()
    _fill(book, 1, "0.010", trade_id=1)

    book.cross_check(D("0.010"))

    assert book.agrees_with_last_report() is True


def test_a_difference_of_one_step_is_rounding_and_two_steps_are_not() -> None:
    book = _book()
    _fill(book, 1, "0.010", trade_id=1)

    book.cross_check(D("0.010") + STEP)
    assert book.agrees_with_last_report() is True

    book.cross_check(D("0.010") + 2 * STEP)
    assert book.agrees_with_last_report() is False


def test_asking_changes_nothing_so_the_next_report_still_raises_its_divergence() -> (
    None
):
    book = _book()
    book.cross_check(D(0))
    book.agrees_with_last_report()

    divergence = book.cross_check(D("0.010"))

    assert divergence is not None, "the query must not consume or hide a divergence"


def test_a_spot_book_holds_no_position_to_agree() -> None:
    assert OwnerBook(REGISTRATION, EMPTY_INVENTORY).agrees_with_last_report() is False


def test_the_registry_answers_only_for_the_owner_that_holds_the_tag() -> None:
    books = OwnerBooks()
    book = _book()
    books.install(REGISTRATION.tag, book)
    book.cross_check(D(0))

    assert books.reads.agrees_with_last_report(REGISTRATION.tag, REGISTRATION.owner_id)
    assert not books.reads.agrees_with_last_report(REGISTRATION.tag, "another-owner")
    assert not books.reads.agrees_with_last_report("no-such-tag", REGISTRATION.owner_id)
