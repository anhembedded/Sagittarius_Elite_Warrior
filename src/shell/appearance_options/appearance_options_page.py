"""Tools → Options → Appearance (`EPIC-043B`, `EPIC-043D`).

Two choices. The colour scheme: System (the default), Light or Dark. And whether a price on the
Market watchlist briefly takes the up or down tone when it ticks (off by default). The page
changes the two preferences only on OK or Apply, never on the click itself (the dialog's own
contract, `IOptionsSection`); the colour scheme tells `ColourSchemeApplier`, which asks Qt, so
the whole window follows without a restart, and the flash tells the table. Nothing here takes
long enough to need a coordinator.

An `IOptionsSection` (satisfied structurally).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.tick_flash_preference import (
    TickFlashPreference,
)

_TITLE = "Appearance"
_GROUP_TEXT = "Colour scheme"
_PRICES_GROUP_TEXT = "Live prices"
_FLASH_TEXT = "&Flash a price when it moves"
_CHOICE_TEXT = {
    ColourSchemeChoice.SYSTEM: "&System",
    ColourSchemeChoice.LIGHT: "&Light",
    ColourSchemeChoice.DARK: "&Dark",
}


class AppearanceOptionsPage:
    """The colour scheme and the tick flash, applied with the dialog's OK or Apply."""

    def __init__(
        self, preference: ColourSchemePreference, tick_flash: TickFlashPreference
    ) -> None:
        self._preference = preference
        self._tick_flash = tick_flash
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
        self._flash = QCheckBox(_FLASH_TEXT)
        self._flash.setObjectName("options::appearance::tick_flash")
        self._flash.toggled.connect(self._on_flash_edited)
        prices = QGroupBox(_PRICES_GROUP_TEXT)
        QVBoxLayout(prices).addWidget(self._flash)
        layout = QVBoxLayout(self._widget)
        layout.addWidget(box)
        layout.addWidget(prices)
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
        self._tick_flash.set_enabled(self._flash.isChecked())

    def revert(self) -> None:
        saved = self._preference.choice
        for choice, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(choice == saved)
            button.blockSignals(False)
        self._flash.blockSignals(True)
        self._flash.setChecked(self._tick_flash.enabled)
        self._flash.blockSignals(False)

    def is_dirty(self) -> bool:
        return (
            self._chosen() != self._preference.choice
            or self._flash.isChecked() != self._tick_flash.enabled
        )

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

    def _on_flash_edited(self, _checked: bool) -> None:
        if self._listener is not None:
            self._listener()
