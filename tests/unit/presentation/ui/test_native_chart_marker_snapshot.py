from __future__ import annotations

import struct

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_marker_snapshot import (
    NativeChartMarker,
    NativeChartMarkerDirection,
    NativeChartMarkerKind,
    pack_native_marker_snapshot,
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


def test_marker_snapshot_keeps_truthful_entry_and_exit_semantics():
    snapshot = bytes(
        pack_native_marker_snapshot(
            revision=7,
            candle_count=4,
            markers=(
                _marker(1, NativeChartMarkerKind.LONG_ENTRY),
                _marker(2, NativeChartMarkerKind.LONG_EXIT),
            ),
        )
    )

    assert struct.unpack_from("<4sHHQQQ", snapshot) == (b"SGMK", 1, 32, 7, 4, 2)
    assert struct.unpack_from("<QdIBBH", snapshot, 32)[3:5] == (1, 1)
    assert struct.unpack_from("<QdIBBH", snapshot, 56)[3:5] == (2, 2)
    assert _marker(1, NativeChartMarkerKind.LONG_ENTRY).label == "MUA (LONG)"
    assert _marker(2, NativeChartMarkerKind.LONG_EXIT).label == "ĐÓNG LONG"


@pytest.mark.parametrize(
    ("markers", "message"),
    [
        ((_marker(4, NativeChartMarkerKind.LONG_ENTRY),), "align"),
        (
            (
                _marker(2, NativeChartMarkerKind.LONG_EXIT),
                _marker(1, NativeChartMarkerKind.LONG_ENTRY),
            ),
            "sorted",
        ),
        (
            (
                NativeChartMarker(
                    candle_index=1,
                    price=float("nan"),
                    rgba=0xFF00C087,
                    kind=NativeChartMarkerKind.LONG_ENTRY,
                    direction=NativeChartMarkerDirection.UP,
                ),
            ),
            "finite",
        ),
    ],
)
def test_marker_snapshot_rejects_invalid_business_input(markers, message: str):
    with pytest.raises(ValueError, match=message):
        pack_native_marker_snapshot(revision=1, candle_count=4, markers=markers)
