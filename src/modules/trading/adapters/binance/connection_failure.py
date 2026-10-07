"""The one place a Binance error becomes a `ConnectionFailureKind` (BUG-167).

Both account readers (Futures and Spot) classify a failed connection check
through `classify_connection_failure`, so the code-to-kind table exists once.

Binance `-2015` ("Invalid API-key, IP, or permissions for action") is not an
expiry: the exchange rejected the key for a reason it does not name — an unknown
key (a mainnet key sent to the testnet, the app being testnet-only), an IP off
the key's allowlist, or a key without the needed permission. It maps to
`KEY_REJECTED`, as do `-2008` (unknown key) and `-2014` (bad key format). No Binance code means "expired", so no such kind exists.

A non-JSON answer (a gateway's HTML page: `502 Bad Gateway`, a maintenance
notice) is the other thing this module names once, `BUG-168`: python-binance
wraps the whole page in `BinanceAPIException(code=0)`, and every adapter used
to forward that text to a screen and a log. `describe_failure` is the one
function an adapter calls to word any failure: a short plain reason, the page
itself written once at DEBUG. The connection check names the same answer
`ConnectionFailureKind.MAINTENANCE`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TypeGuard

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
    #: `BUG-175`: "Invalid Api-Key ID" (the exchange does not know the key: a
    #: testnet key pasted for mainnet, or the reverse) and "API-key format
    #: invalid". Both are about the key, never the network.
    -2008: ConnectionFailureKind.KEY_REJECTED,
    -2014: ConnectionFailureKind.KEY_REJECTED,
}

#: `BUG-175`: what to do about the key codes, in plain words. `describe_failure`
#: appends it to the exchange's own code and message, so a log line, the
#: key-enrolment script and the Connect step all say the same thing.
_KEY_CODE_HINTS: dict[int, str] = {
    -2015: (
        "The key's IP whitelist does not include this machine's public IP "
        "(a LAN address such as 192.168.x.x never matches), Enable Reading is "
        "off, or the change is not saved yet."
    ),
    -2008: (
        "The exchange does not know this key; a testnet or Demo Trading key "
        "does not work on mainnet."
    ),
    -2014: "The key is malformed: copy it again, with no spaces or missing characters.",
}

#: The text python-binance starts a non-JSON answer's message with
#: (`binance.exceptions.BinanceAPIException`).
_NON_JSON_MESSAGE_PREFIX = "Invalid JSON error message from Binance"
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]*>?")
_MAX_TITLE_CHARS = 60
#: How much of a page the DEBUG line carries.
_MAX_LOGGED_BODY_CHARS = 2000


def is_non_json_answer(exc: BaseException) -> TypeGuard[BinanceAPIException]:
    """Whether `exc` is the exchange answering with something that is not an
    API reply (an HTML error page) — python-binance's `code=0` exception."""
    return (
        isinstance(exc, BinanceAPIException)
        and not exc.code
        and str(exc.message).startswith(_NON_JSON_MESSAGE_PREFIX)
    )


def _page_title(page: str) -> str:
    """The page's `<title>` as plain words: tags dropped, whitespace
    collapsed, capped. Empty when the page has none."""
    found = _TITLE.search(page)
    if found is None:
        return ""
    words = " ".join(_TAG.sub("", found.group(1)).replace("<", "").split())
    return words[:_MAX_TITLE_CHARS]


def describe_failure(
    exc: BaseException, other: Callable[[BaseException], str] = str
) -> str:
    """A short plain-text reason for a failed exchange call, never a body.

    A non-JSON answer reads "the exchange is unavailable (HTTP 502 Bad
    Gateway)"; the page is written once, at DEBUG. Any other failure keeps its
    own short text, worded by `other` (`str` by default; `repr` for a payload
    that could not be mapped).
    """
    if isinstance(exc, BinanceAPIException) and exc.code in _KEY_CODE_HINTS:
        message = str(exc.message).rstrip(".")
        return f"{exc.code} {message}. {_KEY_CODE_HINTS[exc.code]}"
    if not is_non_json_answer(exc):
        return other(exc)
    page = str(getattr(exc.response, "text", "") or "")
    title = _page_title(page)
    status = f"HTTP {exc.status_code}" if exc.status_code else "no HTTP status"
    logger.debug(
        "Exchange answered %s with a non-JSON page: %s [exchange-unavailable]",
        status,
        page[:_MAX_LOGGED_BODY_CHARS],
    )
    return f"the exchange is unavailable ({status}{' ' + title if title else ''})"


def classify_connection_failure(
    exc: Exception, venue_label: str
) -> ConnectionFailureKind:
    """The failure kind of a connection-check exception, logged once.

    `venue_label` ("Futures Testnet", "Spot Testnet") only words the log line.
    """
    if is_non_json_answer(exc):
        kind = ConnectionFailureKind.MAINTENANCE
    elif not isinstance(exc, BinanceAPIException):
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
