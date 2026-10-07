"""The one place a Binance error becomes a `ConnectionFailureKind` (BUG-167).

Both account readers (Futures and Spot) classify a failed connection check
through `classify_connection_failure`, so the code-to-kind table exists once.

Binance `-2015` ("Invalid API-key, IP, or permissions for action") is not an
expiry: the exchange rejected the key for a reason it does not name — an unknown
key (a mainnet key sent to the testnet, the app being testnet-only), an IP off
the key's allowlist, or a key without the needed permission. It maps to
`KEY_REJECTED`. No Binance code means "expired", so no such kind exists.
"""

from __future__ import annotations

import logging

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

logger = logging.getLogger("App.TradingAdapter")

#: Binance error codes that name a failure precisely. Any other
#: `BinanceAPIException` code — or a failure with no code at all — degrades to
#: `ConnectionFailureKind.NETWORK`.
_ERROR_CODE_TO_FAILURE_KIND: dict[int, ConnectionFailureKind] = {
    -1021: ConnectionFailureKind.CLOCK_SKEW,
    -1022: ConnectionFailureKind.BAD_SIGNATURE,
    -2015: ConnectionFailureKind.KEY_REJECTED,
}


def classify_connection_failure(
    exc: Exception, venue_label: str
) -> ConnectionFailureKind:
    """The failure kind of a connection-check exception, logged once.

    `venue_label` ("Futures Testnet", "Spot Testnet") only words the log line.
    """
    if not isinstance(exc, BinanceAPIException):
        kind = ConnectionFailureKind.NETWORK
    else:
        kind = _ERROR_CODE_TO_FAILURE_KIND.get(exc.code, ConnectionFailureKind.NETWORK)
    if kind is ConnectionFailureKind.NETWORK:
        # `BUG-137`: the catch-all bucket must leave the real exception in the
        # run log (`code/errors.md` #1).
        logger.error(
            "%s connection check failed with an unclassified exception: %s: %s",
            venue_label,
            type(exc).__name__,
            exc,
        )
    else:
        logger.info(
            "%s connection check rejected: Binance code %s -> %s [connection-failure]",
            venue_label,
            getattr(exc, "code", None),
            kind.name,
        )
    return kind
