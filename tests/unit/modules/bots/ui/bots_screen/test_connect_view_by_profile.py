"""`EPIC-039J` — what the Connect step says the balance is for.

@details A Spot balance is spent; a Futures balance is lent to positions as margin. The Spot
sentence is the one it always was, pinned whole; the Futures one names margin."""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    connected_view,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


def test_a_spot_account_is_available_as_it_always_said() -> None:
    snapshot = replace(
        a_venue_account_snapshot(available=1500), source=AccountSource.SPOT_TESTNET
    )

    assert connected_view(snapshot).detail == "1,500.00 USDT available · key can trade"


def test_a_futures_account_is_available_as_margin() -> None:
    snapshot = replace(
        a_venue_account_snapshot(available=1500), source=AccountSource.FUTURES_TESTNET
    )

    assert (
        connected_view(snapshot).detail
        == "1,500.00 USDT available as margin · key can trade"
    )
