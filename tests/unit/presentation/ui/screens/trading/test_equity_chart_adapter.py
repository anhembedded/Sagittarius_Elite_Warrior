"""`EPIC-021M` §2.4 — `EquitySample` -> `ChartCard`'s `OhlcCandle` tuple."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.equity_chart_adapter import (
    equity_sample_to_candle,
    equity_samples_to_candles,
)


def _sample(minute: int, total_pnl: str) -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 9, 2, 12, minute, tzinfo=UTC),
        wallet_balance=Decimal("1000.00"),
        unrealized_pnl=Decimal(total_pnl),
    )


def test_one_sample_becomes_a_flat_ohlcv_where_all_four_prices_equal_the_total():
    sample = _sample(0, "25.50")

    candle = equity_sample_to_candle(sample)

    t, o, h, low, c = candle
    assert t == sample.captured_at.timestamp()
    assert o == h == low == c == 1025.50


def test_many_samples_map_in_order():
    samples = [_sample(0, "0"), _sample(1, "10"), _sample(2, "-5")]

    candles = equity_samples_to_candles(samples)

    assert [candle[1] for candle in candles] == [1000.0, 1010.0, 995.0]


def test_no_samples_is_an_empty_list_not_an_error():
    assert equity_samples_to_candles([]) == []
