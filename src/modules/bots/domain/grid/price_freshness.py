"""`EPIC-035A` — how old a price may be before a bot stops trusting its feed.

A stop loss and a take profit are the only price-driven exits. They watch ticks;
a feed that goes quiet looks, to them, exactly like a flat market. This rule
compares the age of the last tick with a limit, on a **monotonic** clock's
seconds, so a wall-clock step (NTP, sleep, a manual change) can neither fire it
nor hide it.

Binance pushes a kline update about every two seconds while a pair trades. The
limits are therefore tens of seconds, which is many missed pushes and not a
quiet minute on a thin pair:

  · `PRICE_STALE_AFTER_SECONDS` — a bot that has heard ticks and then hears
    none for this long halts.
  · `PRICE_START_GRACE_SECONDS` — a bot that has not yet heard its first tick
    waits this long for the stream to open, then halts. It is longer than a
    connect and a subscribe take, and bounded: a stream that never opens must
    end in a named halt, not in a bot that waits for ever.
"""

from __future__ import annotations

PRICE_STALE_AFTER_SECONDS: float = 60.0
PRICE_START_GRACE_SECONDS: float = 60.0


def price_is_stale(last_tick_at: float, now: float, limit: float) -> bool:
    """Whether a tick heard at `last_tick_at` is `limit` seconds old at `now`.

    The boundary is stale: "no tick for N seconds" is true at N.

    @raise ValueError `limit` is not positive: a limit that cannot be met would
    halt every bot on its first check."""
    if limit <= 0:
        raise ValueError(f"the staleness limit must be positive, got {limit}")
    return now - last_tick_at >= limit
