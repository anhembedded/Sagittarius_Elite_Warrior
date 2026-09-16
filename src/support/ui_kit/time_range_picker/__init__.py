"""The shared "pick a start and an end" dialog and the pure rules behind it."""

from .dialog import TimeRangePickerDialog
from .range_rules import (
    FALLBACK_DAYS,
    PRESET_LABELS,
    PRESET_ORDER,
    RangePresetKind,
    build_summary,
    can_apply,
    format_instant,
    parse_instant,
    resolve_preset,
    seed_range,
)

__all__ = [
    "FALLBACK_DAYS",
    "PRESET_LABELS",
    "PRESET_ORDER",
    "RangePresetKind",
    "TimeRangePickerDialog",
    "build_summary",
    "can_apply",
    "format_instant",
    "parse_instant",
    "resolve_preset",
    "seed_range",
]
