from unittest.mock import Mock

from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    klines_type_for,
    resolve_market_data_venue,
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


def test_resolve_market_data_venue_reads_the_configured_value():
    config = Mock()
    config.get.return_value = MarketDataVenue.FUTURES_TESTNET.value

    resolved = resolve_market_data_venue(config)

    assert resolved is MarketDataVenue.FUTURES_TESTNET
    config.get.assert_called_once_with(
        ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value,
        MarketDataVenue.MAINNET_PUBLIC.value,
    )


def test_resolve_market_data_venue_falls_back_on_missing_config():
    config = Mock()
    config.get.return_value = MarketDataVenue.MAINNET_PUBLIC.value

    assert resolve_market_data_venue(config) is MarketDataVenue.MAINNET_PUBLIC


def test_resolve_market_data_venue_falls_back_and_warns_on_an_unknown_value(caplog):
    config = Mock()
    config.get.return_value = "not_a_real_venue"

    resolved = resolve_market_data_venue(config)

    assert resolved is MarketDataVenue.MAINNET_PUBLIC
    assert "not_a_real_venue" in caplog.text
