"""Serializer for immutable native indicator snapshot ABI v1."""

from __future__ import annotations

import math
import struct
import sys
from array import array
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QByteArray

_INDICATOR_SNAPSHOT_MAGIC = b"SGIN"
_INDICATOR_SNAPSHOT_ABI_VERSION = 1
_INDICATOR_SNAPSHOT_HEADER_BYTES = 32
_INDICATOR_SNAPSHOT_HEADER = struct.Struct("<4sHHQQII")
_RGBA_MAX_VALUE = (1 << 32) - 1


@dataclass(frozen=True, slots=True)
class NativeIndicatorSeries:
    """One native-rendered price overlay with immutable sample values."""

    rgba: int
    values: tuple[float, ...]


def pack_native_indicator_snapshot(
    *,
    revision: int,
    candle_count: int,
    series: Sequence[NativeIndicatorSeries],
) -> QByteArray:
    """Pack indicator arrays aligned to the active native OHLCV snapshot."""
    if revision <= 0:
        raise ValueError("indicator snapshot revision must be positive")
    if candle_count < 0:
        raise ValueError("indicator candle count must not be negative")

    _validate_series(series, candle_count)
    payload = bytearray(
        _INDICATOR_SNAPSHOT_HEADER.pack(
            _INDICATOR_SNAPSHOT_MAGIC,
            _INDICATOR_SNAPSHOT_ABI_VERSION,
            _INDICATOR_SNAPSHOT_HEADER_BYTES,
            revision,
            candle_count,
            len(series),
            0,
        )
    )
    payload.extend(_little_endian_array_bytes("I", [item.rgba for item in series]))
    for item in series:
        payload.extend(_little_endian_array_bytes("d", item.values))
    return QByteArray(bytes(payload))


def _validate_series(
    series: Sequence[NativeIndicatorSeries], candle_count: int
) -> None:
    for item in series:
        if item.rgba < 0 or item.rgba > _RGBA_MAX_VALUE:
            raise ValueError("indicator rgba must fit an unsigned 32-bit integer")
        if len(item.values) != candle_count:
            raise ValueError("indicator values must align with candle count")
        if any(not math.isfinite(value) for value in item.values):
            raise ValueError("indicator values must be finite")


def _little_endian_array_bytes(
    typecode: str, values: Sequence[int] | Sequence[float]
) -> bytes:
    packed_values = array(typecode, values)
    if sys.byteorder != "little":
        packed_values.byteswap()
    return packed_values.tobytes()
