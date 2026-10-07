"""`BOT-167` — which timeframes a market can load, as one domain fact.

Binance USD-M Futures has no 1-second klines (`fapi/v1/klines?interval=1s`
answers `-1120 Invalid interval`), Spot does. Every picker asks this rule, so
none of them can offer a timeframe the selected market cannot load.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    supports_timeframe,
    timeframe_or_fallback,
    timeframes_for,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

_FUTURES = [MarketType.FUTURES_USD_M, MarketType.FUTURES_COIN_M]


def test_spot_offers_every_timeframe_including_one_second() -> None:
    assert set(timeframes_for(MarketType.SPOT)) == set(TimeFrame)
    assert supports_timeframe(MarketType.SPOT, "1s")


@pytest.mark.parametrize("market", _FUTURES)
def test_futures_offers_every_timeframe_except_one_second(market: MarketType) -> None:
    offered = timeframes_for(market)
    assert TimeFrame.ONE_SECOND not in offered
    assert set(offered) == set(TimeFrame) - {TimeFrame.ONE_SECOND}
    assert not supports_timeframe(market, "1s")
    assert supports_timeframe(market, "1m")


def test_timeframes_are_shortest_first() -> None:
    offered = timeframes_for(MarketType.SPOT)
    assert [tf.to_seconds() for tf in offered] == sorted(
        tf.to_seconds() for tf in offered
    )


def test_a_code_the_domain_does_not_know_is_not_supported() -> None:
    assert not supports_timeframe(MarketType.SPOT, "7s")


def test_every_market_declares_a_rule() -> None:
    """A market added to `MarketType` without a decision about its intervals
    must fail here, not silently offer everything."""
    for market in MarketType:
        assert timeframes_for(market)


def test_a_supported_timeframe_is_kept() -> None:
    assert timeframe_or_fallback(MarketType.FUTURES_USD_M, "5m") == "5m"
    assert timeframe_or_fallback(MarketType.SPOT, "1s") == "1s"


def test_an_unsupported_timeframe_falls_back_to_the_shortest_supported_one() -> None:
    assert timeframe_or_fallback(MarketType.FUTURES_USD_M, "1s") == "1m"


def test_an_unknown_code_falls_back_too() -> None:
    assert timeframe_or_fallback(MarketType.FUTURES_USD_M, "nonsense") == "1m"
