"""
@brief The concrete `Overlay` subclasses this package ships — one file per
class, per EPIC-007 §3.4.

`ChecklistOverlay` arrived in `EPIC-025` PR 4.3f, the step that needed the
shape `PickerOverlay`'s docstring had named as a candidate and declined to
guess at: multi-select, toggling, and never closing.

@details
`DateRangeOverlay` was a third, deleted in `EPIC-025` PR 4.3c: it hand-drew a
two-month calendar out of one `QPushButton` per day with inline QSS on each,
which is the substitute for `QCalendarWidget` that ADR D20 rules out, and
nothing in `src/` had constructed it since `EPIC-015` gave the job to the QML
time-range picker — only `tools/kit_showcase` did.

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

from .checklist_overlay import ChecklistItem, ChecklistOverlay
from .confirm_overlay import ConfirmOverlay
from .picker_overlay import PickerItem, PickerOverlay

__all__ = [
    "ChecklistItem",
    "ChecklistOverlay",
    "ConfirmOverlay",
    "PickerItem",
    "PickerOverlay",
]
