from __future__ import annotations

import struct

import pytest

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_indicator_snapshot import (
    NativeIndicatorSeries,
    pack_native_indicator_snapshot,
)


def test_indicator_snapshot_is_contiguous_little_endian_series_of_arrays():
    snapshot = bytes(
        pack_native_indicator_snapshot(
            revision=9,
            candle_count=2,
            series=(
                NativeIndicatorSeries(rgba=0xFF00C087, values=(1.0, 2.0)),
                NativeIndicatorSeries(rgba=0xFFF0B90B, values=(3.0, 4.0)),
            ),
        )
    )

    assert struct.unpack_from("<4sHHQQII", snapshot) == (
        b"SGIN",
        1,
        32,
        9,
        2,
        2,
        0,
    )
    assert struct.unpack_from("<2I", snapshot, 32) == (0xFF00C087, 0xFFF0B90B)
    assert struct.unpack_from("<2d", snapshot, 40) == (1.0, 2.0)
    assert struct.unpack_from("<2d", snapshot, 56) == (3.0, 4.0)


@pytest.mark.parametrize(
    ("series", "message"),
    [
        (
            (NativeIndicatorSeries(rgba=-1, values=(1.0,)),),
            "unsigned 32-bit",
        ),
        (
            (NativeIndicatorSeries(rgba=0xFFFFFFFF + 1, values=(1.0,)),),
            "unsigned 32-bit",
        ),
        (
            (NativeIndicatorSeries(rgba=0xFF00C087, values=()),),
            "align",
        ),
        (
            (NativeIndicatorSeries(rgba=0xFF00C087, values=(float("nan"),)),),
            "finite",
        ),
    ],
)
def test_indicator_snapshot_rejects_invalid_series(series, message: str):
    with pytest.raises(ValueError, match=message):
        pack_native_indicator_snapshot(revision=1, candle_count=1, series=series)
