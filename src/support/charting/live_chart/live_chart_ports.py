"""`EPIC-029` ADR D15 — what a live candle chart needs, as one value
(`code/quality.md` §7)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@dataclass(frozen=True)
class LiveChartPorts:
    """The candle feed of the chart's market, the worker runner, and the
    chart's identity on the stream."""

    thread_manager: IThreadManager
    feed: ICandleFeed
    #: This chart's own owner on the stream (`BOT-126`): `desk.<venue>`,
    #: `bot.<id>`.
    stream_owner: str
    #: The timeframe the chart opens on.
    interval: str
    #: The market the candles are of. The chart offers only the timeframes this
    #: market can load and opens on the nearest one to `interval` that it can
    #: (`BOT-167`). Required: a caller that forgot it would silently offer `1s`
    #: on Futures.
    market: MarketType
    #: Where a failed sync or stream is told (`BOT-169`).
    notifier: INotifier
    #: The mode whose message bar shows that failure: the owner's `*_ROUTE`.
    scope: str
    #: Whether the chart shows the live chip and its command (`EPIC-034G`).
    #: `False` for a chart that only draws a finished run (a backtest's
    #: replay): its candles are recorded, and a stream would replace them.
    live_commands: bool = True
    #: Seconds on a clock that only moves forward: how old the last live
    #: update is (`EPIC-034G`). A test passes its own.
    clock: Callable[[], float] = field(default=time.monotonic)
