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


def test_rsi_strictly_decreasing_prices_yields_zero():
    rsi = RSI(period=14)
    decreasing_prices = [100.0 - i for i in range(20)]
    outputs = [rsi.update(v) for v in decreasing_prices]

    # Every loss, zero gains ever seen: avg_gain stays 0, RSI = 0.0
    for value in outputs[14:]:
        assert value == 0.0


def test_rsi_flat_prices_yields_fifty():
    rsi = RSI(period=14)
    flat_prices = [100.0] * 20
    outputs = [rsi.update(v) for v in flat_prices]

    # Zero gain and zero loss on every bar: neutral RSI = 50.0
    for value in outputs[14:]:
        assert value == 50.0


def test_rsi_period_one():
    rsi = RSI(period=1)
    # 1st call: establishes previous close
    assert rsi.update(100.0) is None
    # 2nd call: delta = +5 -> gain=5, loss=0 -> seeds immediately -> 100.0
    assert rsi.update(105.0) == pytest.approx(100.0)
    # 3rd call: delta = -2 -> gain=0, loss=2 -> recurrence -> 0.0
    assert rsi.update(103.0) == pytest.approx(0.0)
    # 4th call: delta = 0 -> gain=0, loss=0 -> recurrence -> 50.0
    assert rsi.update(103.0) == pytest.approx(50.0)


def test_rsi_large_period_warmup():
    period = 50
    rsi = RSI(period=period)
    prices = [100.0 + (i % 5) for i in range(period + 10)]
    outputs = [rsi.update(v) for v in prices]

    assert outputs[:period] == [None] * period
    assert outputs[period] is not None
    assert 0.0 <= outputs[period] <= 100.0


def test_rsi_negative_price_series():
    # E.g. Spread indicator or negative commodities (oil futures)
    rsi = RSI(period=5)
    negative_prices = [-50.0, -45.0, -48.0, -40.0, -42.0, -38.0, -35.0, -39.0]
    outputs = [rsi.update(v) for v in negative_prices]

    assert outputs[:5] == [None] * 5
    for val in outputs[5:]:
        assert val is not None
        assert 0.0 <= val <= 100.0


def test_rsi_extreme_scales():
    # Huge price scale: 10^9
    huge_rsi = RSI(period=5)
    huge_prices = [1e9 + i * 1e7 for i in range(10)]
    huge_outs = [huge_rsi.update(v) for v in huge_prices]
    for val in huge_outs[5:]:
        assert val == pytest.approx(100.0)

    # Micro price scale: 10^-8
    micro_rsi = RSI(period=5)
    micro_prices = [1e-8 + i * 1e-9 for i in range(10)]
    micro_outs = [micro_rsi.update(v) for v in micro_prices]
    for val in micro_outs[5:]:
        assert val == pytest.approx(100.0)


def test_rsi_oscillating_prices_converges_within_bounds():
    rsi = RSI(period=6)
    prices = [100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0]
    outputs = [rsi.update(v) for v in prices]
    for val in outputs[6:]:
        assert val is not None
        assert 0.0 < val < 100.0


def test_rsi_matches_independent_mathematical_reference():
    # Standalone reference implementation of Wilder's RSI formula
    def reference_wilder_rsi(prices: list[float], period: int) -> list[float | None]:
        if len(prices) <= period:
            return [None] * len(prices)
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [max(d, 0.0) for d in deltas]
        losses = [max(-d, 0.0) for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        results: list[float | None] = [None] * period

        def calc(ag: float, al: float) -> float:
            if al == 0.0:
                return 100.0 if ag > 0.0 else 50.0
            return 100.0 - 100.0 / (1.0 + (ag / al))

        results.append(calc(avg_gain, avg_loss))
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            results.append(calc(avg_gain, avg_loss))
        return results

    series = CLOSES * 2  # 40 bars
    period = 14
    rsi = RSI(period=period)
    actual = [rsi.update(v) for v in series]
    expected = reference_wilder_rsi(series, period)

    assert len(actual) == len(expected)
    for act, exp in zip(actual, expected, strict=True):
        if exp is None:
            assert act is None
        else:
            assert act == pytest.approx(exp, rel=1e-12)


def test_rsi_peek_provisional_stress_pure_state():
    rsi = RSI(period=14)
    reference = RSI(period=14)

    for step, v in enumerate(CLOSES):
        # Stress with chaotic probes before each commit
        for probe in (-1e9, 1e9, 0.0, v - 10.0, v + 10.0, v):
            rsi.peek_provisional(probe)

        # Committed update must match an unpolluted instance exactly
        res_act = rsi.update(v)
        res_ref = reference.update(v)
        if res_ref is None:
            assert res_act is None
        else:
            assert res_act == pytest.approx(res_ref, rel=1e-12)


def test_rsi_peek_provisional_extreme_directional_moves():
    rsi = RSI(period=5)
    for v in CLOSES[:6]:
        rsi.update(v)

    # Astronomical up move -> provisional RSI approaches 100
    assert rsi.peek_provisional(CLOSES[5] + 1e6) == pytest.approx(100.0, rel=1e-3)
    # Astronomical down move -> provisional RSI approaches 0
    assert rsi.peek_provisional(CLOSES[5] - 1e6) == pytest.approx(0.0, abs=1e-3)


def test_rsi_batch_vs_incremental_identity():
    series = CLOSES * 2
    single_instance = RSI(period=14)
    incremental_results = [single_instance.update(v) for v in series]

    batch_results = []
    for i in range(1, len(series) + 1):
        fresh = RSI(period=14)
        out = None
        for v in series[:i]:
            out = fresh.update(v)
        batch_results.append(out)

    assert incremental_results == batch_results
