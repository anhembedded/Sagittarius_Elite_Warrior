"""`BOT-182` — how far this machine's clock may be from the exchange's before it is called off.

@details One number for the two places that judge the skew, so they cannot drift
apart silently: the headless pre-flight fails a skew of this size or more
(`trading/adapters/preflight/clock_skew_check.py`), and the desktop app tells
the owner of a skew above it. The pre-flight keeps failing closed on real money;
the desktop app only tells, it refuses nothing.
"""

from __future__ import annotations

#: Binance rejects a signed request whose timestamp is more than this many
#: milliseconds ahead of its server time (`-1021`, research R5).
CLOCK_SKEW_LIMIT_MS = 1000
