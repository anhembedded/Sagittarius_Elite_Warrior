import pytest

from Binace_Bot.src.domain.indicators.ema import EMA

# A fixed 20-point close series with both ups and downs, used across the
# EMA/RSI/MACD test files so their golden values are cross-comparable.
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
]


def test_ema_returns_none_during_warmup():
    # Arrange
    ema = EMA(period=12)

    # Act
    outputs = [ema.update(v) for v in CLOSES[:11]]

    # Assert — first `period - 1` calls have no seed yet
    assert outputs == [None] * 11


def test_ema_matches_reference_values():
    # Arrange
    ema = EMA(period=12)

    # Act — feed the full series, keep the first two post-warm-up outputs
    outputs = [ema.update(v) for v in CLOSES]

    # Assert — independently cross-checked against a separately-implemented
    # (plain list/array-based, not incremental-state-based) reference EMA
    assert outputs[10] is None
    assert outputs[11] == pytest.approx(44.975833333333334, rel=1e-9)
    assert outputs[12] == pytest.approx(45.073397435897434, rel=1e-9)


def test_ema_constant_input_converges_to_input():
    # Arrange
    ema = EMA(period=5)
    constant_price = 100.0

    # Act
    outputs = [ema.update(constant_price) for _ in range(10)]

    # Assert — once seeded, EMA of a never-changing input equals that input
    assert outputs[3] is None
    for value in outputs[4:]:
        assert value == pytest.approx(constant_price)


def test_ema_invalid_period_raises():
    with pytest.raises(ValueError):
        EMA(period=0)
