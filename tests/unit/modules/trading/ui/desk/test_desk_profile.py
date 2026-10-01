"""`EPIC-028` ADR D5 — a desk's differences are data, picked by venue."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskNotBuiltError,
    HeldTab,
    SideLayout,
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_rules import (
    futures_side_figures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    spot_side_figures,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def test_the_spot_desk_offers_limit_market_and_stop_limit_in_two_columns() -> None:
    profile = desk_profile_for(TradingVenue.SPOT_TESTNET)

    assert profile.venue is TradingVenue.SPOT_TESTNET
    assert profile.market_type is MarketType.SPOT
    assert profile.order_types == (
        OrderType.LIMIT,
        OrderType.MARKET,
        OrderType.STOP_LIMIT,
    )
    assert profile.side_layout is SideLayout.TWO_COLUMNS
    assert profile.figures is spot_side_figures
    assert profile.side_label(EntrySide.BUY) == "Buy"
    assert profile.side_label(EntrySide.SELL) == "Sell"
    assert profile.tp_sl_unavailable_reason is not None  # ADR O2


def test_a_venue_without_a_market_has_no_desk() -> None:
    """`FUTURES_TESTNET` was refused here too until `EPIC-028I` built its
    desk; `DISABLED` trades no market."""
    with pytest.raises(DeskNotBuiltError, match=TradingVenue.DISABLED.value):
        desk_profile_for(TradingVenue.DISABLED)


def test_the_futures_desk_sizes_long_and_short_with_its_own_controls() -> None:
    """`EPIC-028I` — Buy/Long and Sell/Short sized by the Futures estimates,
    Stop-limit offered (ADR O3), TP/SL available, Positions held."""
    profile = desk_profile_for(TradingVenue.FUTURES_TESTNET)

    assert profile.venue is TradingVenue.FUTURES_TESTNET
    assert profile.order_types == (
        OrderType.LIMIT,
        OrderType.MARKET,
        OrderType.STOP_LIMIT,
    )
    assert profile.figures is futures_side_figures
    assert profile.side_label(EntrySide.BUY) == "Buy/Long"
    assert profile.side_label(EntrySide.SELL) == "Sell/Short"
    assert profile.tp_sl_unavailable_reason is None
    assert profile.held_tab is HeldTab.POSITIONS
    assert profile.futures_controls is True
    assert desk_profile_for(TradingVenue.SPOT_TESTNET).futures_controls is False
