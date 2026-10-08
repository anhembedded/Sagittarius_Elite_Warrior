"""`EPIC-035D` — which failures of an exchange call are worth another try, and which are a pause.

The one function every adapter's retry policy asks (`ExchangeCallPolicy`):

  · `TRANSIENT` — the request may never have arrived or its answer was lost: a
    transport failure (timeout, reset, DNS), python-binance's own request
    exception, a gateway's HTML page, the exchange's busy codes (`-1001`
    internal error, `-1006` / `-1007` status unknown). Another try can succeed.
  · `RATE_LIMITED` — HTTP 429, or the codes `-1003` (too many requests) and
    `-1015` (too many new orders). The pause is what the exchange stated
    (`Retry-After`), else a named default.
  · `BANNED` — HTTP 418: the IP is banned. The window is `Retry-After`, else the
    instant the exchange's message names ("banned until <ms>"), else the
    shortest ban Binance gives.
  · `OTHER` — the exchange read the request and answered with another code
    (an unknown order, a filter, a key): asking again changes nothing.

The pause is capped at `MAX_PAUSE_SECONDS`: Binance's longest ban is three days,
and a number from a header must not park a caller for longer than that.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    is_non_json_answer,
)

#: The pause when the exchange rate-limits a request without saying for how long
#: (the weight window is a minute).
DEFAULT_RATE_LIMIT_PAUSE_SECONDS = 60.0
#: `-1015`: the order-count windows are ten seconds and a day; the short one is
#: what an automated bot meets.
DEFAULT_ORDER_COUNT_PAUSE_SECONDS = 10.0
#: The shortest IP ban Binance gives.
DEFAULT_BAN_PAUSE_SECONDS = 120.0
MAX_PAUSE_SECONDS = 3 * 24 * 3600.0

_BUSY_CODES = frozenset({-1001, -1006, -1007})
_ORDER_COUNT_CODE = -1015
_RATE_LIMIT_CODES = frozenset({-1003, _ORDER_COUNT_CODE})
_HTTP_RATE_LIMITED = 429
_HTTP_BANNED = 418
_FIRST_SERVER_ERROR_STATUS = 500
_BANNED_UNTIL = re.compile(r"banned until (\d{10,})")


class FailureKind(Enum):
    TRANSIENT = "transient"
    RATE_LIMITED = "rate_limited"
    BANNED = "banned"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ExchangeFailure:
    """What a failed call means: its kind and, for a pause, its seconds."""

    kind: FailureKind
    pause_seconds: float = 0.0


def classify_exchange_failure(
    exc: BaseException, server_now_ms: int
) -> ExchangeFailure:
    """@param server_now_ms The exchange's clock now, to turn "banned until
    <instant>" into a window."""
    if isinstance(exc, BinanceAPIException):
        return _classify_answer(exc, server_now_ms)
    if isinstance(exc, BinanceRequestException | RequestException):
        return ExchangeFailure(FailureKind.TRANSIENT)
    return ExchangeFailure(FailureKind.OTHER)


def _classify_answer(exc: BinanceAPIException, server_now_ms: int) -> ExchangeFailure:
    status = getattr(exc, "status_code", None)
    if status == _HTTP_BANNED:
        return ExchangeFailure(FailureKind.BANNED, _ban_seconds(exc, server_now_ms))
    if status == _HTTP_RATE_LIMITED or exc.code in _RATE_LIMIT_CODES:
        return ExchangeFailure(FailureKind.RATE_LIMITED, _limit_seconds(exc))
    if exc.code in _BUSY_CODES or (
        is_non_json_answer(exc) and _is_gateway_status(status)
    ):
        return ExchangeFailure(FailureKind.TRANSIENT)
    return ExchangeFailure(FailureKind.OTHER)


def _is_gateway_status(status: object) -> bool:
    return isinstance(status, int) and status >= _FIRST_SERVER_ERROR_STATUS


def _limit_seconds(exc: BinanceAPIException) -> float:
    stated = _retry_after_seconds(exc)
    if stated is not None:
        return stated
    if exc.code == _ORDER_COUNT_CODE:
        return DEFAULT_ORDER_COUNT_PAUSE_SECONDS
    return DEFAULT_RATE_LIMIT_PAUSE_SECONDS


def _ban_seconds(exc: BinanceAPIException, server_now_ms: int) -> float:
    stated = _retry_after_seconds(exc)
    if stated is not None:
        return stated
    named = _BANNED_UNTIL.search(str(exc.message))
    if named is not None:
        left_seconds = (int(named.group(1)) - server_now_ms) / 1000
        return min(max(left_seconds, 1.0), MAX_PAUSE_SECONDS)
    return DEFAULT_BAN_PAUSE_SECONDS


def _retry_after_seconds(exc: BinanceAPIException) -> float | None:
    """The `Retry-After` header as seconds, or `None` when absent or not a
    positive number (an HTTP date is not used: nothing here sends one)."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    value = headers.get("Retry-After") if headers else None
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    return min(seconds, MAX_PAUSE_SECONDS)
