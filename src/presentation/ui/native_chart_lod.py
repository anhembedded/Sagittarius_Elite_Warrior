"""Pure semantic contracts for native volume and indicator render buckets."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NativeVolumeBucket:
    """One visual volume bar retaining its source total and final direction."""

    first_index: int
    end_index: int
    total_volume: float
    bullish: bool


@dataclass(frozen=True, slots=True)
class NativeIndicatorEnvelope:
    """One physical-pixel indicator column preserving both extrema."""

    first_index: int
    end_index: int
    minimum: float
    maximum: float


def native_render_bucket_size(
    *,
    viewport_start: float,
    viewport_end: float,
    logical_pixel_width: float,
    device_pixel_ratio: float,
) -> int:
    """Return samples per physical output column for native render geometry."""
    viewport_span = max(1.0, viewport_end - viewport_start)
    physical_pixel_width = max(1.0, logical_pixel_width * device_pixel_ratio)
    return max(1, math.ceil(viewport_span / math.floor(physical_pixel_width)))


def aggregate_native_volume(
    volumes: Sequence[float],
    bullish: Sequence[bool],
    *,
    bucket_size: int,
) -> tuple[NativeVolumeBucket, ...]:
    """Group volume without losing the total source amount."""
    if bucket_size <= 0:
        raise ValueError("native render bucket size must be positive")
    if len(volumes) != len(bullish):
        raise ValueError("volume and direction arrays must align")

    buckets: list[NativeVolumeBucket] = []
    for first_index in range(0, len(volumes), bucket_size):
        end_index = min(len(volumes), first_index + bucket_size)
        buckets.append(
            NativeVolumeBucket(
                first_index=first_index,
                end_index=end_index,
                total_volume=sum(volumes[first_index:end_index]),
                bullish=bullish[end_index - 1],
            )
        )
    return tuple(buckets)


def build_native_indicator_envelopes(
    values: Sequence[float], *, bucket_size: int
) -> tuple[NativeIndicatorEnvelope, ...]:
    """Group indicator samples while preserving every bucket peak and trough."""
    if bucket_size <= 0:
        raise ValueError("native render bucket size must be positive")

    envelopes: list[NativeIndicatorEnvelope] = []
    for first_index in range(0, len(values), bucket_size):
        end_index = min(len(values), first_index + bucket_size)
        bucket_values = values[first_index:end_index]
        envelopes.append(
            NativeIndicatorEnvelope(
                first_index=first_index,
                end_index=end_index,
                minimum=min(bucket_values),
                maximum=max(bucket_values),
            )
        )
    return tuple(envelopes)
