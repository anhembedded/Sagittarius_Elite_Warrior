from Binace_Bot.src.presentation.ui.components.chart_card.heikin_ashi import (
    to_heikin_ashi,
)


def test_empty_input_returns_empty_list():
    assert to_heikin_ashi([]) == []


def test_first_candle_seeds_ha_open_from_its_own_open_close():
    """First candle has no previous HA candle — HA open seeds from its own O/C."""
    data = [(0.0, 10.0, 12.0, 9.0, 11.0)]
    ha = to_heikin_ashi(data)

    assert len(ha) == 1
    t, ha_open, ha_high, ha_low, ha_close = ha[0]
    assert t == 0.0
    assert ha_close == (10.0 + 12.0 + 9.0 + 11.0) / 4.0  # 10.5
    assert ha_open == (10.0 + 11.0) / 2.0  # seed: avg(open, close) = 10.5


def test_second_candle_ha_open_is_midpoint_of_previous_ha_open_close():
    data = [
        (0.0, 10.0, 12.0, 9.0, 11.0),
        (1.0, 11.0, 13.0, 10.0, 12.0),
    ]
    ha = to_heikin_ashi(data)

    assert len(ha) == 2
    prev_ha_open, prev_ha_close = ha[0][1], ha[0][4]
    assert ha[1][1] == (prev_ha_open + prev_ha_close) / 2.0


def test_ha_high_low_extend_to_include_the_ha_body():
    """HA high/low must never be inside the HA open/close body."""
    data = [(0.0, 10.0, 12.0, 9.0, 11.0), (1.0, 11.0, 13.0, 10.0, 12.0)]
    ha = to_heikin_ashi(data)

    for t, ha_open, ha_high, ha_low, ha_close in ha:
        assert ha_high >= max(ha_open, ha_close)
        assert ha_low <= min(ha_open, ha_close)


def test_preserves_timestamps_and_candle_count():
    data = [(float(i), 100 + i, 105 + i, 95 + i, 102 + i) for i in range(20)]
    ha = to_heikin_ashi(data)

    assert len(ha) == len(data)
    assert [row[0] for row in ha] == [row[0] for row in data]
