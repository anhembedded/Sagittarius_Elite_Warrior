from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

MarkerPoint = tuple[float, float, str, str, str]
MarkerIdentity = tuple[str, str, str]

_MIN_LABEL_SPACING_PIXELS = 120.0
_FALLBACK_VIEWPORT_WIDTH_PIXELS = 1200.0


@dataclass(frozen=True, slots=True)
class DisplayMarker:
    """One exact or aggregated marker selected for the current viewport."""

    source: MarkerPoint
    represented_count: int


def marker_display_capacity(pixel_width: float) -> int:
    """Return the maximum readable full-label count for a viewport width."""
    safe_width = (
        pixel_width
        if math.isfinite(pixel_width) and pixel_width > 0.0
        else _FALLBACK_VIEWPORT_WIDTH_PIXELS
    )
    return max(1, int(safe_width // _MIN_LABEL_SPACING_PIXELS))


def select_marker_display(
    markers: Sequence[MarkerPoint],
    *,
    min_x: float,
    max_x: float,
    pixel_width: float,
) -> tuple[DisplayMarker, ...]:
    """Select truthful marker detail under the current horizontal pixel budget.

    Sparse viewports retain exact labels. Dense viewports aggregate only equal
    semantic identities (text, color and direction) into stable X buckets.
    """
    if not markers:
        return ()

    capacity = marker_display_capacity(pixel_width)
    if len(markers) <= capacity:
        return tuple(DisplayMarker(marker, 1) for marker in markers)

    identities = tuple(
        dict.fromkeys((marker[2], marker[3], marker[4]) for marker in markers)
    )
    bucket_count = max(1, capacity // len(identities))
    lower_x, upper_x = sorted((min_x, max_x))
    span = upper_x - lower_x

    grouped: dict[tuple[int, MarkerIdentity], list[MarkerPoint]] = defaultdict(list)
    for marker in markers:
        bucket_index = _bucket_index(marker[0], lower_x, span, bucket_count)
        identity = (marker[2], marker[3], marker[4])
        grouped[(bucket_index, identity)].append(marker)

    display = [_aggregate_marker(group) for group in grouped.values()]
    return tuple(sorted(display, key=lambda marker: marker.source[0]))


def _bucket_index(x: float, lower_x: float, span: float, bucket_count: int) -> int:
    if span <= 0.0 or bucket_count == 1:
        return 0
    normalized = (x - lower_x) / span
    return min(bucket_count - 1, max(0, int(normalized * bucket_count)))


def _aggregate_marker(markers: Sequence[MarkerPoint]) -> DisplayMarker:
    count = len(markers)
    representative = markers[count // 2]
    if count == 1:
        return DisplayMarker(representative, 1)
    x, y, text, color, direction = representative
    return DisplayMarker(
        source=(x, y, f"{text} ×{count}", color, direction),
        represented_count=count,
    )
