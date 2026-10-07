"""`EPIC-029` ADR D15 — how `LiveChartCoordinator` reports back to its chart."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


@dataclass(frozen=True)
class LiveChartCallbacks:
    """Each one is bound to a Qt signal of the chart that owns the
    coordinator: the coordinator runs on a worker thread and never touches a
    widget (`BUG-031`)."""

    #: `(symbol, candles, volume, raw rows oldest first)`: the candles and
    #: volume as `map_klines`/`map_volume` shape them, and the `MarketData`
    #: rows an overlay replays (`EPIC-022E`).
    history_ready: Callable[[str, list, list, list], None]
    #: The load asked with this token settled (drawn, empty or failed).
    #: Never called once the token is cancelled (`BUG-150`).
    load_finished: Callable[[CancellationToken], None]
    #: `(the request's token, a line)`: the chart matches the token to its
    #: current request, so a report that was on its way when the request was
    #: replaced (a new symbol, a Retry) moves nothing (`EPIC-034G`).
    stream_started: Callable[[CancellationToken, str], None]
    #: `(token, headline, detail)`: what failed as a sentence, and the technical
    #: text behind Details… (`BOT-169`); never one string with the exception.
    stream_failed: Callable[[CancellationToken, str, str], None]
    log: Callable[[str], None]
