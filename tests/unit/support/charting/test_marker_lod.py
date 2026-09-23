import math

from Sagittarius_Elite_Warrior.src.support.charting.chart_card.marker_lod import (
    MarkerDensityMode,
    classify_marker_density,
    select_marker_display,
    visible_candle_count,
)


def _dense_long_markers(trade_count: int = 930):
    markers = []
    for trade_index in range(trade_count):
        entry_x = float(trade_index * 2)
        markers.extend(
            (
                (entry_x, 100.0, "MUA (LONG)", "#0ECB81", "up"),
                (entry_x + 1.0, 99.0, "ĐÓNG LONG", "#F6465D", "down"),
            )
        )
    return markers


def test_dense_marker_display_obeys_pixel_budget_and_preserves_event_count():
    markers = _dense_long_markers()

    display = select_marker_display(
        markers,
        min_x=0.0,
        max_x=1860.0,
        pixel_width=1200.0,
    )

    assert len(display) <= 10
    assert sum(marker.represented_count for marker in display) == len(markers)
    assert {marker.source[2].split(" ×", 1)[0] for marker in display} == {
        "MUA (LONG)",
        "ĐÓNG LONG",
    }
    assert all(" ×" in marker.source[2] for marker in display)


def test_sparse_marker_display_restores_every_exact_marker():
    markers = _dense_long_markers(trade_count=3)

    display = select_marker_display(
        markers,
        min_x=0.0,
        max_x=6.0,
        pixel_width=1200.0,
    )

    assert [marker.source for marker in display] == markers
    assert all(marker.represented_count == 1 for marker in display)


def test_marker_lod_never_merges_entry_and_exit_semantics():
    markers = _dense_long_markers(trade_count=100)

    display = select_marker_display(
        markers,
        min_x=0.0,
        max_x=200.0,
        pixel_width=360.0,
    )

    labels = {marker.source[2].split(" ×", 1)[0] for marker in display}
    assert labels == {"MUA (LONG)", "ĐÓNG LONG"}
    assert all(marker.represented_count <= 100 for marker in display)


# ---------------------------------------------------------------------------
# `PROP-003` — `MarkerDensityMode` (AC-4)
# ---------------------------------------------------------------------------


def test_visible_candle_count_divides_span_by_spacing():
    assert visible_candle_count(0.0, 300.0, bar_seconds=60.0) == 5.0


def test_visible_candle_count_is_order_independent():
    assert visible_candle_count(300.0, 0.0, bar_seconds=60.0) == 5.0


def test_visible_candle_count_of_unknown_spacing_is_infinite_not_a_crash():
    # `bar_seconds <= 0` means "not known yet" (e.g. before any history
    # loads) — must never raise `ZeroDivisionError`.
    assert math.isinf(visible_candle_count(0.0, 300.0, bar_seconds=0.0))
    assert math.isinf(visible_candle_count(0.0, 300.0, bar_seconds=-1.0))


def test_classify_marker_density_dense_above_eighty_candles():
    assert classify_marker_density(80.01) is MarkerDensityMode.DENSE
    assert classify_marker_density(500.0) is MarkerDensityMode.DENSE


def test_classify_marker_density_medium_from_thirty_to_eighty_inclusive():
    assert classify_marker_density(30.0) is MarkerDensityMode.MEDIUM
    assert classify_marker_density(80.0) is MarkerDensityMode.MEDIUM
    assert classify_marker_density(55.0) is MarkerDensityMode.MEDIUM


def test_classify_marker_density_detailed_below_thirty_candles():
    assert classify_marker_density(29.99) is MarkerDensityMode.DETAILED
    assert classify_marker_density(0.0) is MarkerDensityMode.DETAILED
