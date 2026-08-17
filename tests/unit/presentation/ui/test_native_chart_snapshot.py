from __future__ import annotations

import struct

import pytest

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_snapshot import (
    pack_native_ohlcv_snapshot,
)


def test_native_snapshot_is_contiguous_little_endian_structure_of_arrays():
    snapshot = bytes(
        pack_native_ohlcv_snapshot(
            revision=7,
            timestamps=[10, 20],
            opens=[1.0, 2.0],
            highs=[3.0, 4.0],
            lows=[0.5, 1.5],
            closes=[2.5, 3.5],
            volumes=[100.0, 200.0],
        )
    )

    assert struct.unpack_from("<4sHHQQ", snapshot) == (b"SGCH", 1, 24, 7, 2)
    assert struct.unpack_from("<2q", snapshot, 24) == (10, 20)
    assert struct.unpack_from("<2d", snapshot, 40) == (1.0, 2.0)
    assert len(snapshot) == 24 + 2 * 48


def test_native_snapshot_rejects_non_monotonic_revision_source_value():
    with pytest.raises(ValueError, match="revision must be positive"):
        pack_native_ohlcv_snapshot(
            revision=0,
            timestamps=[],
            opens=[],
            highs=[],
            lows=[],
            closes=[],
            volumes=[],
        )


def test_native_snapshot_rejects_misaligned_arrays():
    with pytest.raises(ValueError, match="equal length"):
        pack_native_ohlcv_snapshot(
            revision=1,
            timestamps=[10],
            opens=[],
            highs=[1.0],
            lows=[1.0],
            closes=[1.0],
            volumes=[1.0],
        )
