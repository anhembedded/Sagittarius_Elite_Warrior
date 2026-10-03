"""`EPIC-029` ADR D6 — the owner book follows the owner's orders and fills.

@details The figures are worked by hand in each test's comment and every
one is asserted, so a sign or a missing fee shows up as a wrong number.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
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

_T0 = datetime(2026, 10, 3, 12, tzinfo=UTC)
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag="a3f9c1",
    symbol="BTCUSDT",
    run_started_at=_T0,
    budget=OwnerBudget(
        max_open_orders=10,
        max_exposure_quote=Decimal(1000),
        min_order_spacing=timedelta(milliseconds=250),
        max_orders_per_window=60,
        window=timedelta(minutes=1),
    ),
)


def _order(
    number: int,
    side: OrderSide = OrderSide.BUY,
    quantity: str = "0.002",
    status: OrderStatus = OrderStatus.NEW,
) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-a3f9c1-{number:010x}"),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.LIMIT,
        quantity=Decimal(quantity),
        status=status,
        price=Decimal(50000),
    )


def _book(inventory: OwnerInventory = EMPTY_INVENTORY) -> OwnerBook:
    return OwnerBook(_REGISTRATION, inventory)


def test_a_sent_buy_commits_its_quote_and_counts_as_open() -> None:
    book = _book()
    book.record_sent(_order(1), Decimal(100), _T0)

    facts = book.facts(OrderSide.BUY, Decimal("0.002"), _T0 + timedelta(seconds=1))

    assert (facts.open_order_count, facts.open_buy_quote, facts.orders_in_window) == (
        1,
        Decimal(100),
        1,
    )
    assert facts.time_since_last_order == timedelta(seconds=1)


def test_a_partial_fill_releases_its_share_and_adds_inventory() -> None:
    """Bought 0.0005 of 0.002 at 50 000: a quarter filled, so 75 of the 100
    quote stay committed, and the owner holds 0.0005 that cost 25."""
    book = _book()
    book.record_sent(_order(1), Decimal(100), _T0)

    book.apply_fill(
        _order(1, status=OrderStatus.PARTIALLY_FILLED),
        (Decimal(50000), Decimal("0.0005")),
        (Decimal("0.00001"), "USDT"),
    )

    facts = book.facts(OrderSide.BUY, Decimal(1), _T0)
    assert facts.open_buy_quote == Decimal(75)
    assert book.inventory == OwnerInventory(Decimal("0.0005"), Decimal(25))


def test_a_full_fill_closes_the_order() -> None:
    book = _book()
    book.record_sent(_order(1), Decimal(100), _T0)

    book.apply_fill(
        _order(1, status=OrderStatus.FILLED), (Decimal(50000), Decimal("0.002")), None
    )

    facts = book.facts(OrderSide.BUY, Decimal(1), _T0)
    assert (facts.open_order_count, facts.open_buy_quote) == (0, Decimal(0))
    assert book.inventory == OwnerInventory(Decimal("0.002"), Decimal(100))


def test_a_fee_in_the_base_asset_is_not_inventory() -> None:
    book = _book()
    book.apply_fill(
        _order(1, status=OrderStatus.FILLED),
        (Decimal(50000), Decimal("0.002")),
        (Decimal("0.000002"), "BTC"),
    )
    assert book.inventory.quantity == Decimal("0.001998")


def test_a_fee_in_bnb_leaves_the_inventory_whole() -> None:
    book = _book()
    book.apply_fill(
        _order(1, status=OrderStatus.FILLED),
        (Decimal(50000), Decimal("0.002")),
        (Decimal("0.0001"), "BNB"),
    )
    assert book.inventory.quantity == Decimal("0.002")


def test_a_sell_takes_its_share_of_the_cost() -> None:
    """Held 0.004 that cost 200; selling 0.001 takes a quarter of the cost."""
    book = _book(OwnerInventory(Decimal("0.004"), Decimal(200)))
    book.record_sent(_order(2, OrderSide.SELL, "0.001"), Decimal(51), _T0)

    assert book.facts(OrderSide.SELL, Decimal(1), _T0).open_sell_quantity == Decimal(
        "0.001"
    )
    book.apply_fill(
        _order(2, OrderSide.SELL, "0.001", OrderStatus.FILLED),
        (Decimal(51000), Decimal("0.001")),
        (Decimal("0.051"), "USDT"),
    )

    assert book.inventory == OwnerInventory(Decimal("0.003"), Decimal(150))
    assert book.facts(OrderSide.SELL, Decimal(1), _T0).open_sell_quantity == 0


def test_an_end_releases_the_order() -> None:
    book = _book()
    book.record_sent(_order(1), Decimal(100), _T0)

    book.apply_end(replace(_order(1), status=OrderStatus.CANCELED))

    facts = book.facts(OrderSide.BUY, Decimal(1), _T0)
    assert (facts.open_order_count, facts.open_buy_quote) == (0, Decimal(0))


def test_a_quote_sized_buy_commits_its_quote_until_it_ends() -> None:
    book = _book()
    quote_buy = replace(_order(1, quantity="0"), order_type=OrderType.MARKET)
    book.record_sent(quote_buy, Decimal(300), _T0)

    book.apply_fill(
        replace(quote_buy, status=OrderStatus.PARTIALLY_FILLED),
        (Decimal(50000), Decimal("0.001")),
        None,
    )

    assert book.facts(OrderSide.BUY, Decimal(1), _T0).open_buy_quote == Decimal(300)


def test_sends_leave_the_window_once_it_has_passed() -> None:
    book = _book()
    book.record_sent(_order(1), Decimal(10), _T0)
    book.record_sent(_order(2), Decimal(10), _T0 + timedelta(seconds=30))

    window = _REGISTRATION.budget.window
    assert book.facts(OrderSide.BUY, Decimal(1), _T0 + window).orders_in_window == 1
    assert (
        book.facts(
            OrderSide.BUY, Decimal(1), _T0 + window - timedelta(milliseconds=1)
        ).orders_in_window
        == 2
    )


def test_an_unknown_fill_still_moves_the_inventory() -> None:
    """A fill of the owner's order the book never saw sent (sent before a
    restart, say) is still the owner's evidence."""
    book = _book()
    book.apply_fill(
        _order(9, status=OrderStatus.FILLED), (Decimal(50000), Decimal("0.001")), None
    )
    assert book.inventory == OwnerInventory(Decimal("0.001"), Decimal(50))
