"""`BUG-257` — the exchange's pause behind a read that failed, when there is one.

@details A history or position read that met the exchange's pause (429, 418) reaches a registration
as `AccountHistoryUnavailableError`, whose text is the reader's. The pause is the cause the owner
can act on (wait), so the registration's refusal names it instead of only "unavailable". The pause
is found along the exception's causes (`raise ... from`), the way the readers chain it.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)


def exchange_pause_behind(error: BaseException) -> timedelta | None:
    """The pause the exchange asked for that `error` or one of its causes is, else `None`."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if isinstance(current, ExchangeRateLimitedError):
            return current.retry_after
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return None
