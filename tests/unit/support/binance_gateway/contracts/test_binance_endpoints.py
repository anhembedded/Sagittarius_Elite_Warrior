from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    klines_type_for,
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


def test_resolve_testnet_flag_every_venue():
    assert resolve_testnet_flag(MarketDataVenue.MAINNET_PUBLIC) is False
    assert resolve_testnet_flag(MarketDataVenue.FUTURES_TESTNET) is True


def test_klines_type_for_every_market():
    assert klines_type_for(MarketType.SPOT) == HistoricalKlinesType.SPOT
    assert klines_type_for(MarketType.FUTURES_USD_M) == HistoricalKlinesType.FUTURES
    assert (
        klines_type_for(MarketType.FUTURES_COIN_M) == HistoricalKlinesType.FUTURES_COIN
    )
