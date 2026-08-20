import pytest
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA

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


def test_ema_peek_provisional_returns_none_during_warmup():
    ema = EMA(period=12)
    for v in CLOSES[:5]:
        ema.update(v)

    assert ema.peek_provisional(999.0) is None


def test_ema_peek_provisional_matches_what_update_would_return():
    # Two instances warmed to the same committed state — one takes the
    # provisional branch, the other the real commit branch. Same formula,
    # same input, must agree (BOT-042B).
    provisional_side = EMA(period=12)
    commit_side = EMA(period=12)
    for v in CLOSES[:13]:
        provisional_side.update(v)
        commit_side.update(v)

    next_value = CLOSES[13]
    assert provisional_side.peek_provisional(next_value) == commit_side.update(
        next_value
    )


def test_ema_peek_provisional_never_mutates_state():
    ema = EMA(period=12)
    reference = EMA(period=12)
    for v in CLOSES[:13]:
        ema.update(v)
        reference.update(v)

    for probe in (1.0, 999.0, -50.0, CLOSES[13]):
        ema.peek_provisional(probe)

    # However many times (or with what values) peek_provisional was called,
    # the next real update() must be identical to an instance never peeked.
    assert ema.update(CLOSES[13]) == reference.update(CLOSES[13])
