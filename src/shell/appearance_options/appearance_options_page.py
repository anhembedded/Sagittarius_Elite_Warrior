"""Tools → Options → Appearance (`EPIC-043B`).

One choice, the colour scheme: System (the default), Light or Dark. The page changes the
`ColourSchemePreference` only on OK or Apply, never on the click itself (the dialog's own
contract, `IOptionsSection`); the preference tells `ColourSchemeApplier`, which asks Qt, so the
whole window follows without a restart. Nothing here takes long enough to need a coordinator.

An `IOptionsSection` (satisfied structurally).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)

_TITLE = "Appearance"
_GROUP_TEXT = "Colour scheme"
_CHOICE_TEXT = {
    ColourSchemeChoice.SYSTEM: "&System",
    ColourSchemeChoice.LIGHT: "&Light",
    ColourSchemeChoice.DARK: "&Dark",
}


class AppearanceOptionsPage:
    """The colour scheme choice, applied with the dialog's OK or Apply."""

    def __init__(self, preference: ColourSchemePreference) -> None:
        self._preference = preference
        self._listener: Callable[[], None] | None = None
        self._widget = QWidget()
        self._widget.setObjectName("options::appearance")
        self._group = QButtonGroup(self._widget)
        self._buttons: dict[ColourSchemeChoice, QRadioButton] = {}
        box = QGroupBox(_GROUP_TEXT)
        box_layout = QVBoxLayout(box)
        for choice in ColourSchemeChoice:
            button = QRadioButton(_CHOICE_TEXT[choice])
            button.setObjectName(f"options::appearance::{choice.value}")
            button.toggled.connect(self._on_edited)
            self._group.addButton(button)
            box_layout.addWidget(button)
            self._buttons[choice] = button
        layout = QVBoxLayout(self._widget)
        layout.addWidget(box)
        layout.addStretch(1)
        self.revert()

    # -- IOptionsSection -------------------------------------------------------

    @property
    def title(self) -> str:
        return _TITLE

    def widget(self) -> QWidget:
        return self._widget

    def apply(self) -> None:
        self._preference.set_choice(self._chosen())

    def revert(self) -> None:
        saved = self._preference.choice
        for choice, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(choice == saved)
            button.blockSignals(False)

    def is_dirty(self) -> bool:
        return self._chosen() != self._preference.choice

    def validation_message(self) -> str | None:
        return None

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        self._listener = listener

    # -- internals -------------------------------------------------------------

    def _chosen(self) -> ColourSchemeChoice:
        for choice, button in self._buttons.items():
            if button.isChecked():
                return choice
        return self._preference.choice

    def _on_edited(self, checked: bool) -> None:
        if checked and self._listener is not None:
            self._listener()
