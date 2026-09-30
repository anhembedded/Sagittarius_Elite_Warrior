"""`EPIC-028` ADR D5 — a desk's differences are data, picked by venue."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskNotBuiltError,
    SideLayout,
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    spot_side_figures,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def test_the_spot_desk_offers_limit_and_market_in_two_columns() -> None:
    profile = desk_profile_for(TradingVenue.SPOT_TESTNET)

    assert profile.venue is TradingVenue.SPOT_TESTNET
    assert profile.market_type is MarketType.SPOT
    assert profile.order_types == (OrderType.LIMIT, OrderType.MARKET)
    assert profile.side_layout is SideLayout.TWO_COLUMNS
    assert profile.figures is spot_side_figures
    assert profile.side_label(EntrySide.BUY) == "Buy"
    assert profile.side_label(EntrySide.SELL) == "Sell"
    assert profile.tp_sl_unavailable_reason is not None  # ADR O2


@pytest.mark.parametrize("venue", [TradingVenue.FUTURES_TESTNET, TradingVenue.DISABLED])
def test_a_venue_without_a_desk_is_refused_by_name(venue: TradingVenue) -> None:
    with pytest.raises(DeskNotBuiltError, match=venue.value):
        desk_profile_for(venue)
