"""`EPIC-039C` — the fake Futures exchange's funding schedule and clock.

@details Funding is settled every 8 hours; the first settlement is 8 hours after the
fake's start (`START_MS`, the fixed `time` the market has always answered with), then every
8 hours after that. A test moves the clock with `advance` and takes back the settlement
times it crossed, one per charge. The rate is per symbol, defaulting to the `0.0001` the
market has always reported as its last funding rate.

Binance's pages do not give the settlement schedule per symbol (it can differ), so the
8-hour grid is this fake's choice, not a documented fact.
"""

from __future__ import annotations

from decimal import Decimal

START_MS = 1_700_000_000_000
INTERVAL_MS = 8 * 60 * 60 * 1000
DEFAULT_RATE = Decimal("0.0001")


class FuturesFunding:
    """The clock the funding schedule runs on, and each symbol's rate."""

    def __init__(self) -> None:
        self.now_ms = START_MS
        self.next_time_ms = START_MS + INTERVAL_MS
        self._rates: dict[str, Decimal] = {}

    def rate(self, symbol: str) -> Decimal:
        return self._rates.get(symbol, DEFAULT_RATE)

    def set_rate(self, symbol: str, rate: Decimal) -> None:
        self._rates[symbol] = rate

    def advance(self, milliseconds: int) -> tuple[int, ...]:
        """Moves the clock; returns every settlement time it passed, oldest first."""
        self.now_ms += milliseconds
        settled = []
        while self.next_time_ms <= self.now_ms:
            settled.append(self.next_time_ms)
            self.next_time_ms += INTERVAL_MS
        return tuple(settled)
