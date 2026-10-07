"""`EPIC-034D` — the fake `IVenueAccounts` keeps the real registry's rules, and
its one extra helper, `answer_with`, does what it says."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    UnknownAccountSourceError,
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

_SPOT = AccountSource.SPOT_TESTNET


def test_it_serves_the_readers_it_was_given_in_order_and_refuses_the_rest() -> None:
    spot = FakeVenueAccountReader(_SPOT, a_venue_account_snapshot())
    accounts = FakeVenueAccounts(spot)

    assert accounts.sources() == (_SPOT,)
    assert accounts.reader(_SPOT) is spot
    with pytest.raises(UnknownAccountSourceError):
        accounts.reader(AccountSource.FUTURES_TESTNET)


def test_answer_with_changes_what_the_next_read_answers_and_reads_are_counted() -> None:
    reader = FakeVenueAccountReader(_SPOT, a_venue_account_snapshot())
    failure = ConnectFailure(_SPOT, ConnectionFailureKind.NETWORK)

    first = reader.read("BTCUSDT")
    reader.answer_with(failure)
    second = reader.read("ETHUSDT")

    assert first == a_venue_account_snapshot()
    assert second is failure
    assert reader.symbols_read == ["BTCUSDT", "ETHUSDT"]
