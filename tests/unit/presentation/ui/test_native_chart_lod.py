from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_lod import (
    aggregate_native_volume,
    build_native_indicator_envelopes,
    native_render_bucket_size,
)


def test_native_volume_lod_preserves_total_source_volume_and_final_direction():
    buckets = aggregate_native_volume(
        [2.0, 3.0, 5.0, 7.0, 11.0],
        [True, False, True, True, False],
        bucket_size=2,
    )

    assert [bucket.total_volume for bucket in buckets] == [5.0, 12.0, 11.0]
    assert [bucket.bullish for bucket in buckets] == [False, True, False]
    assert sum(bucket.total_volume for bucket in buckets) == 28.0


def test_native_indicator_envelope_preserves_peak_and_trough_in_dense_columns():
    envelopes = build_native_indicator_envelopes(
        [100.0, 105.0, 99.0, 102.0, 108.0, 101.0],
        bucket_size=3,
    )

    assert [(item.minimum, item.maximum) for item in envelopes] == [
        (99.0, 105.0),
        (101.0, 108.0),
    ]


def test_native_indicator_lod_uses_physical_pixels_but_sparse_view_is_exact():
    assert (
        native_render_bucket_size(
            viewport_start=0.0,
            viewport_end=1_200.0,
            logical_pixel_width=600.0,
            device_pixel_ratio=1.0,
        )
        == 2
    )
    assert (
        native_render_bucket_size(
            viewport_start=0.0,
            viewport_end=1_200.0,
            logical_pixel_width=600.0,
            device_pixel_ratio=2.0,
        )
        == 1
    )
