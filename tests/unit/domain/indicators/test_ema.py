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


def test_ema_explicit_default_alpha_matches_implicit_alpha():
    for period in (2, 5, 12, 14, 50):
        implicit = EMA(period=period)
        explicit = EMA(period=period, alpha=2.0 / (period + 1))
        for v in CLOSES:
            res_imp = implicit.update(v)
            res_exp = explicit.update(v)
            if res_imp is None:
                assert res_exp is None
            else:
                assert res_exp == pytest.approx(res_imp, rel=1e-12)


def test_ema_custom_wilder_alpha_matches_recurrence():
    # Wilder's RMA has alpha = 1 / period
    period = 5
    rma = EMA(period=period, alpha=1.0 / period)
    outputs = [rma.update(v) for v in CLOSES]

    # Seed is SMA over first 5 points
    expected_seed = sum(CLOSES[:5]) / 5.0
    assert outputs[3] is None
    assert outputs[4] == pytest.approx(expected_seed, rel=1e-12)

    # 6th point recurrence: (prev * (5-1) + v) / 5
    expected_6 = (expected_seed * 4.0 + CLOSES[5]) / 5.0
    assert outputs[5] == pytest.approx(expected_6, rel=1e-12)


@pytest.mark.parametrize(
    "invalid_alpha",
    [0.0, -0.1, -1.0, 1.0001, 2.0, float("nan"), float("inf"), float("-inf")],
)
def test_ema_invalid_alpha_raises(invalid_alpha: float):
    with pytest.raises(ValueError, match="EMA alpha must be a finite float in"):
        EMA(period=10, alpha=invalid_alpha)


def test_ema_alpha_one_tracks_input_immediately_post_seed():
    ema = EMA(period=3, alpha=1.0)
    assert ema.update(10.0) is None
    assert ema.update(20.0) is None
    # 3rd point: seed SMA(10, 20, 30) = 20.0
    assert ema.update(30.0) == pytest.approx(20.0)
    # Post-seed: alpha=1.0 means EMA_t = (value - EMA_{t-1}) * 1.0 + EMA_{t-1} = value
    assert ema.update(45.0) == pytest.approx(45.0)
    assert ema.update(12.5) == pytest.approx(12.5)


def test_ema_negative_inputs():
    ema = EMA(period=3)
    series = [-10.0, -20.0, -30.0, -40.0]
    res = [ema.update(v) for v in series]
    assert res[:2] == [None, None]
    assert res[2] == pytest.approx(-20.0)
    # EMA(4th point) = (-40 - (-20)) * (2/4) + (-20) = -30.0
    assert res[3] == pytest.approx(-30.0)


def test_ema_extreme_magnitude_scales():
    # Large scale 1e9
    large_ema = EMA(period=3)
    large_vals = [1e9, 2e9, 3e9, 4e9]
    res_large = [large_ema.update(v) for v in large_vals]
    assert res_large[2] == pytest.approx(2e9)
    assert res_large[3] == pytest.approx(3e9)

    # Small scale 1e-8 (satoshi scale)
    small_ema = EMA(period=3)
    small_vals = [1e-8, 2e-8, 3e-8, 4e-8]
    res_small = [small_ema.update(v) for v in small_vals]
    assert res_small[2] == pytest.approx(2e-8)
    assert res_small[3] == pytest.approx(3e-8)


def test_ema_batch_vs_incremental_identity():
    series = CLOSES * 3  # 60 points
    single_instance = EMA(period=7)
    incremental_results = [single_instance.update(v) for v in series]

    # Rebuilding from scratch up to index i for each point
    batch_results = []
    for i in range(1, len(series) + 1):
        fresh = EMA(period=7)
        out = None
        for v in series[:i]:
            out = fresh.update(v)
        batch_results.append(out)

    assert incremental_results == batch_results
