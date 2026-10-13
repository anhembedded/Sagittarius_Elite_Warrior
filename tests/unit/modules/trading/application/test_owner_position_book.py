"""`EPIC-039D` - a Futures owner's book: the position, its budget facts and the
cross-check with `positionRisk`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    nothing_counted,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_book import (
    OwnerPositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    BUDGET,
    NOW,
    REGISTRATION,
    STEP,
    order,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL


def _book(
    counted: Callable[[int | None], bool] = nothing_counted,
) -> OwnerPositionBook:
    return OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP, counted)


def _fill(
    book: OwnerPositionBook,
    number: int,
    side: OrderSide,
    quantity: str,
    price: str,
    trade_id: int | None = None,
    fee: tuple[Decimal, str] | None = None,
) -> None:
    book.apply_fill(
        order(number, side, quantity, status=OrderStatus.FILLED),
        (Decimal(price), Decimal(quantity)),
        fee,
        trade_id,
    )


def test_a_fill_moves_the_position_by_the_one_formula() -> None:
    book = _book()
    _fill(book, 1, BUY, "0.010", "60000")
    _fill(book, 2, SELL, "0.004", "61000", fee=(Decimal("0.2"), "USDT"))

    held = book.held_position()
    assert held is not None
    assert (held.quantity, held.average_entry, held.fees) == (
        Decimal("0.006"),
        Decimal(60000),
        Decimal("0.2"),
    )
    assert book.held_inventory() is None


def test_a_trade_the_exchange_reports_twice_moves_the_position_once() -> None:
    book = _book()
    _fill(book, 1, BUY, "0.010", "60000", trade_id=77)
    _fill(book, 1, BUY, "0.010", "60000", trade_id=77)

    assert book.position.quantity == Decimal("0.010")


def test_a_trade_the_derivation_already_counted_is_not_counted_again() -> None:
    book = _book(counted=lambda trade_id: trade_id == 77)
    _fill(book, 1, BUY, "0.010", "60000", trade_id=77)

    assert book.position.quantity == Decimal(0)


def test_the_facts_leave_reduce_only_orders_out_of_what_could_be_added() -> None:
    book = _book()
    book.record_sent(order(1, BUY, "0.010"), Decimal(600), NOW)
    book.record_sent(order(2, SELL, "0.020", reduce_only=True), Decimal(1200), NOW)
    book.record_sent(order(3, SELL, "0.030"), Decimal(1800), NOW)

    facts = book.facts_for(order(4, SELL, "0.001", reduce_only=True), NOW)

    assert facts.position is not None
    assert (
        facts.position.open_adding_buy_quantity,
        facts.position.open_adding_sell_quantity,
        facts.position.order_reduce_only,
        facts.open_order_count,
    ) == (Decimal("0.010"), Decimal("0.030"), True, 3)


def test_a_filled_order_stops_counting_towards_what_could_be_added() -> None:
    book = _book()
    sent = order(1, BUY, "0.010")
    book.record_sent(sent, Decimal(600), NOW)
    book.apply_fill(
        replace(sent, status=OrderStatus.FILLED),
        (Decimal(60000), Decimal("0.010")),
        None,
        5,
    )

    facts = book.facts_for(order(2, BUY), NOW + timedelta(seconds=1))

    assert facts.position is not None
    assert facts.position.open_adding_buy_quantity == Decimal(0)
    assert facts.open_order_count == 0


def test_a_book_needs_futures_limits_and_a_positive_step() -> None:
    spot_budget = replace(BUDGET, futures=None)
    with pytest.raises(ValueError, match="Futures limits"):
        OwnerPositionBook(
            replace(REGISTRATION, budget=spot_budget), EMPTY_POSITION, STEP
        )
    with pytest.raises(ValueError, match="step"):
        OwnerPositionBook(REGISTRATION, EMPTY_POSITION, Decimal(0))


class TestCrossCheck:
    def test_a_difference_within_one_step_is_rounding(self) -> None:
        book = _book()
        _fill(book, 1, BUY, "0.010", "60000")

        assert book.cross_check(Decimal("0.011")) is None

    def test_a_difference_beyond_one_step_is_a_mismatch_named_with_both_figures(
        self,
    ) -> None:
        book = _book()
        _fill(book, 1, BUY, "0.010", "60000")

        found = book.cross_check(Decimal("0.0111"))

        assert found is not None
        assert found.kind is PositionDivergenceKind.POSITION_MISMATCH
        assert (found.derived, found.exchange, found.symbol, found.tag) == (
            Decimal("0.010"),
            Decimal("0.0111"),
            "BTCUSDT",
            "f0a1b2",
        )

    def test_the_same_disagreement_is_reported_once_and_again_after_they_agree(
        self,
    ) -> None:
        book = _book()
        assert book.cross_check(Decimal("0.5")) is not None
        assert book.cross_check(Decimal("0.5")) is None
        assert book.cross_check(Decimal(0)) is None
        assert book.cross_check(Decimal("0.5")) is not None

    def test_the_exchange_moving_with_no_fill_of_ours_is_unordered(self) -> None:
        book = _book()
        _fill(book, 1, BUY, "0.010", "60000")
        assert book.cross_check(Decimal("0.010")) is None

        found = book.cross_check(Decimal(0))

        assert found is not None
        assert found.kind is PositionDivergenceKind.POSITION_CHANGED_UNORDERED
        assert book.position.quantity == Decimal("0.010")  # reported, not overwritten

    def test_a_fill_of_ours_since_the_last_check_makes_a_disagreement_a_mismatch(
        self,
    ) -> None:
        book = _book()
        assert book.cross_check(Decimal(0)) is None
        _fill(book, 1, BUY, "0.010", "60000")

        found = book.cross_check(Decimal("0.030"))

        assert found is not None
        assert found.kind is PositionDivergenceKind.POSITION_MISMATCH

    def test_a_second_forced_change_is_unordered_too(self) -> None:
        book = _book()
        _fill(book, 1, BUY, "0.030", "60000")
        assert book.cross_check(Decimal("0.030")) is None
        first = book.cross_check(Decimal("0.020"))
        second = book.cross_check(Decimal("0.010"))

        assert first is not None and second is not None
        assert second.kind is PositionDivergenceKind.POSITION_CHANGED_UNORDERED
