"""`EPIC-035D` — a venue's python-binance client, with the call policy on every request.

Retry belongs in one place below every caller: the account reader, the history
readers, the trading client (a bot's and the manual desk's alike) and the market
reads all talk to the same session, so the policy wraps the session once and no
adapter carries its own loop.

What a method is called decides how it is sent (`call_mode_of`):

  · `RETRIED` — a read (`get_*`, `futures_get_*`, `ping`, the time and account
    reads) or one of the named cancels: safe to repeat;
  · `ONCE` — everything else: an order's submit, a leverage or margin change, a
    method nobody classified. A name has to be added to the read list on purpose
    to be repeated, so a new method defaults to the safe side.

A request the exchange rejects for its timestamp (`-1021`) is the one failure the session
repairs itself (`BUG-221`): the clock offset the client measured when it was opened has
gone stale (the machine's clock stepped), so the session measures it again on **that
client** and sends the request once more. `-1021` is answered before the exchange looks at
the request, so sending an order again cannot duplicate it. A second `-1021` is a skew the
measurement cannot cure and goes to the caller as it came (`CLOCK_SKEW`); the session never
loops.

Attributes pass through (`timestamp_offset` is read by the history readers).
After each answer the client's last response is asked for its used-weight header.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    CLOCK_SKEW_CODE,
)

logger = logging.getLogger("App.TradingAdapter")

#: Measures the exchange's clock again and stores it on the client this is bound to.
ClockResync = Callable[[], None]

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
#: Cancels, by exact name: safe to repeat (an exchange answers "unknown order"
#: when the first one arrived). A substring rule would also repeat a method that
#: cancels *and* places, which no call here is — until one is added by mistake.
_CANCEL_NAMES = frozenset(
    {
        "cancel_order",
        "cancel_all_open_orders",
        "futures_cancel_order",
        "futures_cancel_all_open_orders",
        "futures_cancel_algo_order",
        "futures_cancel_all_algo_open_orders",
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
    return CallMode.RETRIED if method_name in _CANCEL_NAMES else CallMode.ONCE


class ResilientSession:
    """Forwards a client's methods through the policy and its attributes as they are."""

    def __init__(
        self,
        client: object,
        policy: ExchangeCallPolicy,
        resync_clock: ClockResync | None = None,
    ) -> None:
        """@param resync_clock Re-measures `client`'s clock offset; `None` for a session
        that signs nothing (the public one), which the exchange never rejects for a timestamp."""
        self._client = client
        self._policy = policy
        self._resync_clock = resync_clock

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
            answer = run(lambda: self._sent(name, method, args, kwargs))
            self._policy.note_used_weight_header(self._used_weight_header())
            return answer

        return resilient

    def _sent(
        self,
        name: str,
        method: Callable[..., object],
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> object:
        """One request, and once more after the clock is measured again when the exchange
        rejected its timestamp.
        @raise BinanceAPIException `-1021` twice, or any other failure."""
        try:
            return method(*args, **kwargs)
        except BinanceAPIException as exc:
            if exc.code != CLOCK_SKEW_CODE or self._resync_clock is None:
                raise
            before = getattr(self._client, "timestamp_offset", None)
            self._resync_clock()
            logger.warning(
                "Exchange rejected the timestamp of %s (-1021); clock offset measured again "
                "(%s ms -> %s ms), sending it once more [clock-resync]",
                name,
                before,
                getattr(self._client, "timestamp_offset", None),
            )
        return method(*args, **kwargs)

    def _used_weight_header(self) -> str | None:
        response = getattr(self._client, "response", None)
        headers = getattr(response, "headers", None)
        return headers.get(_WEIGHT_HEADER) if headers else None
