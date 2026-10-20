"""Venue -> `python-binance` `testnet` flag (`EPIC-021A`); also where the assembled
`TradingVenue`s are resolved (`EPIC-021F`, `EPIC-034B`)."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
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

#: The `recvWindow` every signed REST request carries (`EPIC-026I`): how long after its
#: `timestamp` the exchange still accepts it. Binance recommends 5000 ms or less and caps it
#: at 60000. python-binance sends its own 10000 ms when nothing is set, and a per-call
#: `recvWindow` is overwritten by it, so the one place that sets it is `new_client`. The
#: `timestamp` is already corrected by the measured clock offset, so this bounds the
#: request's time in transit, not the machine's clock error (`BUG-111`, `BUG-221`).
SIGNED_REQUEST_RECV_WINDOW_MS = 5000

#: `python-binance`'s `Client(testnet=...)` is one flag that redirects every
#: API family's host at once (`base_client.py`'s `_create_api_uri`/
#: `_create_futures_api_uri` both check it) — there is no per-call override,
#: so one client instance always serves exactly one environment: the testnet
#: members share the flag, and the market picks which testnet host answers.
_TESTNET_FLAG: dict[MarketDataVenue, bool] = {
    MarketDataVenue.MAINNET_PUBLIC: False,
    MarketDataVenue.FUTURES_TESTNET: True,
    MarketDataVenue.SPOT_TESTNET: True,
}


def resolve_testnet_flag(venue: MarketDataVenue) -> bool:
    """Returns the `testnet` flag `Client(...)` must be constructed with."""
    return _TESTNET_FLAG[venue]


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
