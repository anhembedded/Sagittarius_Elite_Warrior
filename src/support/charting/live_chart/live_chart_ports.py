"""`EPIC-029` ADR D15 — what a live candle chart needs, as one value
(`code/quality.md` §7)."""

from __future__ import annotations

from dataclasses import dataclass

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
