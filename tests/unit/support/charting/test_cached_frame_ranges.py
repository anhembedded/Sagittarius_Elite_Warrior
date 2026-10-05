"""The pure range maths behind the cached-frame pan and zoom preview."""

from Sagittarius_Elite_Warrior.src.support.charting.chart_card.cached_frame_interaction import (
    shifted_x_range,
    zoomed_x_range,
)


def test_shifted_x_range_translates_data_opposite_to_drag_direction():
    shifted = shifted_x_range((100.0, 200.0), pixel_delta=160.0, viewport_width=1600.0)

    assert shifted == (90.0, 190.0)


def test_zoomed_x_range_preserves_the_data_point_under_the_cursor():
    zoomed = zoomed_x_range(
        (100.0, 200.0),
        anchor_ratio=0.25,
        preview_scale=2.0,
    )

    assert zoomed == (112.5, 162.5)
