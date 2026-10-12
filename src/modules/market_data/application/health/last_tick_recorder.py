"""When each live feed last delivered a candle (`EPIC-038C`).

`MarketTickEvent` fires for every kline update; nothing keeps the latest time
per symbol. This does, on the monotonic clock (a wall-clock jump must not make a
feed look fresh or dead), so the health snapshot answers from memory. One entry
per market and symbol, bounded by the feeds the app has opened.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)


class LastTickRecorder:
    """Subscribed to `MarketTickEvent` by `MarketDataModule.boot()`."""

    def __init__(self, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def on_tick(self, event: MarketTickEvent) -> None:
        key = f"{event.market_type.value}:{event.market_data.symbol}"
        with self._lock:
            self._last[key] = self._monotonic()

    def ages_s(self) -> dict[str, int]:
        """`market:symbol` -> whole seconds since its last candle."""
        now = self._monotonic()
        with self._lock:
            return {
                key: max(0, int(now - at)) for key, at in sorted(self._last.items())
            }
