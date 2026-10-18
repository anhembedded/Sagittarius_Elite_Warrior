from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


def test_resolve_testnet_flag_every_venue():
    assert resolve_testnet_flag(MarketDataVenue.MAINNET_PUBLIC) is False
    assert resolve_testnet_flag(MarketDataVenue.FUTURES_TESTNET) is True
