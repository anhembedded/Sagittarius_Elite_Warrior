from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_interaction import (
    resolve_native_crosshair_candle,
    select_native_marker_display,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_marker_snapshot import (
    NativeChartMarker,
    NativeChartMarkerDirection,
    NativeChartMarkerKind,
)


def _marker(index: int, kind: NativeChartMarkerKind) -> NativeChartMarker:
    return NativeChartMarker(
        candle_index=index,
        price=100.0 + index,
        rgba=0xFF00C087 if kind == NativeChartMarkerKind.LONG_ENTRY else 0xFFF6465D,
        kind=kind,
        direction=(
            NativeChartMarkerDirection.UP
            if kind == NativeChartMarkerKind.LONG_ENTRY
            else NativeChartMarkerDirection.DOWN
        ),
    )


def test_dense_marker_lod_never_merges_entry_and_exit_contracts():
    display = select_native_marker_display(
        (
            _marker(1, NativeChartMarkerKind.LONG_ENTRY),
            _marker(2, NativeChartMarkerKind.LONG_ENTRY),
            _marker(2, NativeChartMarkerKind.LONG_EXIT),
        ),
        viewport_start=0,
        viewport_end=100,
        logical_pixel_width=1,
    )

    assert [(point.kind, point.represented_count) for point in display] == [
        (NativeChartMarkerKind.LONG_ENTRY, 2),
        (NativeChartMarkerKind.LONG_EXIT, 1),
    ]


def test_crosshair_snaps_and_clamps_to_real_visible_candles():
    arguments = {
        "logical_pixel_width": 100.0,
        "viewport_start": 10.0,
        "viewport_end": 20.0,
        "candle_count": 50,
    }

    assert resolve_native_crosshair_candle(-20.0, **arguments) == 10
    assert resolve_native_crosshair_candle(55.0, **arguments) == 15
    assert resolve_native_crosshair_candle(120.0, **arguments) == 19
