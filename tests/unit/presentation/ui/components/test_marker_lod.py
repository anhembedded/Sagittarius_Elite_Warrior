from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.marker_lod import (
    select_marker_display,
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
