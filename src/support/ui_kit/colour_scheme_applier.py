"""`EPIC-043B` — asks Qt to draw the colour scheme the person chose.

Qt's own call, `QStyleHints.setColorScheme` (Qt 6.8+), makes the platform draw its own light or
dark palette; `unsetColorScheme` gives the choice back to the system. The application writes no
palette, style sheet or colour (`ui-presentation-rule.md` §1; `EPIC-033` D8 as amended), and
every widget, the charts' chrome included, follows the change through `QEvent.PaletteChange`,
so a choice applies without a restart.

Where the platform theme does not implement the request (Qt's offscreen, minimal and Linux xcb
platforms do not, measured on PySide6 6.11.1 in `EPIC-043A`) the call is accepted and nothing
changes: `colorScheme()` stays `Unknown`. That is the platform's, so the applier only logs what
Qt then reports and never second-guesses it.

Capability: Apply the chosen colour scheme through Qt, never a palette
    Also: setColorScheme, dark mode, apply theme, unsetColorScheme
    Use: ColourSchemeApplier, ColourSchemeHints
    User: src/presentation/ui/remembered_state_wiring.py
    Status: stable
"""

from __future__ import annotations

import logging
from typing import Protocol

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)

logger = logging.getLogger("App.UiKit.ColourScheme")

_QT_SCHEMES = {
    ColourSchemeChoice.LIGHT: Qt.ColorScheme.Light,
    ColourSchemeChoice.DARK: Qt.ColorScheme.Dark,
}


class ColourSchemeHints(Protocol):
    """The three calls of Qt's `QStyleHints` this needs (`QGuiApplication.styleHints()`)."""

    def setColorScheme(self, scheme: Qt.ColorScheme) -> None: ...

    def unsetColorScheme(self) -> None: ...

    def colorScheme(self) -> Qt.ColorScheme: ...


class ColourSchemeApplier:
    """@brief Applies the preference now, and again on every change."""

    def __init__(
        self, preference: ColourSchemePreference, hints: ColourSchemeHints
    ) -> None:
        self._preference = preference
        self._hints = hints
        self._unsubscribe = preference.subscribe(self._on_choice)

    def apply_now(self) -> None:
        """Draws the chosen scheme; System hands the choice back to the platform."""
        self._on_choice(self._preference.choice)

    def stop(self) -> None:
        self._unsubscribe()

    def _on_choice(self, choice: ColourSchemeChoice) -> None:
        scheme = _QT_SCHEMES.get(choice)
        if scheme is None:
            self._hints.unsetColorScheme()
        else:
            self._hints.setColorScheme(scheme)
        logger.info(
            "Colour scheme %s asked of Qt; Qt now reports %s",
            choice.value,
            self._hints.colorScheme().name,
        )
