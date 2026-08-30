"""`BacktestTimeRangeSource` — translates between `BackTestViewModel`'s
preset/custom-range state and the plain `get_*`/`apply` shape
`TimeRangePickerDialog` wants.

Kept apart from `time_range_picker_dialog.py` (the `QDialog` composition
root that constructs this and wires it in) per `architecture-rule.md` §5: a
translation adapter and the widget wiring that constructs it are different
abstraction levels and do not share a file — the same split
`backtest_symbol_picker_source.py`/`symbol_picker_dialog.py` already use.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    describe as describe_timeframe,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT

from ..logic.time_range_preset import TimeRangePreset, resolve_time_range

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

#: `describe_timeframe()` returns `None` for a code the domain no longer
#: recognises (stale remembered state) — the same fallback
#: `data_management_view.py`'s equivalent helper uses.
_FALLBACK_TIMEFRAME_SECONDS = 60


def _parse(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


class BacktestTimeRangeSource:
    """Reads Backtest's *effective* current range — resolved through
    whichever preset is active (`resolve_time_range`, the same function
    `BackTestPresenter` itself uses), not just the raw custom-text fields,
    so opening the picker while e.g. "30 ngày qua" is active seeds it with
    real dates instead of blank fields. Writes an applied pair back as an
    explicit custom range: an explicit start/end coming out of the picker
    *is* what "Tuỳ chỉnh" already means on this screen, whichever preset
    produced those dates while the picker was open.
    """

    def __init__(self, view_model: BackTestViewModel) -> None:
        self._view_model = view_model

    def get_from_text(self) -> str:
        start, _end = self._resolve()
        return start.strftime(DATETIME_FORMAT) if start else ""

    def get_to_text(self) -> str:
        _start, end = self._resolve()
        return end.strftime(DATETIME_FORMAT) if end else ""

    def get_timeframe_seconds(self) -> int:
        option = describe_timeframe(self._view_model.selectedTimeframe)
        return option.seconds if option is not None else _FALLBACK_TIMEFRAME_SECONDS

    def get_timeframe_label(self) -> str:
        return self._view_model.selectedTimeframe

    def apply(self, start_text: str, end_text: str) -> None:
        self._view_model.customStartText = start_text
        self._view_model.customEndText = end_text
        self._view_model.timeRangePreset = TimeRangePreset.CUSTOM.value

    def _resolve(self) -> tuple[datetime | None, datetime | None]:
        preset = TimeRangePreset(self._view_model.timeRangePreset)
        custom_start = _parse(self._view_model.customStartText)
        custom_end = _parse(self._view_model.customEndText)
        return resolve_time_range(preset, datetime.now(UTC), custom_start, custom_end)
