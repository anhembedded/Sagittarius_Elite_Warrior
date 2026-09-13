"""The golden master's dataset: 600 hourly bars from a seeded random walk.

A weak sine drift and ±1.5 % per-bar noise, chosen so the 12/26 EMA crossover
whipsaws enough to produce losing trades and a real drawdown, not only a
trend ride. `random.Random` is stable across Python versions for `random()`
and `uniform()`, so the sequence is the same on every machine.

This is a *regression* fixture, not a benchmark: its point is that Phase 3
reproduces these exact numbers, whatever they are.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

SYMBOL = "GOLDUSDT"
INTERVAL = TimeFrame("1h")
BAR_COUNT = 600
SEED = 20260913
START = datetime(2026, 1, 1, tzinfo=UTC)

_INITIAL_PRICE = 1_000.0
_DRIFT_AMPLITUDE = 0.0005
_DRIFT_PERIOD_BARS = 15.0
_NOISE_PER_BAR = 0.015
_MAX_WICK = 0.004
_BASE_VOLUME = 100.0
_VOLUME_SPREAD = 50.0
_PRICE_DECIMALS = 4
_VOLUME_DECIMALS = 3
_TRADE_COUNT_CYCLE = 7
_CLOSE_TIME_GAP = timedelta(seconds=1)


def make_golden_klines() -> list[MarketData]:
    rng = random.Random(SEED)  # noqa: S311 — determinism, not cryptography
    cadence = timedelta(seconds=INTERVAL.to_seconds())
    klines: list[MarketData] = []
    price = _INITIAL_PRICE
    for index in range(BAR_COUNT):
        drift = _DRIFT_AMPLITUDE * math.sin(index / _DRIFT_PERIOD_BARS)
        shock = rng.uniform(-_NOISE_PER_BAR, _NOISE_PER_BAR)
        open_price = price
        close_price = round(open_price * (1.0 + drift + shock), _PRICE_DECIMALS)
        wick_up = rng.uniform(0.0, _MAX_WICK)
        wick_down = rng.uniform(0.0, _MAX_WICK)
        high_price = round(
            max(open_price, close_price) * (1.0 + wick_up), _PRICE_DECIMALS
        )
        low_price = round(
            min(open_price, close_price) * (1.0 - wick_down), _PRICE_DECIMALS
        )
        volume = round(_BASE_VOLUME + _VOLUME_SPREAD * rng.random(), _VOLUME_DECIMALS)
        open_time = START + cadence * index
        klines.append(
            MarketData(
                symbol=SYMBOL,
                interval=INTERVAL.value,
                open_time=open_time,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                close_time=open_time + cadence - _CLOSE_TIME_GAP,
                quote_asset_volume=round(volume * close_price, _VOLUME_DECIMALS),
                number_of_trades=1 + index % _TRADE_COUNT_CYCLE,
                taker_buy_base_asset_volume=round(volume / 2.0, _VOLUME_DECIMALS),
                taker_buy_quote_asset_volume=round(
                    volume * close_price / 2.0, _VOLUME_DECIMALS
                ),
            )
        )
        price = close_price
    return klines
