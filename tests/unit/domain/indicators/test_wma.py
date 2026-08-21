import pytest
from Sagittarius_Elite_Warrior.src.domain.indicators.wma import WMA

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


def test_wma_returns_none_during_warmup():
    # Arrange
    wma = WMA(period=5)

    # Act
    outputs = [wma.update(v) for v in CLOSES[:4]]

    # Assert — first `period - 1` calls have no seed yet
    assert outputs == [None] * 4


def test_wma_matches_reference_values():
    # Arrange
    wma = WMA(period=3)

    # Act — feed the first 5 values
    outputs = [wma.update(v) for v in CLOSES[:5]]

    # Assert
    # WMA(3) for [44.34, 44.09, 44.15] = (44.34*1 + 44.09*2 + 44.15*3) / 6
    # = 44.16166666666667
    # WMA(3) for [44.09, 44.15, 43.61] = (44.09*1 + 44.15*2 + 43.61*3) / 6
    # = 43.87
    # WMA(3) for [44.15, 43.61, 44.33] = (44.15*1 + 43.61*2 + 44.33*3) / 6
    # = 44.06
    assert outputs[0] is None
    assert outputs[1] is None
    assert outputs[2] == pytest.approx(44.16166666666667, rel=1e-9)
    assert outputs[3] == pytest.approx(43.87, rel=1e-9)
    assert outputs[4] == pytest.approx(44.06, rel=1e-9)


def test_wma_constant_input_converges_to_input():
    # Arrange
    wma = WMA(period=5)
    constant_price = 100.0

    # Act
    outputs = [wma.update(constant_price) for _ in range(10)]

    # Assert — once seeded, WMA of a never-changing input equals that input
    assert outputs[3] is None
    for value in outputs[4:]:
        assert value == pytest.approx(constant_price)


def test_wma_invalid_period_raises():
    with pytest.raises(ValueError, match="WMA period must be positive"):
        WMA(period=0)

    with pytest.raises(ValueError, match="WMA period must be positive"):
        WMA(period=-5)


def test_wma_peek_provisional_returns_none_during_warmup():
    wma = WMA(period=5)
    for v in CLOSES[:2]:
        wma.update(v)

    # 2 committed + 1 provisional = 3, still short of period=5.
    assert wma.peek_provisional(999.0) is None


def test_wma_peek_provisional_matches_what_update_would_return_while_filling():
    # Committed window not yet full (4 of 5) — provisional must extend it,
    # not slide it, same as update() would.
    provisional_side = WMA(period=5)
    commit_side = WMA(period=5)
    for v in CLOSES[:4]:
        provisional_side.update(v)
        commit_side.update(v)

    next_value = CLOSES[4]
    assert provisional_side.peek_provisional(next_value) == commit_side.update(
        next_value
    )


def test_wma_peek_provisional_matches_what_update_would_return_once_full():
    # Committed window already full (5 of 5) — provisional must slide the
    # window (drop oldest), same as update() would.
    provisional_side = WMA(period=5)
    commit_side = WMA(period=5)
    for v in CLOSES[:6]:
        provisional_side.update(v)
        commit_side.update(v)

    next_value = CLOSES[6]
    assert provisional_side.peek_provisional(next_value) == commit_side.update(
        next_value
    )


def test_wma_peek_provisional_never_mutates_state():
    wma = WMA(period=5)
    reference = WMA(period=5)
    for v in CLOSES[:6]:
        wma.update(v)
        reference.update(v)

    for probe in (1.0, 999.0, -50.0, CLOSES[6]):
        wma.peek_provisional(probe)

    assert wma.update(CLOSES[6]) == reference.update(CLOSES[6])
