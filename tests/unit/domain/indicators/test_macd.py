import pytest

from Binace_Bot.src.domain.indicators.ema import EMA
from Binace_Bot.src.domain.indicators.macd import MACD

# 40-point close series (extends the 20-point series from test_ema.py/
# test_rsi.py so MACD's longer 26+9-1 warm-up has enough data).
CLOSES = [
    44.34,
    44.09,
    44.15,
    43.61,
    44.33,
    44.83,
    45.10,
    45.42,
    45.84,
    46.08,
    45.89,
    46.03,
    45.61,
    46.28,
    46.28,
    46.00,
    46.03,
    46.41,
    46.22,
    45.64,
    45.90,
    46.10,
    46.50,
    46.80,
    47.00,
    46.70,
    46.40,
    46.90,
    47.20,
    47.50,
    47.10,
    46.80,
    47.00,
    47.30,
    47.60,
    47.90,
    48.10,
    47.80,
    47.50,
    47.90,
]


def test_macd_returns_none_until_slow_and_signal_ready():
    # Arrange
    macd = MACD(fast_period=12, slow_period=26, signal_period=9)

    # Act
    outputs = [macd.update(v) for v in CLOSES]

    # Assert — warm-up length is slow_period + signal_period - 1 = 34
    assert outputs[32] is None
    assert outputs[33] is not None


def test_macd_line_equals_fast_minus_slow_at_every_step():
    # Arrange — MACD composed of internal EMAs vs. two bare EMAs fed the
    # exact same series, independently in this test.
    macd = MACD(fast_period=12, slow_period=26, signal_period=9)
    fast_ema = EMA(period=12)
    slow_ema = EMA(period=26)

    # Act / Assert — structural relationship, not a hardcoded number, so it
    # survives period-constant changes.
    for price in CLOSES:
        macd_value = macd.update(price)
        fast_reading = fast_ema.update(price)
        slow_reading = slow_ema.update(price)
        if macd_value is not None:
            assert macd_value.macd == pytest.approx(fast_reading - slow_reading)


def test_macd_constant_price_yields_zero_everywhere():
    # Arrange
    macd = MACD(fast_period=12, slow_period=26, signal_period=9)
    constant_price = 100.0

    # Act — fast EMA == slow EMA == price when input never varies, so the
    # MACD line, signal line, and histogram all collapse to zero.
    outputs = [macd.update(constant_price) for _ in range(40)]

    # Assert
    for value in outputs[33:]:
        assert value.macd == pytest.approx(0.0, abs=1e-9)
        assert value.signal == pytest.approx(0.0, abs=1e-9)
        assert value.histogram == pytest.approx(0.0, abs=1e-9)


def test_macd_invalid_period_ordering_raises():
    with pytest.raises(ValueError):
        MACD(fast_period=26, slow_period=12)
