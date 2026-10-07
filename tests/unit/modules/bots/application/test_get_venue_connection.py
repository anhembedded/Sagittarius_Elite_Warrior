"""`EPIC-034D` — the Connect step's query answers the venue's own reader."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
    GetVenueConnectionQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_accounts import (
    FakeVenueAccountReader,
    FakeVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def test_the_venues_own_reader_answers_for_the_symbol() -> None:
    spot = FakeVenueAccountReader(
        AccountSource.SPOT_TESTNET, a_venue_account_snapshot()
    )
    futures = FakeVenueAccountReader(
        AccountSource.FUTURES_TESTNET,
        a_venue_account_snapshot(AccountSource.FUTURES_TESTNET),
    )
    handler = GetVenueConnectionQueryHandler(FakeVenueAccounts(spot, futures))

    answer = handler.execute(
        GetVenueConnectionQuery(TradingVenue.SPOT_TESTNET, "ETHUSDT")
    )

    assert answer is spot.read("BTCUSDT")
    assert spot.symbols_read == ["ETHUSDT", "BTCUSDT"]
    assert futures.symbols_read == []


def test_a_venue_that_is_not_served_is_a_named_failure_not_an_exception() -> None:
    handler = GetVenueConnectionQueryHandler(FakeVenueAccounts())

    answer = handler.execute(
        GetVenueConnectionQuery(TradingVenue.SPOT_TESTNET, "BTCUSDT")
    )

    assert answer == ConnectFailure(
        AccountSource.SPOT_TESTNET,
        ConnectionFailureKind.NOT_CONFIGURED,
        "the venue is not enabled",
    )


def test_a_venue_with_no_account_is_a_wiring_bug_that_raises() -> None:
    handler = GetVenueConnectionQueryHandler(FakeVenueAccounts())

    with pytest.raises(ValueError, match="no account"):
        handler.execute(GetVenueConnectionQuery(TradingVenue.DISABLED, "BTCUSDT"))
