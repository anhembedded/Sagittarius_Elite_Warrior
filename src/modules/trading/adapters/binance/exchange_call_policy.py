"""`EPIC-035D` — the one retry policy below the gateway (retry with backoff, and a gate).

Every request a venue sends passes `run_read` or `run_once`:

  · **`run_read`** — a read or a cancel: tried again after a growing, capped wait
    (`READ_RETRY_DELAYS_SECONDS`) while the failure is transient. A cancel is safe
    to repeat: the exchange answers "unknown order" if the first one arrived.
  · **`run_once`** — anything else, an order's submit above all: sent once. What a
    submit that fails in transit means is already decided elsewhere
    (`order_send_failure`: an unknown outcome, resolved by looking the order up by
    its client order id); a second send here would be the duplicate that lookup
    exists to prevent.
  · **Both stop at the gate.** A rate-limit answer is not waited out inside a call
    (a call that sleeps for a minute holds a bot's worker): it closes the venue's
    gate for the stated pause and raises `RateLimitedApiException`, and every call
    until the pause ends raises the same without sending. A 418 does the same for
    its ban window.

The used-weight header (`X-MBX-USED-WEIGHT-1M`) is read after each answer
(`note_used_weight_header`): at 90 % of the venue's per-minute weight the gate
closes to the end of the minute, before the exchange has to say so.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_failure import (
    ExchangeFailure,
    FailureKind,
    classify_exchange_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)

logger = logging.getLogger("App.TradingAdapter")

T = TypeVar("T")

#: The wait before each retry of a read or a cancel: three retries, 3.5 s in all,
#: capped at 2 s each. Short, because the caller is a worker or a click.
READ_RETRY_DELAYS_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)
#: Binance's per-minute request weight for a Spot IP; a Futures venue passes 2400.
SPOT_WEIGHT_LIMIT = 6000
#: The share of the minute's weight at which the gate closes to the minute's end.
SOFT_WEIGHT_RATIO = 0.9
_SECONDS_PER_MINUTE = 60.0


class ExchangeCallPolicy:
    """Retries what may be retried, stops at the gate, closes it on a rate limit."""

    def __init__(
        self,
        gate: RateLimitGate,
        *,
        sleep: Callable[[float], None] | None = None,
        wall_seconds: Callable[[], float] = time.time,
        weight_limit: int = SPOT_WEIGHT_LIMIT,
    ) -> None:
        self._gate = gate
        # Resolved at the call, so a test can replace `time.sleep` itself.
        self._sleep = sleep or (lambda seconds: time.sleep(seconds))
        self._wall_seconds = wall_seconds
        self._weight_limit = weight_limit

    def run_read(self, call: Callable[[], T]) -> T:
        """@raise RateLimitedApiException The gate is closed, or the exchange
        just closed it. Any other failure: the last one, after the retries."""
        return self._run(call, READ_RETRY_DELAYS_SECONDS)

    def run_once(self, call: Callable[[], T]) -> T:
        """@raise RateLimitedApiException As `run_read`.
        @raise Exception The call's own failure, at once."""
        return self._run(call, ())

    def note_used_weight_header(self, value: str | None) -> None:
        """Read the used-weight header of the answer just received."""
        if value is None:
            return
        try:
            self.note_used_weight(int(value))
        except ValueError:
            logger.debug("Ignoring a used-weight header that is not a number")

    def note_used_weight(self, used: int) -> None:
        if used < self._weight_limit * SOFT_WEIGHT_RATIO:
            return
        into_minute = self._wall_seconds() % _SECONDS_PER_MINUTE
        pause = _SECONDS_PER_MINUTE - into_minute + 1.0
        logger.warning(
            "Used weight %d of %d: no request for %.0f s [rate-limit-soft]",
            used,
            self._weight_limit,
            pause,
        )
        self._gate.block(pause)

    def _run(self, call: Callable[[], T], delays: tuple[float, ...]) -> T:
        retries = iter(delays)
        while True:
            self._raise_if_closed()
            try:
                return call()
            except Exception as exc:
                failure = classify_exchange_failure(exc, self._server_now_ms())
                if failure.kind in (FailureKind.RATE_LIMITED, FailureKind.BANNED):
                    raise self._close_gate(failure, exc) from exc
                delay = next(retries, None)
                if failure.kind is not FailureKind.TRANSIENT or delay is None:
                    raise
                logger.warning(
                    "Exchange call failed in transit (%s); trying again in %.1f s [exchange-retry]",
                    type(exc).__name__,
                    delay,
                )
                self._sleep(delay)

    def _raise_if_closed(self) -> None:
        remaining = self._gate.remaining()
        if remaining > 0:
            raise RateLimitedApiException(
                timedelta(seconds=remaining),
                banned=self._gate.banned,
                note=f"no request is sent for another {math.ceil(remaining)} s: "
                "the exchange asked for a pause",
            )

    def _close_gate(
        self, failure: ExchangeFailure, cause: Exception
    ) -> RateLimitedApiException:
        banned = failure.kind is FailureKind.BANNED
        self._gate.block(failure.pause_seconds, banned=banned)
        logger.warning(
            "Exchange %s: no request for %.0f s [rate-limit-%s]",
            "banned this IP" if banned else "rate-limited the app",
            failure.pause_seconds,
            "ban" if banned else "pause",
        )
        return RateLimitedApiException(
            timedelta(seconds=failure.pause_seconds),
            banned=banned,
            note=(
                f"{'banned' if banned else 'rate limited'} by the exchange "
                f"({type(cause).__name__}); no request for "
                f"{math.ceil(failure.pause_seconds)} s"
            ),
        )

    def _server_now_ms(self) -> int:
        return int(self._wall_seconds() * 1000)
