"""The verified fake's own helpers: a book a test can move, lose and count."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceRateLimitedError,
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)


def _book(price: str) -> BestBidAsk:
    value = Decimal(price)
    return BestBidAsk("BTCUSDT", value, Decimal(1), value, Decimal(1))


def test_quote_moves_the_book_from_the_next_read() -> None:
    fake = FakeOrderEntryTerms(books={"BTCUSDT": _book("100")})

    first = fake.best_bid_ask_for("BTCUSDT")
    fake.quote(_book("130"))

    assert (first.bid_price, fake.best_bid_ask_for("BTCUSDT").bid_price) == (
        Decimal(100),
        Decimal(130),
    )


def test_unquote_makes_the_book_unreadable() -> None:
    fake = FakeOrderEntryTerms(books={"BTCUSDT": _book("100")})

    fake.unquote("BTCUSDT")

    with pytest.raises(MarketPriceUnavailableError):
        fake.best_bid_ask_for("BTCUSDT")


def test_unquote_of_an_unseeded_symbol_is_not_an_error() -> None:
    FakeOrderEntryTerms().unquote("ETHUSDT")


def test_ask_for_a_pause_makes_the_book_a_rate_limited_read_until_it_is_quoted() -> (
    None
):
    fake = FakeOrderEntryTerms(books={"BTCUSDT": _book("100")})

    fake.ask_for_a_pause("BTCUSDT", timedelta(seconds=30))
    with pytest.raises(MarketPriceRateLimitedError) as raised:
        fake.best_bid_ask_for("BTCUSDT")
    fake.quote(_book("101"))

    assert raised.value.retry_after == timedelta(seconds=30)
    assert fake.best_bid_ask_for("BTCUSDT").bid_price == Decimal(101)
