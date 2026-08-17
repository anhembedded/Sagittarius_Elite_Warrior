"""Serializer for the immutable native chart snapshot ABI."""

from __future__ import annotations

import struct
import sys
from array import array
from collections.abc import Sequence
from itertools import pairwise

from PySide6.QtCore import QByteArray

_SNAPSHOT_MAGIC = b"SGCH"
_SNAPSHOT_ABI_VERSION = 1
_SNAPSHOT_HEADER_BYTES = 24
_SNAPSHOT_HEADER = struct.Struct("<4sHHQQ")


def pack_native_ohlcv_snapshot(
    *,
    revision: int,
    timestamps: Sequence[int],
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> QByteArray:
    """Pack strictly ordered UTC-ms OHLCV arrays into native snapshot ABI v1."""
    if revision <= 0:
        raise ValueError("snapshot revision must be positive")

    candle_count = len(timestamps)
    arrays = (opens, highs, lows, closes, volumes)
    if any(len(values) != candle_count for values in arrays):
        raise ValueError("all native chart snapshot arrays must have equal length")
    if any(current <= previous for previous, current in pairwise(timestamps)):
        raise ValueError("native chart timestamps must increase strictly")

    payload = bytearray(
        _SNAPSHOT_HEADER.pack(
            _SNAPSHOT_MAGIC,
            _SNAPSHOT_ABI_VERSION,
            _SNAPSHOT_HEADER_BYTES,
            revision,
            candle_count,
        )
    )
    payload.extend(_little_endian_array_bytes("q", timestamps))
    for values in arrays:
        payload.extend(_little_endian_array_bytes("d", values))
    return QByteArray(bytes(payload))


def _little_endian_array_bytes(
    typecode: str, values: Sequence[int] | Sequence[float]
) -> bytes:
    packed_values = array(typecode, values)
    if sys.byteorder != "little":
        packed_values.byteswap()
    return packed_values.tobytes()
