"""
Primitives shared by every kind of user-authored script.

Lives outside `indicator_scripts/` on purpose: cross detection and bar history
are exactly what a future strategy script needs too (a golden cross *is* the
buy trigger), so putting them here means strategy scripting can reuse them
without moving files around later.
"""

from .series import (
    DEFAULT_HISTORY,
    Series,
    constant_series,
    crossed,
    crossed_above,
    crossed_below,
    is_above,
    is_below,
    series_of,
)
from .streak import Streak

__all__ = [
    "DEFAULT_HISTORY",
    "Series",
    "Streak",
    "constant_series",
    "crossed",
    "crossed_above",
    "crossed_below",
    "is_above",
    "is_below",
    "series_of",
]
