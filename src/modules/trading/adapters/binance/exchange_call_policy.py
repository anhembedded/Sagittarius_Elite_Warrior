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
(`note_used_weight_header`). At 70 % of the venue's per-minute weight the gate closes to the end
of the minute to routine requests, before the exchange has to say so; the reads that guard a
bot's exits (`RequestPriority.EXIT_GUARD`: its position, the mark price, its open protective
stops) still pass, in the reserve up to 90 %, so a burst of ladder placement cannot leave a stop
loss or a take profit unjudged (`BOT-226`, `BUG-247`). At 90 % the gate closes to everything, as
a 429 does.

A pause is told once and no more (`BUG-217`): one WARNING when it begins, with the instant it
ends, and one INFO at the first request after it. It is told again, with the end the gate now
holds, only when it escalates: a later answer moves the end further out or turns it into a ban.
The calls that meet it in between raise at once and say nothing here; what they fail with is
theirs to word, at DEBUG when it is the pause.
"""

from __future__ import annotations

import logging
import math
import threading
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
    current_priority,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.weight_reading import (
    WeightReading,
)

logger = logging.getLogger("App.TradingAdapter")

T = TypeVar("T")

#: The wait before each retry of a read or a cancel: three retries, 3.5 s in all,
#: capped at 2 s each. Short, because the caller is a worker or a click.
READ_RETRY_DELAYS_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)
#: Binance's per-minute request weight for a Spot IP; a Futures venue passes 2400.
SPOT_WEIGHT_LIMIT = 6000
#: The share of the minute's weight at which the gate closes to the minute's end. 70 %, because
#: the header is read after an answer and a Grid's chains (a register is ~100 weight, a burst of
#: fills sends several at once) are already in flight when it closes: the owner's gate closed at
#: 2,168 of 2,400 and the exchange limited the IP in the same second (`BUG-216`). The 30 % left
#: is ~720 weight of such chains.
SOFT_WEIGHT_RATIO = 0.7
#: The share at which the reserve ends and the gate closes to every request, the reads that guard
#: exits included. The reserve (70 % to here, 480 of Futures' 2,400) is for those reads alone: an
#: idle minute of them weighs 96, 240 and ~780 at 1, 5 and 20 bots (`BOT-226`); the cap is five.
#: `BUG-216` found 90 % too late for the *soft* line, when every request, Grid chains included (a
#: register is ~100 weight), was still being sent as the header crossed. Above 70 % no routine chain
#: starts now: each of its requests passes `_raise_if_closed` on its own, so a chain stops at its
#: next request. What can be in flight at 90 % is the guard reads of at most five bots (1 to 5
#: weight each) and single routine requests already sent, well inside the 240 weight above this
#: line. The owner confirms the figure (`BOT-226`).
HARD_WEIGHT_RATIO = 0.9
_SECONDS_PER_MINUTE = 60.0
#: Two pauses whose ends differ by less than this are the same pause to the log.
_SAME_END_SECONDS = 1.0


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
        self._pause_lock = threading.Lock()
        #: When the pause last announced is due to end, on the wall clock; `None` once the
        #: end has been announced (or none began).
        self._announced_pause_end: float | None = None
        self._announced_ban = False
        #: The same for the reserve, which closes routine requests alone: the guards' own pause
        #: (above) and the reserve end at different instants, and each is told with its own.
        self._announced_routine_end: float | None = None
        # Resolved at the call, so a test can replace `time.sleep` itself.
        self._sleep = sleep or (lambda seconds: time.sleep(seconds))
        self._wall_seconds = wall_seconds
        self._weight_limit = weight_limit
        #: The last used-weight header and the wall second it came with (`EPIC-047H`, `weight_reading`).
        self._last_used: tuple[int, float] | None = None

    def weight_reading(self) -> WeightReading:
        """What this venue's sessions last heard of the minute's weight, and whether a routine request may pass."""
        last = self._last_used
        return WeightReading(
            used=None if last is None else last[0],
            limit=self._weight_limit,
            seen_at=None if last is None else last[1],
            routine_open=self._gate.routine_remaining() <= 0,
        )

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
        self._last_used = (used, self._wall_seconds())
        if used < self._weight_limit * SOFT_WEIGHT_RATIO:
            return
        into_minute = self._wall_seconds() % _SECONDS_PER_MINUTE
        pause = _SECONDS_PER_MINUTE - into_minute + 1.0
        # Always to the minute's end: a shorter pause already running (`-1015` is 10 s) must
        # not let the gate reopen inside a minute at 70 % or more. `block` keeps the longer.
        # It is told again only when it moves the announced end, turns the pause into a ban, or
        # the reserve's pause closes every request.
        why = f"Used weight {used} of {self._weight_limit}"
        if used >= self._weight_limit * HARD_WEIGHT_RATIO:
            self._gate.block(pause)
            told = self._tell_pause(why, pause, "rate-limit-soft")
        else:
            self._gate.block_routine(pause)
            told = self._tell_pause(why, pause, "rate-limit-reserve", routine_only=True)
        if not told:
            logger.debug(
                "Used weight %d of %d, inside a pause", used, self._weight_limit
            )

    def _run(self, call: Callable[[], T], delays: tuple[float, ...]) -> T:
        retries = iter(delays)
        priority = current_priority()
        while True:
            self._raise_if_closed(priority)
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

    def _raise_if_closed(self, priority: RequestPriority) -> None:
        """@raise RateLimitedApiException The gate is closed to a request of this priority."""
        routine_remaining = self._gate.routine_remaining()
        if routine_remaining <= 0:
            self._announce_pause_ended()
            return
        if priority is RequestPriority.EXIT_GUARD:
            remaining = self._gate.remaining()
            if remaining <= 0:
                return
            note = (
                f"no request is sent for another {math.ceil(remaining)} s: "
                "the exchange asked for a pause"
            )
        else:
            remaining = routine_remaining
            note = f"no request is sent for another {math.ceil(remaining)} s: " + (
                "the exchange asked for a pause"
                if self._gate.remaining() > 0
                else "the weight reserve is kept for the reads that guard exits"
            )
        raise RateLimitedApiException(
            timedelta(seconds=remaining), banned=self._gate.banned, note=note
        )

    def _close_gate(
        self, failure: ExchangeFailure, cause: Exception
    ) -> RateLimitedApiException:
        banned = failure.kind is FailureKind.BANNED
        self._gate.block(failure.pause_seconds, banned=banned)
        self._tell_pause(
            "Exchange banned this IP" if banned else "Exchange rate-limited the app",
            failure.pause_seconds,
            "rate-limit-ban" if banned else "rate-limit-pause",
            banned=banned,
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

    def _tell_pause(
        self,
        why: str,
        pause: float,
        tag: str,
        *,
        banned: bool = False,
        routine_only: bool = False,
    ) -> bool:
        """Tell a pause that begins, or one that moves the announced end later or turns the
        running pause into a ban (a burst's answers in flight escalate that way: a soft pause, then
        a 429, then a 418). The pause that closes every request and the reserve that closes
        routine requests alone are announced apart, each with its own end. The WARNING names the
        end the gate now holds for the class it is about.
        Decided under the lock, so threads that meet the same pause tell it once.
        @return Whether it was told."""
        ends = self._wall_seconds() + pause
        with self._pause_lock:
            known = (
                self._announced_routine_end
                if routine_only
                else self._announced_pause_end
            )
            worth = (
                known is None
                or ends > known + _SAME_END_SECONDS
                or (banned and not self._announced_ban)
            )
            covered = self._announced_pause_end
            if (
                routine_only
                and covered is not None
                and covered + _SAME_END_SECONDS >= ends
            ):
                worth = False  # a pause that closes every request already says it
            shown = known
            if worth:
                shown = ends if known is None else max(ends, known)
                if routine_only:
                    self._announced_routine_end = shown
                else:
                    self._announced_pause_end = shown
                    self._announced_ban = self._announced_ban or banned
        if not worth or shown is None:
            return False
        until = time.strftime("%H:%M:%S", time.localtime(shown))
        remaining = max(shown - self._wall_seconds(), 0.0)
        if routine_only:
            logger.warning(
                "%s: routine requests are not sent for %.0f s, until %s; the reads that "
                "guard exits still pass, except while a pause of the exchange's own runs [%s]",
                why,
                remaining,
                until,
                tag,
            )
        else:
            logger.warning(
                "%s: no request is sent for %.0f s, until %s [%s]",
                why,
                remaining,
                until,
                tag,
            )
        return True

    def _announce_pause_ended(self) -> None:
        """The one INFO after a pause, at the first request that finds the gate open."""
        with self._pause_lock:
            ended = self._announced_pause_end or self._announced_routine_end
            self._announced_pause_end = None
            self._announced_routine_end = None
            self._announced_ban = False
        if ended is not None:
            logger.info(
                "The exchange's pause is over: requests resume [rate-limit-end]"
            )

    def _server_now_ms(self) -> int:
        return int(self._wall_seconds() * 1000)
