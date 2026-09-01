"""Venue -> `python-binance` `testnet` flag, and `klines_type` for kline calls
(`EPIC-021A`)."""

from __future__ import annotations

import logging

from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig

logger = logging.getLogger("App.ExchangeClient")

_DEFAULT_MARKET_DATA_VENUE = MarketDataVenue.MAINNET_PUBLIC

#: `python-binance`'s `Client(testnet=...)` is one flag that redirects every
#: API family's host at once (`base_client.py`'s `_create_api_uri`/
#: `_create_futures_api_uri` both check it) — there is no per-call override,
#: so one client instance always serves exactly one of these two rows.
_TESTNET_FLAG: dict[MarketDataVenue, bool] = {
    MarketDataVenue.MAINNET_PUBLIC: False,
    MarketDataVenue.FUTURES_TESTNET: True,
}

#: Which `klines_type` `get_historical_klines_generator()` should use for a
#: given market-data venue. Both values share one pagination/retry pipeline
#: inside `python-binance` (`_historical_klines_generator` -> `_klines`) —
#: verified by reading the installed library's own source, not assumed.
_KLINES_TYPE: dict[MarketDataVenue, HistoricalKlinesType] = {
    MarketDataVenue.MAINNET_PUBLIC: HistoricalKlinesType.SPOT,
    MarketDataVenue.FUTURES_TESTNET: HistoricalKlinesType.FUTURES,
}


def resolve_testnet_flag(venue: MarketDataVenue) -> bool:
    """Returns the `testnet` flag `Client(...)` must be constructed with."""
    return _TESTNET_FLAG[venue]


def klines_type_for(venue: MarketDataVenue) -> HistoricalKlinesType:
    """Returns which `python-binance` kline family a venue's klines resolve
    against. Exchange-info/symbol-catalog calls are unaffected — `021C`'s
    concern, not this one's (see `EPIC-021A` §2.2b)."""
    return _KLINES_TYPE[venue]


def resolve_market_data_venue(config: IConfig) -> MarketDataVenue:
    """The configured `MarketDataVenue`, or the default if missing/unusable.

    @details Same shape as `view_factory.resolve_backtest_view_key` — warns
    instead of failing boot on a bad value (`logging-rule.md` §2: a degraded
    branch must say what it chose and why, not fail silently or crash)."""
    raw = config.get(
        ConfigKeys.EXCHANGE_MARKET_DATA_VENUE.value, _DEFAULT_MARKET_DATA_VENUE.value
    )
    try:
        return MarketDataVenue(raw)
    except ValueError:
        logger.warning(
            "Market data venue %r is not known; using %r. Known venues: %s.",
            raw,
            _DEFAULT_MARKET_DATA_VENUE.value,
            [venue.value for venue in MarketDataVenue],
        )
        return _DEFAULT_MARKET_DATA_VENUE
