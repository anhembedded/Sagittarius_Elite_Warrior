from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.venue_alignment import (
    VenueAlignment,
    compute_venue_alignment,
)


def test_trading_disabled_wins_regardless_of_market_data_venue() -> None:
    assert (
        compute_venue_alignment(MarketDataVenue.MAINNET_PUBLIC, TradingVenue.DISABLED)
        is VenueAlignment.TRADING_DISABLED
    )
    assert (
        compute_venue_alignment(MarketDataVenue.FUTURES_TESTNET, TradingVenue.DISABLED)
        is VenueAlignment.TRADING_DISABLED
    )


def test_testnet_data_with_testnet_trading_is_aligned() -> None:
    assert (
        compute_venue_alignment(
            MarketDataVenue.FUTURES_TESTNET, TradingVenue.FUTURES_TESTNET
        )
        is VenueAlignment.ALIGNED
    )


def test_mainnet_data_with_testnet_trading_is_the_named_trap() -> None:
    assert (
        compute_venue_alignment(
            MarketDataVenue.MAINNET_PUBLIC, TradingVenue.FUTURES_TESTNET
        )
        is VenueAlignment.DATA_MAINNET_ORDERS_TESTNET
    )
