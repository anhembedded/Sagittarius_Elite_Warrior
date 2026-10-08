"""`EPIC-035I` — the fresh price is the middle of the venue's best bid and ask."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_fresh_price_reader import (
    VenueFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    terms_entry,
)

_VENUE = TradingVenue.SPOT_TESTNET


def _reader(books: dict[str, BestBidAsk]) -> VenueFreshPriceReader:
    terms = FakeOrderEntryTerms(terms_entry(), books=books)
    return VenueFreshPriceReader(
        FakeVenueTradingPorts(fake_venue_ports(_VENUE, order_entry_terms=terms))
    )


def test_the_price_is_the_middle_of_the_best_bid_and_ask() -> None:
    book = BestBidAsk("BTCUSDT", Decimal(100), Decimal(1), Decimal(102), Decimal(1))

    assert _reader({"BTCUSDT": book}).read(_VENUE, "BTCUSDT") == Decimal(101)


def test_a_venue_that_cannot_answer_is_one_named_fault() -> None:
    with pytest.raises(FreshPriceUnavailableError, match="BTCUSDT"):
        _reader({}).read(_VENUE, "BTCUSDT")


def test_a_venue_that_is_not_served_is_one_named_fault() -> None:
    with pytest.raises(FreshPriceUnavailableError):
        _reader({}).read(TradingVenue.FUTURES_TESTNET, "BTCUSDT")
