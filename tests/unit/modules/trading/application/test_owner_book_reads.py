"""`BOT-207` — `OwnerBooks` (lifecycle and writes) and `OwnerBookReads` (what is asked of the books)
are two classes over one state and one lock.

The split moved nine methods out of a class of seventeen; what must not move is the guarantee they
shared: one lock guards the registry and the departed symbols, so a read never sees a book half-way
through a fill, and a read sees what a write did."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book_reads import (
    OwnerBookReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_book import (
    OwnerPositionBook,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    REGISTRATION,
    STEP,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    TAG as POSITION_TAG,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    order as position_order,
)

_TAG = "a3f9c1"
_NOW = datetime(2026, 10, 3, tzinfo=UTC)
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag=_TAG,
    symbol="BTCUSDT",
    run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
    budget=OwnerBudget(10, Decimal(5000), timedelta(0), 60, timedelta(minutes=1)),
)
_FILL = (Decimal(50000), Decimal("0.002"))
_BOUGHT = OwnerInventory(Decimal("0.002"), Decimal(100))
#: Methods one class may have before it must be split (`architecture-rule.md` §5).
_PUBLIC_METHOD_LIMIT = 15


def _order(status: OrderStatus) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-{_TAG}-0000000001"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.002"),
        price=Decimal(50000),
        status=status,
    )


def _public_methods(cls: type) -> list[str]:
    return [
        name
        for name, member in vars(cls).items()
        if not name.startswith("_")
        and (callable(member) or isinstance(member, property))
    ]


def test_each_side_is_within_the_public_method_guideline() -> None:
    assert len(_public_methods(OwnerBooks)) <= _PUBLIC_METHOD_LIMIT
    assert len(_public_methods(OwnerBookReads)) <= _PUBLIC_METHOD_LIMIT


def test_the_read_side_holds_no_write_and_the_write_side_no_read() -> None:
    reads = {
        "holder_of",
        "has_owner_on",
        "facts",
        "position_of",
        "shares",
        "agrees_with_last_report",
    }
    assert set(_public_methods(OwnerBookReads)) == reads
    assert reads.isdisjoint(_public_methods(OwnerBooks))


def test_a_question_that_moves_a_books_state_is_a_write() -> None:
    """`cross_check` keeps what it was told and returns each divergence once (as `take_departure`
    consumes its mark): a handle that only reads must not be able to spend either."""
    writes = {"cross_check_owner", "cross_check", "take_departure"}

    assert writes <= set(_public_methods(OwnerBooks))
    assert writes.isdisjoint(_public_methods(OwnerBookReads))


def test_a_read_sees_what_a_write_did() -> None:
    books = OwnerBooks()
    reads = books.reads
    assert reads.holder_of(_TAG) is None

    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY))
    books.apply_fill(_order(OrderStatus.FILLED), _FILL, None, 7)

    assert reads.holder_of(_TAG) == "bot-1"
    assert reads.shares()[0].inventory == _BOUGHT
    books.clear()
    assert reads.holder_of(_TAG) is None


class _FillInProgress(OwnerBook):
    """A book whose fill is slow: it says it began, then waits to be let finish, so a test can ask
    a question while the fill is half-way."""

    def __init__(self) -> None:
        super().__init__(_REGISTRATION, EMPTY_INVENTORY)
        self.began = threading.Event()
        self.finish = threading.Event()

    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
        trade_id: int | None = None,
    ) -> None:
        self.began.set()
        assert self.finish.wait(timeout=10)
        super().apply_fill(order, fill, fee, trade_id)


def test_a_read_waits_for_a_fill_in_progress_and_sees_the_book_after_it() -> None:
    """One lock guards both sides: asked while a fill is being applied, `facts` answers after it,
    never from the book as the fill is changing it."""
    books = OwnerBooks()
    book = _FillInProgress()
    resting = _order(OrderStatus.NEW)
    book.adopt_open(resting, Decimal(100))
    books.install(_TAG, book)
    answers: list[object] = []
    writer = threading.Thread(
        target=books.apply_fill, args=(_order(OrderStatus.FILLED), _FILL, None, 7)
    )
    reader = threading.Thread(
        target=lambda: answers.append(books.reads.facts(_TAG, "bot-1", resting, _NOW))
    )

    writer.start()
    assert book.began.wait(timeout=10)
    reader.start()
    reader.join(timeout=0.3)
    still_waiting = reader.is_alive()
    book.finish.set()
    writer.join(timeout=10)
    reader.join(timeout=10)

    assert still_waiting, "the read answered while a fill held the lock"
    (facts,) = answers
    assert facts is not None
    assert facts.open_order_count == 0
    assert facts.inventory == _BOUGHT


class _PositionFillInProgress(OwnerPositionBook):
    """A Futures owner's book whose fill is held half-way, as `_FillInProgress` holds Spot's."""

    def __init__(self) -> None:
        super().__init__(REGISTRATION, EMPTY_POSITION, STEP)
        self.began = threading.Event()
        self.finish = threading.Event()

    def apply_fill(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None,
        trade_id: int | None = None,
    ) -> None:
        self.began.set()
        assert self.finish.wait(timeout=10)
        super().apply_fill(order, fill, fee, trade_id)


def test_a_position_read_waits_for_a_futures_fill_in_progress() -> None:
    """The Futures read path under contention too: `position_of` asked while a fill is being
    applied answers after it, never from the position as the fill changes it."""
    books = OwnerBooks()
    book = _PositionFillInProgress()
    books.install(POSITION_TAG, book)
    answers: list[object] = []
    fill = position_order(1, OrderSide.BUY, "0.010", status=OrderStatus.FILLED)
    writer = threading.Thread(
        target=books.apply_fill,
        args=(fill, (Decimal(60000), Decimal("0.010")), None, 5),
    )
    reader = threading.Thread(
        target=lambda: answers.append(books.reads.position_of(POSITION_TAG, "bot-f0"))
    )

    writer.start()
    assert book.began.wait(timeout=10)
    reader.start()
    reader.join(timeout=0.3)
    still_waiting = reader.is_alive()
    book.finish.set()
    writer.join(timeout=10)
    reader.join(timeout=10)

    assert still_waiting, "the read answered while a fill held the lock"
    (position,) = answers
    assert position is not None and position.quantity == Decimal("0.010")
