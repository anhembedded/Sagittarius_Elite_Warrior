"""`EPIC-043C`: a state is an icon and a word, the word in the state's tone, redrawn with the scheme."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QHBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_badge import StateBadge
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_look import StateLook
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_icon import tone_icon

_RUNNING = StateLook("play", Tone.POSITIVE)
_TEXT = QPalette.ColorRole.WindowText


@pytest.fixture
def restore_app_palette(qapp):
    saved = QGuiApplication.palette()
    yield
    QGuiApplication.setPalette(saved)


def _app_palette(base: str) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Base, QColor(base))
    return palette


def _icon_pixels(badge: StateBadge) -> bytes:
    pixmap = badge._icon.pixmap()
    return bytes(pixmap.toImage().constBits())


def test_a_state_with_a_look_shows_its_word_beside_an_icon(qtbot) -> None:
    badge = StateBadge("lblState")
    qtbot.addWidget(badge)
    badge.show()

    badge.show_state("Running", _RUNNING)

    assert badge.text() == "Running"
    assert badge._icon.isVisible()
    assert not badge._icon.pixmap().isNull()


def test_a_state_with_no_look_is_its_word_alone(qtbot) -> None:
    badge = StateBadge("lblState")
    qtbot.addWidget(badge)
    badge.show()
    badge.show_state("Running", _RUNNING)

    badge.show_state("Draft", None)

    assert badge.text() == "Draft"
    assert not badge._icon.isVisible()


def test_the_word_takes_the_tones_colour(qtbot, restore_app_palette) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    badge = StateBadge("lblState")
    qtbot.addWidget(badge)

    badge.show_state("Halted", StateLook("triangle-alert", Tone.NEGATIVE))

    assert badge._text.palette().color(_TEXT) == tone_colour(
        Tone.NEGATIVE, QGuiApplication.palette()
    )


def test_set_text_keeps_the_labels_own_reading(qtbot) -> None:
    badge = StateBadge("lblState")
    qtbot.addWidget(badge)

    badge.setText("hello")

    assert badge.text() == "hello"


def test_the_icon_is_drawn_again_when_the_colour_scheme_changes(
    qtbot, qapp, restore_app_palette
) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    badge = StateBadge("lblState")
    qtbot.addWidget(badge)
    badge.show_state("Running", _RUNNING)
    on_light = _icon_pixels(badge)

    QGuiApplication.setPalette(_app_palette("black"))
    qapp.processEvents()

    assert _icon_pixels(badge) != on_light


def test_the_object_names_let_a_reader_find_the_parts(qtbot) -> None:
    badge = StateBadge("lblState")
    qtbot.addWidget(badge)

    assert badge.objectName() == "lblState"
    assert badge.findChild(type(badge._icon), "lblState::icon") is badge._icon
    assert badge.findChild(type(badge._text), "lblState::text") is badge._text


@pytest.mark.parametrize("tone", [Tone.POSITIVE, Tone.NEGATIVE])
def test_a_tone_icon_differs_from_the_plain_one_on_a_palette(
    qapp, tone: Tone, restore_app_palette
) -> None:
    QGuiApplication.setPalette(_app_palette("white"))

    toned = tone_icon("play", tone, 16).pixmap(16, 16).toImage()
    plain = tone_icon("play", Tone.NEUTRAL, 16).pixmap(16, 16).toImage()

    assert toned != plain


_LONG_LINE = (
    "Not connected: the exchange has not answered the last three checks in a row"
)


def _host_of(badge: StateBadge, qtbot) -> QWidget:
    host = QWidget()
    qtbot.addWidget(host)
    QHBoxLayout(host).addWidget(badge)
    badge.setText(_LONG_LINE)
    return host


def test_a_wrapping_badge_may_shrink_and_a_plain_one_holds_its_line(qtbot) -> None:
    """A wrapped badge folds a long line instead of widening its host; the status bar's keeps
    its content's width so it does not crowd its neighbours."""
    wrapped = _host_of(StateBadge("wrapped", wrap=True), qtbot)
    plain = _host_of(StateBadge("plain"), qtbot)

    assert wrapped.minimumSizeHint().width() < wrapped.sizeHint().width() // 2
    assert plain.minimumSizeHint().width() >= plain.sizeHint().width()
