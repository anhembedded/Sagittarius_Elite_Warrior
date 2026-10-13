"""`EPIC-039E` — the Connect step's snapshot, in a Futures venue's words, beside Spot's unchanged view."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.account_view import (
    account_view_of,
    margin_view_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import MarginView
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


def test_the_same_snapshot_reads_as_margin_on_a_futures_venue_and_quote_on_spot() -> (
    None
):
    source = AccountSource.FUTURES_TESTNET
    snapshot = a_venue_account_snapshot(source, symbol="BTCUSDT")

    margin = margin_view_of(snapshot)
    quote = account_view_of(snapshot)

    assert margin.available_margin == quote.available_quote == snapshot.available
    assert (margin.venue_title, margin.quote_asset, margin.can_trade) == (
        quote.venue_title,
        quote.quote_asset,
        quote.can_trade,
    )


def test_available_margin_is_never_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        MarginView(Decimal(-1), "USDT", True, "Futures Testnet")
