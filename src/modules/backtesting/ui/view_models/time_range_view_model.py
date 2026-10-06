"""`EPIC-003F3` — the Backtest screen's time-range and display-timezone
state, lifted out of `BackTestViewModel`.

@details Third slice of `EPIC-003F`, under the same rule as `003F1`/`003F2`:
this class owns the state, `BackTestViewModel` forwards to it, and **no
call site changes**. The proof that the forward is faithful is that
`tests/` needs no edit at all.

@par Why these five belong together
`timeRangePreset` and the two `custom*Text` fields are one answer to one
question — *which candles does this run cover* — and
`logic/time_range_preset.py::resolve_time_range()` already reads all three
together. `displayTimezone` joins them because it is the second half of the
same user decision: the preset picks the window, the timezone decides what
the window's boundaries and every timestamp on screen are *called*
(`BOT-097`). Both option lists live here too, since the label properties
(`selectedTimeRangePresetLabel`, `displayTimezoneLabel`) are pure lookups
into them and splitting the lookup from the table it reads is how a label
starts disagreeing with the value it labels.

@par What deliberately stays on the facade
`openTimeRangePickerRequested` — it is part of `BackTestViewModel`'s block
of "open a modal" signals, the same call made in `003F2` for
`openBotParamsRequested`. It carries user intent, not state.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.time_range_preset import (
    TimeRangePreset,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    get_display_timezone_label,
    get_supported_timezones,
)


class TimeRangeViewModel(QObject):
    """@brief Which window the run covers, and in whose clock it is shown."""

    presetChanged = Signal()
    customStartTextChanged = Signal()
    customEndTextChanged = Signal()
    displayTimezoneChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._preset = TimeRangePreset.ALL_HISTORY.value
        self._custom_start_text = ""
        self._custom_end_text = ""
        self._display_timezone = DEFAULT_TIMEZONE

    # ------------------------------------------------------------------ #
    # Preset
    # ------------------------------------------------------------------ #

    @property
    def presetOptions(self) -> list[dict[str, str]]:
        return [
            {"value": TimeRangePreset.LAST_7_DAYS.value, "label": "Last 7 days"},
            {"value": TimeRangePreset.LAST_30_DAYS.value, "label": "Last 30 days"},
            {"value": TimeRangePreset.LAST_90_DAYS.value, "label": "Last 90 days"},
            {"value": TimeRangePreset.LAST_365_DAYS.value, "label": "Last 365 days"},
            {"value": TimeRangePreset.ALL_HISTORY.value, "label": "All history"},
            {"value": TimeRangePreset.CUSTOM.value, "label": "Custom"},
        ]

    @property
    def preset(self) -> str:
        return self._preset

    @preset.setter
    def preset(self, value: str) -> None:
        if value != self._preset:
            self._preset = value
            self.presetChanged.emit()

    @property
    def selectedPresetLabel(self) -> str:
        """Falls back to the raw value rather than to a placeholder: a preset
        the option list does not know about is a bug worth seeing on screen,
        not one worth hiding behind "Tuỳ chỉnh"."""
        for opt in self.presetOptions:
            if opt.get("value") == self._preset:
                return opt.get("label", self._preset)
        return self._preset

    # ------------------------------------------------------------------ #
    # Custom window
    # ------------------------------------------------------------------ #

    @property
    def customStartText(self) -> str:
        return self._custom_start_text

    @customStartText.setter
    def customStartText(self, value: str) -> None:
        if value != self._custom_start_text:
            self._custom_start_text = value
            self.customStartTextChanged.emit()

    @property
    def customEndText(self) -> str:
        return self._custom_end_text

    @customEndText.setter
    def customEndText(self, value: str) -> None:
        if value != self._custom_end_text:
            self._custom_end_text = value
            self.customEndTextChanged.emit()

    # ------------------------------------------------------------------ #
    # Display timezone (BOT-097)
    # ------------------------------------------------------------------ #

    @property
    def displayTimezoneOptions(self) -> list[dict[str, str]]:
        return get_supported_timezones()

    @property
    def displayTimezone(self) -> str:
        return self._display_timezone

    @displayTimezone.setter
    def displayTimezone(self, value: str) -> None:
        self.set_display_timezone(value)

    @Slot(str)
    def set_display_timezone(self, value: str) -> None:
        if value != self._display_timezone:
            self._display_timezone = value
            self.displayTimezoneChanged.emit()

    @property
    def displayTimezoneLabel(self) -> str:
        return get_display_timezone_label(self._display_timezone)
