"""Unit tests for BOT-098F6C's pure drag/wheel viewport math — no QApplication
needed, matching acceptance criterion 1 ("verify pure viewport math,
clamping, final range... independently of rendering")."""

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_viewport_gestures import (
    resolve_drag_viewport,
    resolve_wheel_viewport,
)

_CANDLE_COUNT = 1000


class TestResolveDragViewport:
    def test_dragging_right_reveals_earlier_candles(self):
        start, end = resolve_drag_viewport(
            100.0, 250.0, candle_count=_CANDLE_COUNT, delta_px=100.0, width_px=1600.0
        )
        assert start < 100.0
        assert (end - start) == 150.0

    def test_dragging_left_reveals_later_candles(self):
        start, end = resolve_drag_viewport(
            100.0, 250.0, candle_count=_CANDLE_COUNT, delta_px=-100.0, width_px=1600.0
        )
        assert start > 100.0
        assert (end - start) == 150.0

    def test_clamps_to_zero_at_the_left_edge(self):
        # Positive delta_px (drag right) reveals earlier candles, pushing
        # the viewport toward index 0.
        start, end = resolve_drag_viewport(
            10.0, 160.0, candle_count=_CANDLE_COUNT, delta_px=2000.0, width_px=1600.0
        )
        assert start == 0.0
        assert end == 150.0

    def test_clamps_to_candle_count_at_the_right_edge(self):
        # Negative delta_px (drag left) reveals later candles, pushing the
        # viewport toward candle_count.
        start, end = resolve_drag_viewport(
            900.0, 1000.0, candle_count=_CANDLE_COUNT, delta_px=-2000.0, width_px=1600.0
        )
        assert end == float(_CANDLE_COUNT)
        assert start == _CANDLE_COUNT - 100.0

    def test_zero_width_or_candle_count_is_a_no_op(self):
        assert resolve_drag_viewport(
            10.0, 20.0, candle_count=0, delta_px=50.0, width_px=1600.0
        ) == (10.0, 20.0)
        assert resolve_drag_viewport(
            10.0, 20.0, candle_count=_CANDLE_COUNT, delta_px=50.0, width_px=0.0
        ) == (10.0, 20.0)


class TestResolveWheelViewport:
    def test_zooming_in_shrinks_the_visible_span(self):
        start, end = resolve_wheel_viewport(
            0.0, 200.0, candle_count=_CANDLE_COUNT, wheel_steps=1.0, cursor_fraction=0.5
        )
        assert (end - start) < 200.0

    def test_zooming_out_grows_the_visible_span(self):
        start, end = resolve_wheel_viewport(
            0.0,
            200.0,
            candle_count=_CANDLE_COUNT,
            wheel_steps=-1.0,
            cursor_fraction=0.5,
        )
        assert (end - start) > 200.0

    def test_the_candle_under_the_cursor_stays_under_the_cursor(self):
        start, end = resolve_wheel_viewport(
            100.0,
            300.0,
            candle_count=_CANDLE_COUNT,
            wheel_steps=1.0,
            cursor_fraction=0.25,
        )
        anchor_before = 100.0 + 0.25 * 200.0
        anchor_after = start + 0.25 * (end - start)
        assert abs(anchor_after - anchor_before) < 1e-9

    def test_never_zooms_in_below_the_minimum_visible_span(self):
        start, end = resolve_wheel_viewport(
            0.0, 1.0, candle_count=_CANDLE_COUNT, wheel_steps=50.0, cursor_fraction=0.5
        )
        assert (end - start) >= 1.0

    def test_never_zooms_out_past_the_full_candle_count(self):
        start, end = resolve_wheel_viewport(
            400.0,
            600.0,
            candle_count=_CANDLE_COUNT,
            wheel_steps=-50.0,
            cursor_fraction=0.5,
        )
        assert start == 0.0
        assert end == float(_CANDLE_COUNT)

    def test_cursor_fraction_outside_0_1_is_clamped(self):
        in_bounds = resolve_wheel_viewport(
            100.0,
            300.0,
            candle_count=_CANDLE_COUNT,
            wheel_steps=1.0,
            cursor_fraction=1.0,
        )
        out_of_bounds = resolve_wheel_viewport(
            100.0,
            300.0,
            candle_count=_CANDLE_COUNT,
            wheel_steps=1.0,
            cursor_fraction=5.0,
        )
        assert in_bounds == out_of_bounds

    def test_zero_candle_count_is_a_no_op(self):
        assert resolve_wheel_viewport(
            10.0, 20.0, candle_count=0, wheel_steps=1.0, cursor_fraction=0.5
        ) == (10.0, 20.0)
