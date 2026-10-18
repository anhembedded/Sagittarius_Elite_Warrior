from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.klines_type import (
    klines_type_for,
)


def test_klines_type_for_every_market():
    assert klines_type_for(MarketType.SPOT) == HistoricalKlinesType.SPOT
    assert klines_type_for(MarketType.FUTURES_USD_M) == HistoricalKlinesType.FUTURES
    assert (
        klines_type_for(MarketType.FUTURES_COIN_M) == HistoricalKlinesType.FUTURES_COIN
    )
