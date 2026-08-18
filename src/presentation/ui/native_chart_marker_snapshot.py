"""Serializer and semantic helpers for native chart marker snapshot ABI v1."""

from __future__ import annotations

import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

from PySide6.QtCore import QByteArray

_MARKER_SNAPSHOT_MAGIC = b"SGMK"
_MARKER_SNAPSHOT_ABI_VERSION = 1
_MARKER_SNAPSHOT_HEADER_BYTES = 32
_MARKER_SNAPSHOT_RECORD_BYTES = 24
_MARKER_SNAPSHOT_HEADER = struct.Struct("<4sHHQQQ")
_MARKER_SNAPSHOT_RECORD = struct.Struct("<QdIBBH")
_RGBA_MAX_VALUE = (1 << 32) - 1


class NativeChartMarkerKind(IntEnum):
    """Truthful order-event semantics shared by Python and native rendering."""

    LONG_ENTRY = 1
    LONG_EXIT = 2
    SHORT_ENTRY = 3
    SHORT_EXIT = 4


class NativeChartMarkerDirection(IntEnum):
    """Marker arrow direction in chart coordinates."""

    UP = 1
    DOWN = 2


_MARKER_LABELS = {
    NativeChartMarkerKind.LONG_ENTRY: "MUA (LONG)",
    NativeChartMarkerKind.LONG_EXIT: "ĐÓNG LONG",
    NativeChartMarkerKind.SHORT_ENTRY: "BÁN (SHORT)",
    NativeChartMarkerKind.SHORT_EXIT: "ĐÓNG SHORT",
}


@dataclass(frozen=True, slots=True)
class NativeChartMarker:
    """One immutable chart event aligned to an OHLCV candle index."""

    candle_index: int
    price: float
    rgba: int
    kind: NativeChartMarkerKind
    direction: NativeChartMarkerDirection

    @property
    def label(self) -> str:
        return _MARKER_LABELS[self.kind]


def pack_native_marker_snapshot(
    *,
    revision: int,
    candle_count: int,
    markers: Sequence[NativeChartMarker],
) -> QByteArray:
    """Pack sorted markers without erasing entry/exit semantics."""
    if revision <= 0:
        raise ValueError("marker snapshot revision must be positive")
    if candle_count < 0:
        raise ValueError("marker candle count must not be negative")

    _validate_markers(markers, candle_count)
    payload = bytearray(
        _MARKER_SNAPSHOT_HEADER.pack(
            _MARKER_SNAPSHOT_MAGIC,
            _MARKER_SNAPSHOT_ABI_VERSION,
            _MARKER_SNAPSHOT_HEADER_BYTES,
            revision,
            candle_count,
            len(markers),
        )
    )
    for marker in markers:
        payload.extend(
            _MARKER_SNAPSHOT_RECORD.pack(
                marker.candle_index,
                marker.price,
                marker.rgba,
                int(marker.kind),
                int(marker.direction),
                0,
            )
        )
    return QByteArray(bytes(payload))


def _validate_markers(markers: Sequence[NativeChartMarker], candle_count: int) -> None:
    previous_index = -1
    for marker in markers:
        if marker.candle_index < 0 or marker.candle_index >= candle_count:
            raise ValueError("marker candle index must align with candle count")
        if marker.candle_index < previous_index:
            raise ValueError("markers must be sorted by candle index")
        if not math.isfinite(marker.price):
            raise ValueError("marker price must be finite")
        if marker.rgba < 0 or marker.rgba > _RGBA_MAX_VALUE:
            raise ValueError("marker rgba must fit an unsigned 32-bit integer")
        try:
            NativeChartMarkerKind(marker.kind)
        except ValueError as error:
            raise ValueError("marker kind is not supported") from error
        try:
            NativeChartMarkerDirection(marker.direction)
        except ValueError as error:
            raise ValueError("marker direction is not supported") from error
        previous_index = marker.candle_index
