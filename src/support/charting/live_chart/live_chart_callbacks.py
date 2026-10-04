"""`EPIC-029` ADR D15 — how `LiveChartCoordinator` reports back to its chart."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class LiveChartCallbacks:
    """Each one is bound to a Qt signal of the chart that owns the
    coordinator: the coordinator runs on a worker thread and never touches a
    widget (`BUG-031`)."""

    #: `(symbol, candles, volume, raw rows oldest first)`: the candles and
    #: volume as `map_klines`/`map_volume` shape them, and the `MarketData`
    #: rows an overlay replays (`EPIC-022E`).
    history_ready: Callable[[str, list, list, list], None]
    load_finished: Callable[[], None]
    stream_started: Callable[[str], None]
    stream_failed: Callable[[str], None]
    log: Callable[[str], None]
