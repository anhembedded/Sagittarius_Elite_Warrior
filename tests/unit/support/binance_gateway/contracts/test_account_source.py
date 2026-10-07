"""`EPIC-034D` — an account is read from more places than an order may go to."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_TRADING = [v for v in TradingVenue if v is not TradingVenue.DISABLED]


@pytest.mark.parametrize("venue", _TRADING)
def test_every_trading_venue_has_the_account_it_trades_on(venue: TradingVenue) -> None:
    source = AccountSource.for_venue(venue)

    assert source.trading_venue is venue


def test_a_disabled_venue_has_no_account_to_read() -> None:
    with pytest.raises(ValueError, match="no account"):
        AccountSource.for_venue(TradingVenue.DISABLED)


@pytest.mark.parametrize("source", list(AccountSource))
def test_every_source_has_a_title_that_is_not_its_identifier(
    source: AccountSource,
) -> None:
    assert source.venue_title
    assert source.value not in source.venue_title
    assert "_" not in source.venue_title
