"""`EPIC-043B` — the chosen colour scheme is asked of Qt, never drawn by the application."""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.support.ui_kit.colour_scheme_applier import (
    ColourSchemeApplier,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)


class _RecordingHints:
    """The three `QStyleHints` calls the applier makes, recorded in order."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._scheme = Qt.ColorScheme.Unknown

    def setColorScheme(self, scheme: Qt.ColorScheme) -> None:  # noqa: N802
        self.calls.append(f"set {scheme.name}")
        self._scheme = scheme

    def unsetColorScheme(self) -> None:  # noqa: N802
        self.calls.append("unset")
        self._scheme = Qt.ColorScheme.Unknown

    def colorScheme(self) -> Qt.ColorScheme:  # noqa: N802
        return self._scheme


def test_system_hands_the_choice_back_to_the_platform() -> None:
    hints = _RecordingHints()

    ColourSchemeApplier(ColourSchemePreference(), hints).apply_now()

    assert hints.calls == ["unset"]


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        (ColourSchemeChoice.LIGHT, "set Light"),
        (ColourSchemeChoice.DARK, "set Dark"),
    ],
)
def test_a_change_asks_qt_for_that_scheme(
    choice: ColourSchemeChoice, expected: str
) -> None:
    hints = _RecordingHints()
    preference = ColourSchemePreference()
    ColourSchemeApplier(preference, hints)

    preference.set_choice(choice)

    assert hints.calls == [expected]


def test_the_restored_choice_is_applied_at_start() -> None:
    hints = _RecordingHints()
    preference = ColourSchemePreference()
    preference.restore_state({"choice": "dark"})

    ColourSchemeApplier(preference, hints).apply_now()

    assert hints.calls == ["set Dark"]


def test_a_stopped_applier_asks_nothing_more() -> None:
    hints = _RecordingHints()
    preference = ColourSchemePreference()
    applier = ColourSchemeApplier(preference, hints)
    applier.stop()

    preference.set_choice(ColourSchemeChoice.DARK)

    assert hints.calls == []


def test_the_log_says_what_qt_reports_after_the_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    hints = _RecordingHints()
    preference = ColourSchemePreference()
    ColourSchemeApplier(preference, hints)

    with caplog.at_level(logging.INFO, logger="App.UiKit.ColourScheme"):
        preference.set_choice(ColourSchemeChoice.DARK)

    assert "dark asked of Qt; Qt now reports Dark" in caplog.text


def test_the_real_style_hints_accept_every_choice(qapp) -> None:
    """The calls exist on this PySide6 and Qt accepts them (whether the platform then draws
    differently is the platform's: Qt's offscreen platform does not, `EPIC-043A`)."""
    hints = QGuiApplication.styleHints()
    preference = ColourSchemePreference()
    applier = ColourSchemeApplier(preference, hints)
    try:
        for choice in ColourSchemeChoice:
            preference.set_choice(choice)
    finally:
        applier.stop()
        hints.unsetColorScheme()
