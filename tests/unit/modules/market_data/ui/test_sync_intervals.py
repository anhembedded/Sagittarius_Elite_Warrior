"""`BOT-167` — the Database screen's interval list is the rule's list for the
market its syncs fetch, so nobody can start a sync the market cannot serve."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import timeframes_for
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    sync_coordinator,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.sync_intervals import (
    SYNC_INTERVALS,
    SYNC_MARKET,
)


def test_the_sync_coordinator_syncs_the_market_the_interval_list_is_for():
    assert sync_coordinator._MARKET is SYNC_MARKET


def test_the_interval_list_is_what_the_synced_market_can_load():
    assert [tf.value for tf in timeframes_for(SYNC_MARKET)] == SYNC_INTERVALS


def test_the_screen_offers_one_second_while_it_syncs_spot(qapp):
    assert SYNC_MARKET is MarketType.SPOT
    assert "1s" in DataManagementViewModel().intervals


def test_a_futures_sync_market_would_offer_no_one_second_interval():
    futures = [tf.value for tf in timeframes_for(MarketType.FUTURES_USD_M)]
    assert "1s" not in futures
