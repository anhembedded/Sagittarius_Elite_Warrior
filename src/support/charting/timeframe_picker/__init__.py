"""Every timeframe picker in this app: the catalogue, and the two views on it.

@par Twice around the houses
This package held a QtWidgets `TimeframePickerOverlay` until `EPIC-015` Phase 4
deleted it, when `ChartToolbar` switched to `qml/TimeframePicker/`'s
`TimeframeToolbar.qml` + `TimeframePickerDialog` and the package was left as
catalogue data only. `EPIC-025` PR 4.3k brings the widgets back (ADR D21
deletes the `.qml`), and this time they are here rather than in a `qml/` tree:
`catalogue.py` for the domain-derived grouping, `selection.py` for the state the
two views share, a pill row for the compact row in a chart header, and
`dialog.py` for the full grouped picker. `EPIC-033G` replaced the pill row with
`timeframe_actions.py`: the pinned timeframes as actions for a chart's
toolbar.

The catalogue still takes no Qt import, which is what lets it be read without a
`QApplication` — and what the two new widgets read it through.
"""

from .catalogue import (
    GROUP_CAPTIONS,
    GROUP_LABELS,
    TimeframeGroup,
    TimeframeOption,
    all_options,
    describe,
    group_options,
    options_for,
)
from .dialog import PinnedTimeframes, TimeframePickerDialog
from .selection import (
    PinnedTimeframe,
    TimeframeChoice,
    TimeframeGroupView,
    TimeframeSelection,
)
from .timeframe_actions import TimeframeActions

__all__ = [
    "GROUP_CAPTIONS",
    "GROUP_LABELS",
    "PinnedTimeframe",
    "PinnedTimeframes",
    "TimeframeActions",
    "TimeframeChoice",
    "TimeframeGroup",
    "TimeframeGroupView",
    "TimeframeOption",
    "TimeframePickerDialog",
    "TimeframeSelection",
    "all_options",
    "describe",
    "group_options",
    "options_for",
]
