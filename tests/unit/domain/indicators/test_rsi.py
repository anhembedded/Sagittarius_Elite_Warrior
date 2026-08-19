import pytest

from Sagittarius_Elite_Warrior.src.domain.indicators.rsi import RSI

# Same fixed 20-point close series as test_ema.py.
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


def test_rsi_returns_none_during_warmup():
    # Arrange
    rsi = RSI(period=14)

    # Act — first call seeds previous_close (no delta yet), next 13 calls
    # accumulate gain/loss averages: 14 None outputs total.
    outputs = [rsi.update(v) for v in CLOSES[:14]]

    # Assert
    assert outputs == [None] * 14


def test_rsi_matches_reference_values():
    # Arrange
    rsi = RSI(period=14)

    # Act
    outputs = [rsi.update(v) for v in CLOSES]

    # Assert — independently cross-checked against a separately-implemented
    # (plain list/array-based) reference RSI using the same Wilder recurrence
    assert outputs[13] is None
    assert outputs[14] == pytest.approx(70.46413502109705, rel=1e-9)
    assert outputs[15] == pytest.approx(66.24961855355505, rel=1e-9)


def test_rsi_strictly_increasing_prices_yields_100():
    # Arrange
    rsi = RSI(period=14)
    increasing_prices = [100.0 + i for i in range(16)]

    # Act
    outputs = [rsi.update(v) for v in increasing_prices]

    # Assert — every gain, zero losses ever seen: avg_loss stays 0, RSI = 100
    # exactly (never a ZeroDivisionError from avg_gain/avg_loss).
    for value in outputs[14:]:
        assert value == 100.0


def test_rsi_invalid_period_raises():
    with pytest.raises(ValueError):
        RSI(period=0)


def test_rsi_peek_provisional_returns_none_during_warmup():
    rsi = RSI(period=14)
    for v in CLOSES[:5]:
        rsi.update(v)

    assert rsi.peek_provisional(999.0) is None


def test_rsi_peek_provisional_matches_what_update_would_return():
    provisional_side = RSI(period=14)
    commit_side = RSI(period=14)
    for v in CLOSES[:15]:
        provisional_side.update(v)
        commit_side.update(v)

    next_value = CLOSES[15]
    assert provisional_side.peek_provisional(next_value) == commit_side.update(
        next_value
    )


def test_rsi_peek_provisional_never_mutates_state():
    rsi = RSI(period=14)
    reference = RSI(period=14)
    for v in CLOSES[:15]:
        rsi.update(v)
        reference.update(v)

    for probe in (1.0, 999.0, -50.0, CLOSES[15]):
        rsi.peek_provisional(probe)

    assert rsi.update(CLOSES[15]) == reference.update(CLOSES[15])
