"""Venue -> `python-binance` `testnet` flag, and `klines_type` for kline calls
(`EPIC-021A`); also where the assembled `TradingVenue`s are resolved
(`EPIC-021F`, `EPIC-034B`)."""

from __future__ import annotations

import logging

from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_config import IConfig

logger = logging.getLogger("App.ExchangeClient")

#: `BUG-063` — python-binance's own default read timeout is 10s. A multi-day
#: 1-second-interval sync needs hundreds of sequential requests, so at that
#: default, an ordinary slow response (not an outage) was enough to fail the
#: whole sync. 30s is still bounded — a genuinely dead connection fails loud
#: well within human patience — but stops treating an occasional slow page as
#: fatal.
#:
#: Here rather than in one factory because `EPIC-025` PR 1.3c-4 split the
#: factory in two and both mint sessions with it: a number two contexts must
#: agree on is vocabulary, which is what this package holds (HLD §8).
REQUEST_TIMEOUT_SECONDS = 30.0

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
#: given `MarketType` (`EPIC-027A`; keyed by venue before that — the venue
#: picks the host via `Client(testnet=...)`, the market picks the klines
#: family, and the two vary independently per call). All three values share
#: one pagination/retry pipeline inside `python-binance`
#: (`_historical_klines_generator` -> `_klines`) — verified by reading the
#: installed library's own source, not assumed.
_KLINES_TYPE: dict[MarketType, HistoricalKlinesType] = {
    MarketType.SPOT: HistoricalKlinesType.SPOT,
    MarketType.FUTURES_USD_M: HistoricalKlinesType.FUTURES,
    MarketType.FUTURES_COIN_M: HistoricalKlinesType.FUTURES_COIN,
}


def resolve_testnet_flag(venue: MarketDataVenue) -> bool:
    """Returns the `testnet` flag `Client(...)` must be constructed with."""
    return _TESTNET_FLAG[venue]


def klines_type_for(market: MarketType) -> HistoricalKlinesType:
    """Returns which `python-binance` kline family a `MarketType`'s klines
    resolve against. Exchange-info/symbol-catalog calls are unaffected —
    `021C`'s concern, not this one's (see `EPIC-021A` §2.2b)."""
    return _KLINES_TYPE[market]


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


def resolve_trading_venue(config: IConfig) -> TradingVenue:
    """The one venue a single-venue caller acts on: the primary of
    `resolve_trading_venues` (the first one in `TradingVenue` order)."""
    return resolve_trading_venues(config)[0]


def resolve_trading_venues(config: IConfig) -> tuple[TradingVenue, ...]:
    """`EPIC-034B` — every venue that can place orders, in `TradingVenue` order.

    @details The set is a fact of the build, not a setting: a venue with no
    usable key is still assembled, and its connection check answers "no key"
    (`SPOT_TESTNET` and `FUTURES_TESTNET` resolve their credentials per call,
    so a key saved in Options reaches them without a restart). `config` is
    accepted so the callers did not change; what it says about venues is
    reported by `log_ignored_venue_setting`, never obeyed.
    """
    del config
    return tuple(venue for venue in TradingVenue if venue.supports_order_submission)


def log_ignored_venue_setting(config: IConfig) -> bool:
    """Say once, at boot, that a configuration written before `EPIC-034B`
    still names venues and that the app no longer reads the setting.

    @return `True` when something was logged. The defaults file's scalar
    (`"disabled"`) is not a choice anyone made, so it stays silent.
    """
    listed = config.get(ConfigKeys.EXCHANGE_TRADING_VENUES.value, None)
    scalar = config.get(
        ConfigKeys.EXCHANGE_TRADING_VENUE.value, TradingVenue.DISABLED.value
    )
    if listed is None and scalar == TradingVenue.DISABLED.value:
        return False
    logger.info(
        "%s / %s name trading venues (%r / %r); the setting is ignored — every "
        "venue with a usable key is on (EPIC-034B).",
        ConfigKeys.EXCHANGE_TRADING_VENUES.value,
        ConfigKeys.EXCHANGE_TRADING_VENUE.value,
        listed,
        scalar,
    )
    return True
