from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


def test_market_data_venue_enum_values():
    assert MarketDataVenue.MAINNET_PUBLIC == "mainnet_public"
    assert MarketDataVenue.FUTURES_TESTNET == "futures_testnet"
