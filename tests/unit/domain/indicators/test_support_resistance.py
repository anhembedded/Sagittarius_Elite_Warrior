import pytest
from Sagittarius_Elite_Warrior.src.domain.indicators.support_resistance import (
    SupportResistance,
    SupportResistanceValue,
)


def test_support_resistance_rejects_non_positive_period():
    with pytest.raises(ValueError, match="period must be positive"):
        SupportResistance(period=0)
    with pytest.raises(ValueError, match="period must be positive"):
        SupportResistance(period=-5)


def test_support_resistance_warmup_returns_none():
    sr = SupportResistance(period=4)

    assert sr.update(100.0) is None
    assert sr.update(105.0) is None
    assert sr.update(95.0) is None

    result = sr.update(110.0)
    assert result is not None
    assert isinstance(result, SupportResistanceValue)
    assert result.resistance == 110.0
    assert result.support == 95.0
    assert result.midline == pytest.approx((110.0 + 95.0) / 2.0)


def test_support_resistance_rolling_window():
    sr = SupportResistance(period=3)

    # Feed [10, 20, 30] -> max=30, min=10, mid=20
    sr.update(10.0)
    sr.update(20.0)
    r1 = sr.update(30.0)
    assert r1 is not None
    assert r1.resistance == 30.0
    assert r1.support == 10.0
    assert r1.midline == 20.0

    # Feed 25 -> window is [20, 30, 25] -> max=30, min=20, mid=25
    r2 = sr.update(25.0)
    assert r2 is not None
    assert r2.resistance == 30.0
    assert r2.support == 20.0
    assert r2.midline == 25.0

    # Feed 15 -> window is [30, 25, 15] -> max=30, min=15, mid=22.5
    r3 = sr.update(15.0)
    assert r3 is not None
    assert r3.resistance == 30.0
    assert r3.support == 15.0
    assert r3.midline == 22.5


def test_support_resistance_peek_provisional_matches_update_and_does_not_mutate():
    sr = SupportResistance(period=3)
    sr.update(100.0)

    # With only 1 value committed, peek_provisional with 2nd value has len=2 < 3 -> returns None
    assert sr.peek_provisional(105.0) is None

    # Commit 2nd value (110.0)
    sr.update(110.0)

    # Peek with 3rd value (90.0) -> hypothetical window: [100, 110, 90] -> max=110, min=90
    prov1 = sr.peek_provisional(90.0)
    assert prov1 is not None
    assert prov1.resistance == 110.0
    assert prov1.support == 90.0
    assert prov1.midline == 100.0

    # Peek with 120.0 -> hypothetical window: [100, 110, 120] -> max=120, min=100
    prov2 = sr.peek_provisional(120.0)
    assert prov2 is not None
    assert prov2.resistance == 120.0
    assert prov2.support == 100.0
    assert prov2.midline == 110.0

    # Commit 3rd value (90.0) -> real window: [100, 110, 90]
    real = sr.update(90.0)
    assert real is not None
    assert real.resistance == 110.0
    assert real.support == 90.0
    assert real.midline == 100.0
