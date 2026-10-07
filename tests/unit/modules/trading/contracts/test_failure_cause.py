"""`BOT-169` — a failure's key names its venue, so two desks' outages are two messages."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.failure_cause import (
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def test_a_cause_joins_the_venue_and_its_parts() -> None:
    assert (
        failure_cause(TradingVenue.FUTURES_TESTNET, "history", "orders")
        == "trading.futures_testnet.history.orders"
    )


def test_two_venues_never_share_a_cause() -> None:
    assert failure_cause(TradingVenue.SPOT_TESTNET, "account_tabs") != failure_cause(
        TradingVenue.FUTURES_TESTNET, "account_tabs"
    )
