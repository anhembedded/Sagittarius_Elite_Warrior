"""`EPIC-035D` — the rate-limit pause, as an exception every existing handler already catches.

Around fifteen adapters catch `BinanceAPIException` to turn an exchange answer into
their own result (a connection status, `AccountHistoryUnavailableError`, a mark price
that is unavailable). A 429 reached them as that exception before the call policy
existed, and it must keep reaching them as one: the policy therefore raises this
subclass — a `BinanceAPIException` that looks like the answer it stands for (status
429 or 418, code `-1003`, `Retry-After`) and also carries the pause — rather than a
domain error those handlers would not catch.

The trading clients are the one place that turns it into the contract error a bot
and the desk understand (`rate_limited_error_of`): an order's submit, a cancel and
an order lookup raise `ExchangeRateLimitedError`; a reader keeps its own words.
"""

from __future__ import annotations

import json
import math
from datetime import timedelta
from types import SimpleNamespace

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)

_RATE_LIMIT_CODE = -1003
_HTTP_RATE_LIMITED = 429
_HTTP_BANNED = 418


class RateLimitedApiException(BinanceAPIException):
    """A call refused, or not sent, because the exchange asked for a pause."""

    def __init__(self, retry_after: timedelta, *, banned: bool, note: str) -> None:
        seconds = math.ceil(retry_after.total_seconds())
        body = json.dumps({"code": _RATE_LIMIT_CODE, "msg": note})
        response = SimpleNamespace(text=body, headers={"Retry-After": str(seconds)})
        super().__init__(response, _HTTP_BANNED if banned else _HTTP_RATE_LIMITED, body)
        self.retry_after = retry_after
        self.banned = banned


def rate_limited_error_of(exc: BaseException) -> ExchangeRateLimitedError | None:
    """The contract error for `exc` when it is a rate-limit pause, else `None`."""
    if not isinstance(exc, RateLimitedApiException):
        return None
    error = ExchangeRateLimitedError(
        exc.retry_after, banned=exc.banned, raw_message=str(exc.message)
    )
    error.__cause__ = exc
    return error
