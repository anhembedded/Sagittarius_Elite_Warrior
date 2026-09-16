"""The catalogue behind every timeframe picker in this app.

`TimeframePickerOverlay` (QtWidgets) and its `TimeframeCard` delegate used to
live here too — deleted in `EPIC-015` Phase 4 once `ChartToolbar`
(`components/chart_card/chart_toolbar.py`) switched to
`qml/TimeframePicker/`'s `TimeframeToolbar.qml`/`TimeframePickerDialog`, the
last live consumer of the QtWidgets version (`grep -rn
TimeframePickerOverlay src/ tests/` finds none after this change). Every
screen's "choose a candle interval" UI is QML now; this package is catalogue
data only.
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

__all__ = [
    "GROUP_CAPTIONS",
    "GROUP_LABELS",
    "TimeframeGroup",
    "TimeframeOption",
    "all_options",
    "describe",
    "group_options",
    "options_for",
]
