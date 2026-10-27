"""`EPIC-047H` — the forming candle of a longer timeframe, folded from the 1m kline ticks the host already receives.

@details The host streams the 1m kline only (`BotPriceWatch`). The candle of 5m, 15m, 1h or 1d that is open
now is the 1m candles of its bucket put together: the open of the first, the highest high and lowest low, the
last close and the sum of the volumes. A 1m tick carries the whole of its minute so far (the exchange's own
kline), so the minute in progress replaces itself on each tick and is added to the closed ones when the next
minute opens.

`complete` is true only when the first minute folded is the bucket's own first minute: a host that started,
or a stream that opened, inside the bucket knows the bucket from then on, and says so.

Not thread-safe: `MarketRecorder` calls it under its lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    FormingCandle,
)

_MINUTE_S = 60


@dataclass(frozen=True, slots=True)
class MinuteTick:
    """One 1m kline as the stream reported it: the minute so far."""

    opened_at: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class _Closed:
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal


def bucket_start(minute: datetime, timeframe: TimeFrame) -> datetime:
    """The open time of the `timeframe` candle that contains `minute` (the epoch's own grid, as the exchange's)."""
    size = timeframe.to_seconds()
    seconds = int(minute.timestamp())
    return datetime.fromtimestamp(seconds - seconds % size, tz=UTC)


class CandleFold:
    def __init__(self, timeframe: TimeFrame) -> None:
        if timeframe.to_seconds() % _MINUTE_S or timeframe.to_seconds() <= 0:
            raise ValueError(f"{timeframe.value} is not a whole number of minutes")
        self._timeframe = timeframe
        self._bucket: datetime | None = None
        self._first_seen: datetime | None = None
        self._closed: _Closed | None = None
        self._current: MinuteTick | None = None

    def add(self, tick: MinuteTick) -> None:
        bucket = bucket_start(tick.opened_at, self._timeframe)
        if self._bucket is not None and bucket < self._bucket:
            return  # a tick of a bucket already left is late and says nothing new
        if bucket != self._bucket:
            self._bucket, self._first_seen = bucket, tick.opened_at
            self._closed, self._current = None, tick
            return
        current = self._current
        if current is None or tick.opened_at == current.opened_at:
            self._current = tick
        elif tick.opened_at > current.opened_at:
            self._closed = self._with(current)
            self._current = tick
        # A tick of an earlier minute than the one in progress is late too.

    def candle(self) -> FormingCandle | None:
        current, bucket = self._current, self._bucket
        if current is None or bucket is None:
            return None
        closed = self._closed
        return FormingCandle(
            timeframe=self._timeframe.value,
            open_time=bucket,
            open_price=current.open_price if closed is None else closed.open_price,
            high_price=current.high_price
            if closed is None
            else max(closed.high_price, current.high_price),
            low_price=current.low_price
            if closed is None
            else min(closed.low_price, current.low_price),
            close_price=current.close_price,
            volume=current.volume if closed is None else closed.volume + current.volume,
            complete=self._first_seen == bucket,
        )

    def _with(self, minute: MinuteTick) -> _Closed:
        closed = self._closed
        if closed is None:
            return _Closed(
                minute.open_price, minute.high_price, minute.low_price, minute.volume
            )
        return _Closed(
            closed.open_price,
            max(closed.high_price, minute.high_price),
            min(closed.low_price, minute.low_price),
            closed.volume + minute.volume,
        )
