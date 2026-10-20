"""`EPIC-043C`: a label's text takes a tone's colour on the palette and follows a scheme change."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.support.ui_kit import meaning_colours
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_label import paint_label_tone

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


def test_a_tone_colours_the_labels_text_on_the_palette(
    qapp, restore_app_palette
) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    label = QLabel("+1.00")

    paint_label_tone(label, Tone.POSITIVE)

    assert label.palette().color(_TEXT) == tone_colour(
        Tone.POSITIVE, QGuiApplication.palette()
    )


def test_a_label_follows_a_change_of_colour_scheme(qapp, restore_app_palette) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    label = QLabel("-1.00")
    paint_label_tone(label, Tone.NEGATIVE)
    on_light = label.palette().color(_TEXT)

    QGuiApplication.setPalette(_app_palette("black"))
    qapp.processEvents()

    on_dark = label.palette().color(_TEXT)
    assert on_light == tone_colour(Tone.NEGATIVE, _app_palette("white"))
    assert on_dark == tone_colour(Tone.NEGATIVE, _app_palette("black"))
    assert on_light != on_dark


def test_a_label_that_loses_its_tone_gets_the_platforms_colour_back(
    qapp, restore_app_palette
) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    label = QLabel("1.00")
    plain = label.palette().color(_TEXT)
    paint_label_tone(label, Tone.POSITIVE)

    paint_label_tone(label, Tone.NEUTRAL)

    assert label.palette().color(_TEXT) == plain


def test_a_label_never_toned_is_left_alone(qapp) -> None:
    label = QLabel("1.00")
    before = label.palette()

    paint_label_tone(label, Tone.NEUTRAL)

    assert label.palette() == before
    assert not label.children()


def test_in_high_contrast_the_platform_keeps_the_colour(
    qapp, restore_app_palette, monkeypatch: pytest.MonkeyPatch
) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    monkeypatch.setattr(meaning_colours, "is_high_contrast", lambda: True)
    label = QLabel("-1.00")
    plain = label.palette().color(_TEXT)

    paint_label_tone(label, Tone.NEGATIVE)

    assert label.palette().color(_TEXT) == plain


def test_toning_twice_keeps_one_follower(qapp, restore_app_palette) -> None:
    QGuiApplication.setPalette(_app_palette("white"))
    label = QLabel("1.00")

    paint_label_tone(label, Tone.POSITIVE)
    paint_label_tone(label, Tone.NEGATIVE)

    assert len(label.findChildren(type(label.children()[0]))) == 1
    assert label.palette().color(_TEXT) == tone_colour(
        Tone.NEGATIVE, QGuiApplication.palette()
    )
