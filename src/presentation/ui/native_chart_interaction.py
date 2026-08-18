"""Pure interaction contracts for native marker LOD and crosshair snapping."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_marker_snapshot import (
    NativeChartMarker,
    NativeChartMarkerDirection,
    NativeChartMarkerKind,
)


@dataclass(frozen=True, slots=True)
class NativeMarkerDisplayPoint:
    """One rendered marker that preserves one and only one semantic kind."""

    candle_index: int
    price: float
    rgba: int
    kind: NativeChartMarkerKind
    direction: NativeChartMarkerDirection
    represented_count: int


def select_native_marker_display(
    markers: Sequence[NativeChartMarker],
    *,
    viewport_start: float,
    viewport_end: float,
    logical_pixel_width: float,
    device_pixel_ratio: float = 1.0,
) -> tuple[NativeMarkerDisplayPoint, ...]:
    """LOD markers per physical column without crossing semantic boundaries."""
    if viewport_end <= viewport_start:
        raise ValueError("marker viewport must be increasing")
    if logical_pixel_width <= 0 or device_pixel_ratio <= 0:
        raise ValueError("marker render dimensions must be positive")

    physical_width = max(1, math.floor(logical_pixel_width * device_pixel_ratio))
    span = viewport_end - viewport_start
    grouped: dict[
        tuple[int, NativeChartMarkerKind, int, NativeChartMarkerDirection],
        list[NativeChartMarker],
    ] = {}
    for marker in markers:
        if not viewport_start <= marker.candle_index < viewport_end:
            continue
        column = min(
            physical_width - 1,
            max(
                0,
                math.floor(
                    (marker.candle_index - viewport_start) / span * physical_width
                ),
            ),
        )
        key = (column, marker.kind, marker.rgba, marker.direction)
        grouped.setdefault(key, []).append(marker)

    return tuple(
        NativeMarkerDisplayPoint(
            candle_index=group[-1].candle_index,
            price=group[-1].price,
            rgba=group[-1].rgba,
            kind=group[-1].kind,
            direction=group[-1].direction,
            represented_count=len(group),
        )
        for _key, group in sorted(grouped.items(), key=lambda item: item[0])
    )


def resolve_native_crosshair_candle(
    pointer_x: float,
    *,
    logical_pixel_width: float,
    viewport_start: float,
    viewport_end: float,
    candle_count: int,
) -> int:
    """Snap an item-local pointer coordinate to a real visible candle."""
    if candle_count <= 0:
        raise ValueError("crosshair requires at least one candle")
    if logical_pixel_width <= 0 or viewport_end <= viewport_start:
        raise ValueError("crosshair viewport must have positive dimensions")

    ratio = min(1.0, max(0.0, pointer_x / logical_pixel_width))
    sample = viewport_start + ratio * (viewport_end - viewport_start)
    first_visible = max(0, min(candle_count - 1, math.floor(viewport_start)))
    last_visible = max(
        first_visible,
        min(candle_count - 1, math.ceil(viewport_end) - 1),
    )
    return min(last_visible, max(first_visible, math.floor(sample)))
