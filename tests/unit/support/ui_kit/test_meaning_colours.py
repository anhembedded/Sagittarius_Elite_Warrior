import pytest
from PySide6.QtGui import QColor, QPalette
from Sagittarius_Elite_Warrior.src.support.ui_kit import meaning_colours
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    LOSS_COLOUR,
    MIN_TEXT_CONTRAST,
    PROFIT_COLOUR,
    Tone,
    tone_colour,
)


def test_a_verdict_has_a_colour_and_no_verdict_has_none():
    assert tone_colour(Tone.POSITIVE) == PROFIT_COLOUR
    assert tone_colour(Tone.NEGATIVE) == LOSS_COLOUR
    assert tone_colour(Tone.NEUTRAL) is None


def test_profit_and_loss_are_told_apart():
    assert PROFIT_COLOUR != LOSS_COLOUR


def test_the_colour_returned_is_a_copy():
    colour = tone_colour(Tone.POSITIVE)
    assert colour is not None
    colour.setRed(0)
    assert tone_colour(Tone.POSITIVE) == PROFIT_COLOUR


def _palette(base: str) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Base, QColor(base))
    return palette


def _luminance(colour: QColor) -> float:
    def channel(value: int) -> float:
        unit = value / 255
        return unit / 12.92 if unit <= 0.03928 else ((unit + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(colour.red())
        + 0.7152 * channel(colour.green())
        + 0.0722 * channel(colour.blue())
    )


def _contrast(first: QColor, second: QColor) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


_TONES = (Tone.POSITIVE, Tone.NEGATIVE, Tone.CAUTION)


@pytest.mark.parametrize("base", ["white", "black", "#1e1e1e", "#f3f3f3"])
@pytest.mark.parametrize("tone", _TONES)
def test_a_tone_reads_as_text_on_a_light_and_on_a_dark_base(base, tone):
    palette = _palette(base)
    colour = tone_colour(tone, palette)
    assert colour is not None
    background = palette.color(QPalette.ColorRole.Base)
    assert _contrast(colour, background) >= MIN_TEXT_CONTRAST


@pytest.mark.parametrize("base", ["white", "black"])
def test_no_verdict_has_no_colour_on_any_base(base):
    assert tone_colour(Tone.NEUTRAL, _palette(base)) is None


def test_profit_and_loss_and_caution_are_told_apart_on_each_base():
    for base in ("white", "black"):
        names = {tone_colour(tone, _palette(base)).name() for tone in _TONES}
        assert len(names) == 3


def test_high_contrast_leaves_every_colour_to_the_platform(monkeypatch):
    monkeypatch.setattr(meaning_colours, "is_high_contrast", lambda: True)
    for base in ("white", "black"):
        assert [tone_colour(tone, _palette(base)) for tone in _TONES] == [None] * 3


def test_other_platforms_are_never_in_high_contrast(monkeypatch):
    monkeypatch.setattr(meaning_colours.sys, "platform", "linux")
    assert meaning_colours.is_high_contrast() is False
