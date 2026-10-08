"""`EPIC-035D` — a venue's python-binance client, with the call policy on every request.

Retry belongs in one place below every caller: the account reader, the history
readers, the trading client (a bot's and the manual desk's alike) and the market
reads all talk to the same session, so the policy wraps the session once and no
adapter carries its own loop.

What a method is called decides how it is sent (`call_mode_of`):

  · `RETRIED` — a read (`get_*`, `futures_get_*`, `ping`, the time and account
    reads) or a cancel (`*cancel*`): safe to repeat;
  · `ONCE` — everything else: an order's submit, a leverage or margin change, a
    method nobody classified. A name has to be added to the read list on purpose
    to be repeated, so a new method defaults to the safe side.

Attributes pass through (`timestamp_offset` is read by the history readers).
After each answer the client's last response is asked for its used-weight header.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)

_WEIGHT_HEADER = "x-mbx-used-weight-1m"

#: Reads whose names do not start with `get_`. Futures reads are `futures_*`.
_READ_NAMES = frozenset(
    {
        "ping",
        "futures_ping",
        "futures_time",
        "futures_account",
        "futures_position_information",
        "futures_orderbook_ticker",
        "futures_symbol_ticker",
        "futures_mark_price",
        "futures_leverage_bracket",
        "futures_income_history",
        "futures_symbol_config",
        "futures_exchange_info",
        "futures_commission_rate",
        "futures_account_trades",
        "futures_klines",
    }
)
_READ_PREFIXES = ("get_", "futures_get_")


class CallMode(Enum):
    RETRIED = "retried"
    ONCE = "once"


def call_mode_of(method_name: str) -> CallMode:
    """Whether a client method may be sent again after a failure in transit."""
    if method_name.startswith(_READ_PREFIXES) or method_name in _READ_NAMES:
        return CallMode.RETRIED
    if "cancel" in method_name:
        return CallMode.RETRIED
    return CallMode.ONCE


class ResilientSession:
    """Forwards a client's methods through the policy and its attributes as they are."""

    def __init__(self, client: object, policy: ExchangeCallPolicy) -> None:
        self._client = client
        self._policy = policy

    def __getattr__(self, name: str) -> object:
        attribute = getattr(self._client, name)
        if name.startswith("_") or not callable(attribute):
            return attribute
        method: Callable[..., object] = attribute
        run = (
            self._policy.run_read
            if call_mode_of(name) is CallMode.RETRIED
            else self._policy.run_once
        )

        def resilient(*args: object, **kwargs: object) -> object:
            answer = run(lambda: method(*args, **kwargs))
            self._policy.note_used_weight_header(self._used_weight_header())
            return answer

        return resilient

    def _used_weight_header(self) -> str | None:
        response = getattr(self._client, "response", None)
        headers = getattr(response, "headers", None)
        return headers.get(_WEIGHT_HEADER) if headers else None
