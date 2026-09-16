"""
@brief The concrete `Overlay` subclasses this package ships — one file per
class, per EPIC-007 §3.4.

@details
`Overlay` itself has named these two in its abstract-instantiation
`TypeError` since it was written ("instantiate a subclass (e.g.
ConfirmOverlay, PickerOverlay)"), while neither existed anywhere in the
shipped package — the false statement `BUG-004` was filed for. They live
here rather than beside `Overlay` in `overlay.py` because that file is one
of the two `guards._BASE_DEFINITION_FILES`, which the bare-Qt-base guard
skips wholesale; a concrete subclass put there would be exempt from the
guard for no reason other than its address.
"""

from __future__ import annotations

from .confirm_overlay import ConfirmOverlay
from .date_range_overlay import (
    DEFAULT_PRESETS,
    DateRangeOverlay,
    RangePreset,
)
from .picker_overlay import PickerItem, PickerOverlay

__all__ = [
    "DEFAULT_PRESETS",
    "ConfirmOverlay",
    "DateRangeOverlay",
    "PickerItem",
    "PickerOverlay",
    "RangePreset",
]
