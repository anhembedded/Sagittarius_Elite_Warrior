"""The Run setup panel's pick-one fields, as stock combo boxes (`EPIC-033L`).

Strategy, timeframe, time zone and range were each a value button opening a
picker of their own: a card grid, a grouped tree with pinned favourites, a
searchable list. A choice from a short, fixed list is a drop-down list in the
form it belongs to (MS `ctrl-drop-down-lists`); a picker window for it is
one more window to open and close.

`Choice` is what a field offers; `fill_combo` replaces the offer and selects
the current value without announcing it, so only a person's choice reaches
the view model (the panel listens to `QComboBox.activated`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QComboBox

from .logic.time_range_preset import TimeRangePreset


@dataclass(frozen=True)
class Choice:
    """One item of a field: the value the view model holds, and its words."""

    value: str
    label: str


def fill_combo(combo: QComboBox, choices: Sequence[Choice], current: str) -> None:
    """Offers `choices` with `current` selected; nothing is selected when the
    list does not hold it, so a stale value shows as no choice rather than
    as another one."""
    combo.blockSignals(True)
    combo.clear()
    for choice in choices:
        # Verbatim: a combo box never reads an access key in its items, so
        # an escaped "&&" would show as two ampersands (review of PR #362).
        combo.addItem(choice.label, choice.value)
    combo.setCurrentIndex(combo.findData(current))
    combo.blockSignals(False)


def chosen_value(combo: QComboBox, index: int) -> str | None:
    value = combo.itemData(index)
    return value if isinstance(value, str) else None


def strategy_choices(options: Iterable[dict[str, str]]) -> list[Choice]:
    """The catalogue's strategies by name; a strategy without one by key."""
    choices = []
    for option in options:
        key = str(option.get("key", ""))
        choices.append(Choice(key, str(option.get("name", "")) or key))
    return choices


def timeframe_choices(codes: Iterable[str]) -> list[Choice]:
    return [Choice(code, code) for code in codes]


def timezone_choices(options: Iterable[dict[str, str]]) -> list[Choice]:
    choices = []
    for option in options:
        zone = str(option.get("id", ""))
        choices.append(Choice(zone, str(option.get("label", "")) or zone))
    return choices


def range_choices(presets: Iterable[dict[str, str]]) -> list[Choice]:
    """The presets, and "Custom…" last: choosing it asks for the dates
    (`ui-presentation-rule.md` §4, a command that needs more input)."""
    choices = []
    for preset in presets:
        value = str(preset.get("value", ""))
        label = str(preset.get("label", "")) or value
        if value == TimeRangePreset.CUSTOM.value:
            label = f"{label}…"
        choices.append(Choice(value, label))
    return choices
