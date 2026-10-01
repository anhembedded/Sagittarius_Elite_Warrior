"""`EPIC-028O` — the BBO button fills a side's price with the front of its
own queue (a buy the best bid, a sell the best ask), read off the venue's
book on a worker, and drops an answer for a symbol the panel has left."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.best_price_filler import (
    queue_price,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)

from .order_entry_fixtures import SYMBOL, HeldThreadManager
from .order_entry_presenter_fixtures import presented_panel


def _book(bid: str = "99.5", ask: str = "100.5") -> BestBidAsk:
    return BestBidAsk(
        symbol=SYMBOL,
        bid_price=Decimal(bid),
        bid_quantity=Decimal(1),
        ask_price=Decimal(ask),
        ask_quantity=Decimal(1),
    )


@pytest.mark.parametrize(
    ("side", "expected"), [(EntrySide.BUY, "99.5"), (EntrySide.SELL, "100.5")]
)
def test_each_side_joins_its_own_queue(side: EntrySide, expected: str) -> None:
    panel = presented_panel(books={SYMBOL: _book()})
    panel.presenter.show_symbol(SYMBOL)

    panel.vm.use_best_price(side)

    assert panel.vm.entry(side).price == Decimal(expected)
    assert not panel.vm.message_is_error


def test_an_unreadable_book_is_reported_and_the_price_is_kept() -> None:
    panel = presented_panel()  # no book seeded: the read fails
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.set_price(EntrySide.BUY, "98")

    panel.vm.use_best_price(EntrySide.BUY)

    assert panel.vm.entry(EntrySide.BUY).price == 98
    assert panel.vm.message_is_error
    assert panel.vm.message.startswith("Could not read the best price:")
    assert SYMBOL in panel.vm.message


def test_an_empty_side_of_the_book_is_named() -> None:
    panel = presented_panel(books={SYMBOL: _book(bid="0")})
    panel.presenter.show_symbol(SYMBOL)

    panel.vm.use_best_price(EntrySide.BUY)

    assert panel.vm.entry(EntrySide.BUY).price is None
    assert panel.vm.message == "Could not read the best price: the book has no bid yet"


def test_a_book_read_for_a_symbol_the_panel_left_is_dropped() -> None:
    threads = HeldThreadManager()
    panel = presented_panel(threads=threads, books={SYMBOL: _book()})
    panel.presenter.show_symbol(SYMBOL)
    threads.run(0)
    panel.vm.use_best_price(EntrySide.BUY)

    panel.presenter.show_symbol("ETHUSDT")
    threads.run(1)  # BTCUSDT's book answers after the switch

    assert panel.vm.order_symbol == "ETHUSDT"
    assert panel.vm.entry(EntrySide.BUY).price is None


def test_no_book_is_read_before_a_symbol_is_shown() -> None:
    threads = HeldThreadManager()
    panel = presented_panel(threads=threads, books={SYMBOL: _book()})

    panel.vm.use_best_price(EntrySide.BUY)

    assert threads.pending == []


def test_the_queue_price_of_an_empty_side_is_none() -> None:
    assert queue_price(EntrySide.SELL, _book(ask="0")) is None
    assert queue_price(EntrySide.SELL, _book()) == Decimal("100.5")
