"""`EPIC-037E` — Binance's request-rate refusals: `429`, then `418` for a client that ignores it.

@details Off until a test sets `limit`. Binance's general-info page (read 2026-10-20): "HTTP 429
return code is used when breaking a request rate limit"; "HTTP 418 ... an IP has been auto-banned
for continuing to send requests after receiving 429 codes", bans "from 2 minutes to 3 days". The
page does not mention `Retry-After`; it is sent here because the owner's log did receive one and
the app reads it (`BUG-216`). The body is the `-1003` Binance sends with a 429. Chosen here: the
window is the exchange's calendar minute (`WeightMeter`'s own), a 429 lasts to its end, and a
request inside that window after a 429 is the "continuing" that earns a 418, and the ban is held
for its `Retry-After` of two minutes (by the meter's clock): a client that obeys it is served again
after it, one that ignores it is refused throughout. The `-1003` texts are the error-code page's.
"""

from __future__ import annotations

from dataclasses import dataclass

BAN_SECONDS = 120


@dataclass
class RateLimitPolicy:
    """`limit` is the weight allowed per minute; `None` leaves the exchange unlimited."""

    limit: int | None = None
    #: Requests answered `429` / `418`, to say what a journey cost.
    limited: int = 0
    banned: int = 0
    _limited_minute: int | None = None
    _banned_until: float = 0.0

    def refusal(
        self, used_weight: int, now: float, seconds_to_next_minute: int
    ) -> tuple[int, object, dict[str, str]] | None:
        """`(status, body, headers)` for a request that must be refused, else `None`.
        @param now the meter's clock in seconds."""
        if self.limit is None:
            return None
        minute = int(now // 60)
        if now < self._banned_until or self._limited_minute == minute:
            if now >= self._banned_until:
                self._banned_until = (
                    now + BAN_SECONDS
                )  # a ban already running is not extended
            self.banned += 1
            return (
                418,
                {
                    "code": -1003,
                    "msg": "Way too many requests; IP banned until "
                    f"{int(self._banned_until * 1000)}. Please use the websocket for "
                    "live updates to avoid bans.",
                },
                {"Retry-After": str(int(self._banned_until - now))},
            )
        if used_weight <= self.limit:
            return None
        self._limited_minute = minute
        self.limited += 1
        return (
            429,
            {
                "code": -1003,
                "msg": f"Too many requests; current limit is {self.limit} requests per minute. "
                "Please use the websocket for live updates to avoid polling the API.",
            },
            {"Retry-After": str(seconds_to_next_minute)},
        )
