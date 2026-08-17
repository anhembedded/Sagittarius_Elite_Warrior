from __future__ import annotations

import math

OhlcCandle = tuple[float, float, float, float, float]
VolumeBar = tuple[float, float, bool]

_MIN_PIXELS_PER_BUCKET = 3.0


def select_lod_level(
    visible_sample_count: int,
    viewport_width: float,
    *,
    available_levels: int,
    min_pixels_per_bucket: float = _MIN_PIXELS_PER_BUCKET,
) -> int:
    """Choose a power-of-two LOD without exceeding the pixel budget."""
    if visible_sample_count <= 0 or viewport_width <= 0.0 or available_levels <= 1:
        return 0
    target_bucket_count = max(1, int(viewport_width / min_pixels_per_bucket))
    required_bucket_size = max(
        1,
        math.ceil(visible_sample_count / target_bucket_count),
    )
    level = (required_bucket_size - 1).bit_length()
    return min(level, available_levels - 1)


def aggregate_ohlc_bucket(rows: list[OhlcCandle]) -> OhlcCandle:
    """Aggregate ordered candles while preserving OHLC extremes."""
    first = rows[0]
    last = rows[-1]
    timestamp = first[0] + (last[0] - first[0]) / 2.0
    return (
        timestamp,
        first[1],
        max(row[2] for row in rows),
        min(row[3] for row in rows),
        last[4],
    )


def aggregate_volume_bucket(rows: list[VolumeBar]) -> VolumeBar:
    """Aggregate ordered volume; the last bar supplies display direction."""
    first = rows[0]
    last = rows[-1]
    timestamp = first[0] + (last[0] - first[0]) / 2.0
    return timestamp, sum(row[1] for row in rows), last[2]


def build_ohlc_lod_pyramid(data: list[OhlcCandle]) -> list[list[OhlcCandle]]:
    return _build_pairwise_pyramid(data, aggregate_ohlc_bucket)


def build_volume_lod_pyramid(data: list[VolumeBar]) -> list[list[VolumeBar]]:
    return _build_pairwise_pyramid(data, aggregate_volume_bucket)


def lod_slice_indices(raw_lo: int, raw_hi: int, level: int) -> tuple[int, int]:
    bucket_size = 1 << level
    return raw_lo // bucket_size, (raw_hi + bucket_size - 1) // bucket_size


def _build_pairwise_pyramid(data, aggregate):
    levels = [list(data)]
    while len(levels[-1]) > 1:
        source = levels[-1]
        levels.append(
            [aggregate(source[index : index + 2]) for index in range(0, len(source), 2)]
        )
    return levels
