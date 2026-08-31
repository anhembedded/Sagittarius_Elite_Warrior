"""`EPIC-018D` — tick-to-bar aggregation, pulled out of
`RunHistoricalTickBacktestCommandHandler`: that file mixed three
abstraction levels (CQRS orchestration, this bar-forming policy, and
interval-grid math) in 427 lines, past the >400-line hard threshold in
`architecture-rule.md` §5.4. Matches the precedent `EPIC-003C` set pulling
Policies out of `paper_exchange.py`, and `EPIC-018B` repeated for
`sqlalchemy_repository.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData

#: BUG-022 — a kline's `close_time` is the LAST INSTANT it covers, not the
#: exclusive end of its interval: Binance publishes `next_open - 1ms` (the
#: stored 1s data pairs `open=12:14:59.000` with `close=12:14:59.999`, never
#: `12:15:00.000`). So a tick reaches a bar's end when
#: `close_time + 1ms >= bar_end`, and comparing `close_time >= bar_end`
#: directly is never true for real data — which silently sent the closing
#: tick of EVERY bar down the "missing data" path, evaluating it once
#: provisionally and again on commit with identical state. This is the
#: exchange's own millisecond granularity, not a tolerance: a feed that
#: instead reports `close_time == bar_end` also satisfies the comparison,
#: so both conventions close their bars on the correct tick.
CLOSE_TIME_IS_INCLUSIVE_BY = timedelta(milliseconds=1)


@dataclass
class FormingBar:
    """Running OHLCV aggregation of every tick seen so far inside the bar
    currently forming — never committed to the strategy's Series/indicator
    history until the bar boundary is crossed (BOT-042C)."""

    bar_start: datetime
    bar_end: datetime
    #: BUG-022 — the last absorbed tick's own `close_time`, NOT `bar_end`.
    #: A published kline's `close_time` is the last instant it covers
    #: (`bar_end - 1ms`), so using `bar_end` made every aggregated bar sit
    #: 1ms later than the identical kline Static reads, breaking BOT-076
    #: §3.4's "1 tick per bar must match Static bit-for-bit" cross-check.
    last_tick_close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float

    @staticmethod
    def start(bar_start: datetime, bar_end: datetime, tick: MarketData) -> FormingBar:
        return FormingBar(
            bar_start=bar_start,
            bar_end=bar_end,
            last_tick_close_time=tick.close_time,
            open_price=tick.open_price,
            high_price=tick.high_price,
            low_price=tick.low_price,
            close_price=tick.close_price,
            volume=tick.volume,
            quote_asset_volume=tick.quote_asset_volume,
            number_of_trades=tick.number_of_trades,
            taker_buy_base_asset_volume=tick.taker_buy_base_asset_volume,
            taker_buy_quote_asset_volume=tick.taker_buy_quote_asset_volume,
        )

    def absorb(self, tick: MarketData) -> None:
        self.last_tick_close_time = tick.close_time
        self.high_price = max(self.high_price, tick.high_price)
        self.low_price = min(self.low_price, tick.low_price)
        self.close_price = tick.close_price
        self.volume += tick.volume
        self.quote_asset_volume += tick.quote_asset_volume
        self.number_of_trades += tick.number_of_trades
        self.taker_buy_base_asset_volume += tick.taker_buy_base_asset_volume
        self.taker_buy_quote_asset_volume += tick.taker_buy_quote_asset_volume

    def to_candle(self, symbol: str, interval: str, *, is_closed: bool) -> MarketData:
        return MarketData(
            symbol=symbol,
            interval=interval,
            open_time=self.bar_start,
            open_price=self.open_price,
            high_price=self.high_price,
            low_price=self.low_price,
            close_price=self.close_price,
            volume=self.volume,
            close_time=self.last_tick_close_time,
            quote_asset_volume=self.quote_asset_volume,
            number_of_trades=self.number_of_trades,
            taker_buy_base_asset_volume=self.taker_buy_base_asset_volume,
            taker_buy_quote_asset_volume=self.taker_buy_quote_asset_volume,
            is_closed=is_closed,
        )


def bar_bounds(
    tick_open_time: datetime, interval_seconds: int
) -> tuple[datetime, datetime]:
    """Floors `tick_open_time` to the interval boundary it falls inside,
    returning (bar_start, bar_end) — e.g. a 1s tick at 09:00:23 with
    interval=60s falls inside the [09:00:00, 09:01:00) bar."""
    epoch_seconds = tick_open_time.timestamp()
    bar_start_seconds = epoch_seconds - (epoch_seconds % interval_seconds)
    bar_start = datetime.fromtimestamp(bar_start_seconds, tz=tick_open_time.tzinfo)
    return bar_start, bar_start + timedelta(seconds=interval_seconds)
