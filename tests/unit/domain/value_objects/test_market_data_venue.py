from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)


def test_market_data_venue_enum_values():
    assert MarketDataVenue.MAINNET_PUBLIC == "mainnet_public"
    assert MarketDataVenue.FUTURES_TESTNET == "futures_testnet"
